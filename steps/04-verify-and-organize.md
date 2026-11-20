# 步驟 4：影片驗收、狀態更新與暫存清理（AI 驗收 + 使用者抽查）

**前置條件**：已完成 [步驟 3](./03-download-and-mux.md)，且 `output/` 已產出目標檔案。  
**執行主體**：AI 助理執行技術驗證與清理，使用者做最終播放確認。  
**目標**：確保影片完整無損，清理暫存空間並完成任務結案。

---

## AI 執行動作

### 1. 使用 `ffprobe` 驗證檔案完整性
AI 針對 `output/` 新產出的影片執行檢查：

```powershell
ffprobe -v error -show_entries format=duration,size -show_streams "output\<片名>.<格式>"
```

AI 須確認：
* 同時存在 `codec_type=video` 與 `codec_type=audio` 串流。
* `duration`（總秒數）與 `size`（檔案大小）為合理數值，非異常截斷或空檔案。

### 2. 清理暫存目錄
確認輸出檔無誤後，AI 清理 `temp/` 目錄下的暫存分片：

```powershell
Remove-Item -Path "temp\*" -Recurse -Force -ErrorAction SilentlyContinue
```

### 3. 更新任務狀態為完成
AI 將 `tasks.json` 中對應任務的 `status` 由 `"downloaded"` 更新為 `"completed"`。

### 4. 回報使用者並請抽查播放
AI 向使用者回報以下資訊：
* 輸出檔案完整路徑與檔案大小、影片時長
* 請使用者開啟檔案抽查開頭、中段、結尾的畫面與字幕是否正常

---

## 完成條件 (Exit Criteria)

- [ ] `ffprobe` 確認影音軌與時長正常
- [ ] `temp/` 已清空
- [ ] `tasks.json` 對應任務狀態已標記為 `"completed"`
- [ ] 已將成品路徑回報給使用者
