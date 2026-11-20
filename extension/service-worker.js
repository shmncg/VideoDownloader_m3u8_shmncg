const LOCAL_ENDPOINT = "http://127.0.0.1:18765/ingest";
const STREAM_URL_RE = /\.(m3u8|mpd)(\?|$)|\/(master|playlist|index[^/]*)\.(m3u8|mpd|txt)(\?|$)/i;
const SEGMENT_URL_RE = /\.(m4s|ts)(\?|$)|\/init-[^/]+\.mp4(\?|$)/i;
const SUB_URL_RE = /\.(vtt|srt)(\?|$)/i;
const PLAYLIST_MIME_RE = /mpegurl|dash\+xml/i;
const MEDIA_MIME_RE = /^video\//i;

function isSegmentUrl(url) {
  return SEGMENT_URL_RE.test(url);
}

function getBaseUrl(url) {
  try {
    const u = new URL(url);
    return `${u.origin}${u.pathname}`;
  } catch {
    return url.split("?")[0];
  }
}

function getDirKey(url) {
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/");
    parts.pop();
    return `${u.origin}${parts.join("/")}`;
  } catch {
    return url;
  }
}

async function tryAutoSend(tabId, stream, subtitles) {
  const { autoSend = false } = await chrome.storage.local.get("autoSend");
  if (!autoSend || stream.isSegment) return;

  const sentKey = `autosent_${tabId}`;
  const prev = await chrome.storage.session.get(sentKey);
  let originKey = stream.url;
  try {
    originKey = new URL(stream.url).origin;
  } catch {
    // ignore
  }
  if (prev[sentKey] && prev[sentKey].origin === originKey && Date.now() - prev[sentKey].ts < 15000) {
    return;
  }
  await chrome.storage.session.set({ [sentKey]: { origin: originKey, ts: Date.now() } });

  let title = "Video_Download";
  try {
    const tab = await chrome.tabs.get(tabId);
    if (tab?.title) title = tab.title.slice(0, 60);
  } catch {
    // ignore
  }

  try {
    await fetch(LOCAL_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: stream.url,
        referer: stream.referer || "",
        user_agent: stream.userAgent || "",
        subtitle_url: subtitles[0]?.url || "",
        title
      })
    });
  } catch {
    // VideoDownloader.exe might not be running
  }
}

async function saveTabItem(tabId, category, item) {
  if (tabId < 0) return;
  const key = `tab_${tabId}`;
  const data = await chrome.storage.local.get(key);
  const entry = data[key] || { streams: [], subtitles: [] };

  if (category === "subtitles") {
    if (!entry.subtitles.some((x) => x.url === item.url)) {
      entry.subtitles.unshift(item);
      if (entry.subtitles.length > 10) entry.subtitles.length = 10;
      await chrome.storage.local.set({ [key]: entry });
    }
    return;
  }

  if (item.isSegment) {
    const dir = getDirKey(item.url);
    const existingIdx = entry.streams.findIndex(
      (x) => x.isSegment && getDirKey(x.url) === dir
    );
    if (existingIdx >= 0) {
      entry.streams[existingIdx] = item;
    } else {
      entry.streams.push(item);
    }
  } else {
    const base = getBaseUrl(item.url);
    const existing = entry.streams.find((x) => !x.isSegment && x.url === item.url);
    if (existing) return;
    entry.streams = entry.streams.filter(
      (x) => x.isSegment || getBaseUrl(x.url) !== base
    );
    entry.streams.unshift(item);
  }

  // Keep all non-segment playlists (up to 10) and at most 5 segment samples
  const playlists = entry.streams.filter((x) => !x.isSegment).slice(0, 10);
  const segments = entry.streams.filter((x) => x.isSegment).slice(0, 5);
  entry.streams = [...playlists, ...segments];

  await chrome.storage.local.set({ [key]: entry });

  const count = playlists.length || entry.streams.length;
  try {
    await chrome.action.setBadgeText({
      tabId,
      text: count > 0 ? String(count) : ""
    });
    await chrome.action.setBadgeBackgroundColor({
      tabId,
      color: playlists.length > 0 ? "#188038" : "#1a73e8"
    });
  } catch {
    // Tab may have been closed or prerendered
  }
}

chrome.webRequest.onBeforeSendHeaders.addListener(
  async (details) => {
    if (details.tabId < 0) return;
    const headers = details.requestHeaders || [];
    let referer = "";
    let userAgent = "";
    for (const h of headers) {
      const name = (h.name || "").toLowerCase();
      if (name === "referer") referer = h.value || "";
      else if (name === "user-agent") userAgent = h.value || "";
    }

    await chrome.storage.session.set({
      [`req_${details.requestId}`]: { referer, userAgent }
    });

    if (SUB_URL_RE.test(details.url)) {
      await saveTabItem(details.tabId, "subtitles", {
        url: details.url,
        referer,
        userAgent,
        ts: Date.now()
      });
    } else if (STREAM_URL_RE.test(details.url)) {
      await saveTabItem(details.tabId, "streams", {
        url: details.url,
        referer,
        userAgent,
        hint: "主清單 (Playlist)",
        isSegment: false,
        ts: Date.now()
      });
    } else if (isSegmentUrl(details.url)) {
      await saveTabItem(details.tabId, "streams", {
        url: details.url,
        referer,
        userAgent,
        hint: "影片分片 (請重新整理頁面以抓主清單)",
        isSegment: true,
        ts: Date.now()
      });
    }
  },
  { urls: ["<all_urls>"] },
  ["requestHeaders", "extraHeaders"]
);

chrome.webRequest.onHeadersReceived.addListener(
  async (details) => {
    if (details.tabId < 0) return;
    const respHeaders = details.responseHeaders || [];
    const ctHeader = respHeaders.find(
      (h) => (h.name || "").toLowerCase() === "content-type"
    );
    const contentType = ctHeader ? ctHeader.value || "" : "";

    const reqKey = `req_${details.requestId}`;
    const sess = await chrome.storage.session.get(reqKey);
    const reqInfo = sess[reqKey] || { referer: "", userAgent: "" };
    await chrome.storage.session.remove(reqKey);

    if (PLAYLIST_MIME_RE.test(contentType)) {
      await saveTabItem(details.tabId, "streams", {
        url: details.url,
        referer: reqInfo.referer,
        userAgent: reqInfo.userAgent,
        hint: contentType.split(";")[0],
        isSegment: false,
        ts: Date.now()
      });
    } else if (MEDIA_MIME_RE.test(contentType) && !isSegmentUrl(details.url)) {
      await saveTabItem(details.tabId, "streams", {
        url: details.url,
        referer: reqInfo.referer,
        userAgent: reqInfo.userAgent,
        hint: contentType.split(";")[0],
        isSegment: false,
        ts: Date.now()
      });
    }
  },
  { urls: ["<all_urls>"] },
  ["responseHeaders"]
);

chrome.tabs.onRemoved.addListener(async (tabId) => {
  await chrome.storage.local.remove(`tab_${tabId}`);
});
