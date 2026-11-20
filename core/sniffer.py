"""Smart webpage stream sniffer using Playwright + system Microsoft Edge."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class SniffedStream:
    url: str
    referer: str = ""
    user_agent: str = ""
    is_master: bool = False


@dataclass
class SniffResult:
    success: bool
    streams: list[SniffedStream] = field(default_factory=list)
    subtitles: list[str] = field(default_factory=list)
    reason: str = ""
    fatal: bool = False  # True means retrying won't help (e.g. DRM, 404, user closed)


_DRM_KEYWORDS = ("widevine", "fairplay", "playready", "clearkey", "drm", "license")
_STREAM_PATTERN = re.compile(r"\.(m3u8|mpd)(\?|$)", re.IGNORECASE)
_SUB_PATTERN = re.compile(r"\.(vtt|srt)(\?|$)", re.IGNORECASE)


def _is_valid_http_url(url: str) -> bool:
    return url.startswith(("http://", "https://")) and "." in url


def _score_stream(stream: SniffedStream) -> int:
    u = stream.url.lower()
    score = 0
    if "master" in u or "playlist" in u or "index" in u:
        score += 10
    if ".m3u8" in u:
        score += 5
    if "ad" in u or "trailer" in u or "preview" in u:
        score -= 8
    return score


def sniff_streams_from_page(
    page_url: str,
    *,
    max_attempts: int = 3,
    wait_seconds: int = 45,
    log_cb: Callable[[str], None] | None = None,
    stop_check: Callable[[], bool] | None = None,
) -> SniffResult:
    """Open page_url in visible Edge, intercept .m3u8/.mpd and subtitles.

    Retries transient failures up to max_attempts, but stops immediately on
    fatal conditions (invalid URL, 404/DNS error, DRM detected, user closed).
    """
    log = log_cb or print
    url = page_url.strip()
    if not _is_valid_http_url(url):
        return SniffResult(success=False, reason="網址格式無效，請輸入 http:// 或 https:// 開頭的網址。", fatal=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return SniffResult(
            success=False,
            reason="尚未安裝 playwright，請先執行 pip install playwright。",
            fatal=True,
        )

    last_reason = "未在時間內攔截到串流網址"
    for attempt in range(1, max_attempts + 1):
        if stop_check and stop_check():
            return SniffResult(success=False, reason="使用者已取消偵測。", fatal=True)

        log(f"[偵測 {attempt}/{max_attempts}] 正在開啟 Edge 載入頁面...")
        result = _single_sniff_attempt(
            url,
            wait_seconds=wait_seconds,
            log=log,
            stop_check=stop_check,
        )
        if result.success:
            return result

        last_reason = result.reason
        if result.fatal:
            log(f"[停止重試] {result.reason}")
            return result

        if attempt < max_attempts:
            log(f"[準備重試] {result.reason}，2 秒後重試...")
            time.sleep(2)

    return SniffResult(
        success=False,
        reason=f"已重試 {max_attempts} 次仍未抓到串流（{last_reason}）。建議改用「Copy as cURL」備援模式。",
        fatal=False,
    )


def _single_sniff_attempt(
    page_url: str,
    *,
    wait_seconds: int,
    log: Callable[[str], None],
    stop_check: Callable[[], bool] | None,
) -> SniffResult:
    from playwright.sync_api import sync_playwright

    streams: dict[str, SniffedStream] = {}
    subtitles: list[str] = []
    drm_detected = False
    http_fatal_status: int | None = None
    user_closed = False

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                channel="msedge",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception as exc:
            return SniffResult(
                success=False,
                reason=f"無法啟動 Microsoft Edge：{exc}",
                fatal=True,
            )

        context = browser.new_context()
        page = context.new_page()

        def on_close(_: object = None) -> None:
            nonlocal user_closed
            user_closed = True

        page.on("close", on_close)

        # Auto-close popup ad tabs that open unexpectedly
        def on_new_page(new_page: object) -> None:
            try:
                log("      偵測到彈出分頁（疑似廣告），已自動關閉。")
                new_page.close()  # type: ignore[attr-defined]
            except Exception:
                pass

        context.on("page", on_new_page)

        def on_request(req: object) -> None:
            nonlocal drm_detected
            try:
                req_url = req.url  # type: ignore[attr-defined]
                lower = req_url.lower()
                if any(k in lower for k in _DRM_KEYWORDS) and "license" in lower:
                    drm_detected = True
                    return

                headers = req.headers  # type: ignore[attr-defined]
                if _STREAM_PATTERN.search(req_url) or ".m3u8" in lower:
                    if req_url not in streams:
                        streams[req_url] = SniffedStream(
                            url=req_url,
                            referer=headers.get("referer", ""),
                            user_agent=headers.get("user-agent", ""),
                            is_master=("master" in lower or "playlist" in lower),
                        )
                        log(f"      [攔截到串流] {req_url[:90]}...")
                elif _SUB_PATTERN.search(req_url):
                    if req_url not in subtitles:
                        subtitles.append(req_url)
                        log(f"      [攔截到字幕] {req_url[:90]}...")
            except Exception:
                pass

        context.on("request", on_request)

        try:
            log("      正在導向目標網頁...")
            resp = page.goto(page_url, wait_until="commit", timeout=25000)
            if resp is not None and resp.status in (404, 410, 451):
                http_fatal_status = resp.status
        except Exception as exc:
            err_s = str(exc).lower()
            try:
                browser.close()
            except Exception:
                pass
            if "err_name_not_resolved" in err_s or "invalid url" in err_s:
                return SniffResult(
                    success=False,
                    reason="網址無法解析（網域不存在或 DNS 錯誤），停止重試。",
                    fatal=True,
                )
            return SniffResult(success=False, reason=f"頁面載入逾時或失敗: {exc}", fatal=False)

        if http_fatal_status is not None:
            try:
                browser.close()
            except Exception:
                pass
            return SniffResult(
                success=False,
                reason=f"目標頁面回傳 HTTP {http_fatal_status}（頁面不存在或已下架），停止重試。",
                fatal=True,
            )

        log("      頁面已開啟，請在視窗中確認影片開始播放（若有驗證或播放鍵請手動點擊）...")

        deadline = time.monotonic() + wait_seconds
        stable_since: float | None = None

        while time.monotonic() < deadline:
            if user_closed:
                try:
                    browser.close()
                except Exception:
                    pass
                return SniffResult(success=False, reason="瀏覽器視窗已被關閉。", fatal=True)

            if stop_check and stop_check():
                try:
                    browser.close()
                except Exception:
                    pass
                return SniffResult(success=False, reason="使用者已取消。", fatal=True)

            if drm_detected:
                try:
                    browser.close()
                except Exception:
                    pass
                return SniffResult(
                    success=False,
                    reason="偵測到 DRM 加密授權請求，此影片受 DRM 保護無法下載。",
                    fatal=True,
                )

            if streams:
                if stable_since is None:
                    stable_since = time.monotonic()
                # Wait briefly (2.5s) after first stream in case master.m3u8 / subtitle arrives right after
                elif time.monotonic() - stable_since >= 2.5:
                    break

            try:
                page.wait_for_timeout(400)
            except Exception:
                break

        try:
            browser.close()
        except Exception:
            pass

    if not streams:
        return SniffResult(
            success=False,
            reason=f"等待 {wait_seconds} 秒後仍未攔截到 .m3u8 / .mpd 串流。",
            fatal=False,
        )

    ordered = sorted(streams.values(), key=_score_stream, reverse=True)
    return SniffResult(
        success=True,
        streams=ordered,
        subtitles=subtitles,
        reason=f"成功攔截到 {len(ordered)} 個串流與 {len(subtitles)} 個字幕。",
    )
