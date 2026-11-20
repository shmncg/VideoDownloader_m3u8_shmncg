const LOCAL_ENDPOINT = "http://127.0.0.1:18765/ingest";

async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function render() {
  const tab = await getCurrentTab();
  const listEl = document.getElementById("list");
  const statusEl = document.getElementById("status");
  listEl.innerHTML = "";

  if (!tab) return;
  const key = `tab_${tab.id}`;
  const data = await chrome.storage.local.get(key);
  const entry = data[key] || { streams: [], subtitles: [] };

  if (entry.streams.length === 0) {
    listEl.innerHTML =
      '<div class="item">尚未偵測到串流。請先點擊播放影片，再重新打開此視窗。</div>';
    return;
  }

  const sorted = [...entry.streams].sort((a, b) => {
    const score = (s) => {
      if (s.isSegment) return -10;
      const u = s.url.toLowerCase();
      if (u.includes("master")) return 10;
      if (u.includes("playlist")) return 8;
      if (u.includes(".m3u8") || u.includes(".mpd")) return 5;
      return 1;
    };
    return score(b) - score(a);
  });

  for (const stream of sorted) {
    const div = document.createElement("div");
    div.className = "item";

    const isBest = !stream.isSegment && /master|playlist/i.test(stream.url);
    const urlDiv = document.createElement("div");
    urlDiv.className = "url";
    urlDiv.style.cursor = "pointer";
    urlDiv.textContent = (isBest ? "★ 推薦 | " : "") + stream.url;

    const metaDiv = document.createElement("div");
    metaDiv.className = "meta";
    metaDiv.textContent = `來源: ${stream.hint || "stream"} | 字幕: ${entry.subtitles.length} 個`;

    const btn = document.createElement("button");
    btn.className = "btn-send";
    btn.textContent = "傳送到 VideoDownloader";
    btn.addEventListener("click", async () => {
      statusEl.textContent = "傳送中...";
      statusEl.style.color = "#5f6368";
      try {
        const resp = await fetch(LOCAL_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url: stream.url,
            referer: stream.referer || "",
            user_agent: stream.userAgent || "",
            subtitle_url: entry.subtitles[0]?.url || "",
            title: (tab.title || "Video_Download").slice(0, 60)
          })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        statusEl.textContent = "已傳送到 VideoDownloader！請切回程式選畫質下載。";
        statusEl.style.color = "#188038";
      } catch (err) {
        statusEl.textContent = "傳送失敗：請確認 VideoDownloader.exe 已開啟。";
        statusEl.style.color = "#d93025";
      }
    });

    urlDiv.addEventListener("click", () => btn.click());

    div.appendChild(urlDiv);
    div.appendChild(metaDiv);
    div.appendChild(btn);
    listEl.appendChild(div);
  }
}

document.getElementById("clearBtn").addEventListener("click", async () => {
  const tab = await getCurrentTab();
  if (!tab) return;
  await chrome.storage.local.remove(`tab_${tab.id}`);
  await chrome.action.setBadgeText({ tabId: tab.id, text: "" });
  await render();
});

async function init() {
  await render();
}

init();
