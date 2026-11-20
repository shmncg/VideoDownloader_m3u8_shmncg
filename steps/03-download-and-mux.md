# 步驟 3：自動下載與影音封裝（AI 執行）

**前置條件**：已完成 [步驟 2](./02-extract-stream-info.md)，且 `tasks.json` 有 `status == "pending"` 的任務。  
**執行主體**：AI 助理  
**目標**：確保下載腳本就緒並執行下載，將串流與字幕封裝至 `output/`。

---

## AI 執行動作

### 1. 檢查或建立 `scripts/download.py`
檢查 `d:\AI\Video\scripts\download.py` 是否存在。若不存在，AI 應先建立該 Python 腳本，並確保其具備以下功能：
1. 讀取 `tasks.json`，篩選 `status == "pending"` 的任務。
2. 組裝 HTTP Headers（`Referer`、`User-Agent`）。
3. **依 `resolution` 欄位決定目標畫質**：
   * 若 `resolution` 為 `"best"` 或未填：自動選擇最高畫質。
   * 若 `resolution` 指定為 `"1080p"` / `"720p"` / `"480p"` 等：先讀取 `master.m3u8` 的 `#EXT-X-STREAM-INF` 清單，找出對應高度（例如 `1080`）的串流網址或選項；若該影片沒有完全符合的解析度，則退回最接近且不超過目標（或改用 `best`）並提示使用者。
4. 偵測 `N_m3u8DL-RE` 是否可用（檢查系統 `PATH` 與 `scripts/N_m3u8DL-RE.exe`）：
   * **若可用**：呼叫 `N_m3u8DL-RE`，傳入 `--tmp-dir temp`、`--save-dir output`、`--save-name <title>`、對應畫質與最高音軌選項（預設 `-sv best -sa best`）、`--mux-after-done format=<output_format>`，以及 `-H "Referer: ..."`、`-H "User-Agent: ..."`。
   * **若不可用（備援）**：呼叫 `ffmpeg`，透過 `-headers "Referer: ...\r\nUser-Agent: ...\r\n"` 下載目標解析度串流並以 `-c copy` 封裝輸出至 `output/<title>.<output_format>`。
5. 若 `subtitle_url` 非空，下載字幕至 `temp/` 並使用 `ffmpeg` 封裝進影片（或另存同名 `.vtt`/`.srt` 於 `output/`）。
6. 依據指令回傳碼（exit code）更新 `tasks.json`：成功改為 `"downloaded"`，失敗改為 `"failed"` 並記錄 `error` 欄位。

### 2. 執行下載腳本
AI 執行以下指令開始下載：

```powershell
python scripts/download.py
```

### 3. 錯誤排查規則
若執行失敗，AI 應根據錯誤輸出判斷處理方式：
* **`403 Forbidden` / `401 Unauthorized` / Token 過期**：標記該任務失敗，並退回 **[步驟 2](./02-extract-stream-info.md)** 請使用者重新複製最新的 cURL / `m3u8_url`。
* **找不到音訊或影像合併失敗**：檢查 `ffmpeg` 是否在 `PATH` 中，或嘗試將 `output_format` 改為 `mkv` 重新封裝。
* **DRM 加密錯誤**：告知使用者該串流受 DRM 保護，無法透過一般串流下載工具處理。

---

## 完成條件 (Exit Criteria)

- [ ] `scripts/download.py` 執行結束且無失敗狀態
- [ ] `output/` 目錄下已產出對應 `<title>.<output_format>` 檔案
- [ ] `tasks.json` 對應任務狀態已更新為 `"downloaded"`

滿足以上條件後，AI 應進入 **[步驟 4：影片驗收、狀態更新與暫存清理](./04-verify-and-organize.md)**。
