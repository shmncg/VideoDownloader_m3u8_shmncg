# 步驟 2：擷取串流資訊並寫入任務（人機協作）

**前置條件**：已完成 [步驟 1](./01-environment-setup.md)。  
**執行主體**：使用者於瀏覽器取流 → AI 解析並寫入 `tasks.json`。  
**目標**：取得有效且未過期的串流網址與必要 HTTP Headers，建立待下載任務。

---

## AI 執行動作

### 1. 引導使用者提供串流資訊
AI 應向使用者請求以下任一種格式的資訊，並簡要提示取得方式（在瀏覽器開啟影片播放 → `F12` → **Network** → 篩選 `m3u8`）：

* **方式 A（最推薦）**：在 DevTools 中對 `master.m3u8` / `playlist.m3u8` 請求按右鍵 → **Copy** → **Copy as cURL (bash 或 PowerShell)**，直接貼給 AI。
* **方式 B**：分別貼上：
  1. 影片名稱（`title`，用於輸出檔名）
  2. `m3u8_url`
  3. `referer` 與 `user_agent`
  4. 字幕網址 `subtitle_url`（若有，可從 Network 篩選 `vtt` 或 `srt` 取得）

### 2. 解析、查詢可用解析度與驗證輸入
收到使用者貼上的資訊後，AI 應執行以下檢查與處理：
* 若使用者提供 **cURL 指令**，AI 自動從中解析出 `m3u8_url`、`-H "Referer: ..."`（或 `Origin`）、`-H "User-Agent: ..."`。
* 若使用者未指定片名，詢問或依上下文命名，並自動移除 Windows 檔名非法字元（`\ / : * ? " < > |`）。
* 檢查 `m3u8_url` 是否為有效 URL（而非網頁 HTML 網址）。
* **解析度選擇（選用）**：
  * 詢問使用者偏好的解析度（預設為 `"best"` 最高畫質，或指定如 `"1080p"`、`"720p"`、`"480p"`）。
  * 若使用者想先看該影片有哪些畫質可選，AI 可帶著相同的 `Referer` 與 `User-Agent` 讀取 `m3u8_url` 內容（解析 `#EXT-X-STREAM-INF` 中的 `RESOLUTION`）或使用 `ffprobe` 列出可用解析度清單，讓使用者挑選後再寫入任務。

### 3. 寫入 `tasks.json`
AI 將解析後的任務附加（append）到 `d:\AI\Video\tasks.json` 的 `tasks` 陣列中，格式如下：

```json
{
  "id": "task-YYYYMMDD-HHMMSS",
  "title": "Movie_Name_1080p",
  "m3u8_url": "https://example.com/path/master.m3u8?token=...",
  "subtitle_url": "",
  "referer": "https://embed-player-domain.com/",
  "user_agent": "Mozilla/5.0 ...",
  "resolution": "1080p",
  "output_format": "mp4",
  "status": "pending"
}
```

> `resolution` 可填 `"best"`（自動選最高畫質）或目標高度如 `"1080p"`、`"720p"`、`"480p"`。

---

## 完成條件 (Exit Criteria)

- [ ] `tasks.json` 中已新增至少一筆 `status` 為 `"pending"` 且包含有效 `m3u8_url` 的任務

滿足以上條件後，因為串流 Token 具時效性，AI 應**立即**進入 **[步驟 3：自動下載與影音封裝](./03-download-and-mux.md)**。
