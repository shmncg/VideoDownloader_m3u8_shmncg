# 步驟 1：環境與工具準備（AI 執行）

**執行主體**：AI 助理  
**目標**：確保本機工具、專案目錄與 `tasks.json` 處於可執行狀態。若已存在且可用，快速驗證後即可進入步驟 2。

---

## AI 執行動作

### 1. 檢查必要工具
AI 應依序執行以下指令確認環境：

```powershell
python --version
ffmpeg -version
N_m3u8DL-RE --version
```

* **判斷邏輯**：
  * `python` 與 `ffmpeg` 為**必備**；若缺失，AI 應提示使用者安裝（例如建議 `winget install Python.Python.3.12`、`winget install Gyan.FFmpeg`）並暫停等待安裝完成。
  * `N_m3u8DL-RE` 為**強烈建議**（支援多線程 HLS/DASH 下載）；若未安裝，AI 應先檢查 `scripts/N_m3u8DL-RE.exe` 是否存在，若無則告知使用者可從 GitHub Releases 下載，或確認改以 `ffmpeg` 作為備援下載器後繼續。

### 2. 檢查並建立目錄結構
確認 `d:\AI\Video` 下包含 `scripts`、`temp`、`output` 三個資料夾，若不存在則建立：

```powershell
New-Item -ItemType Directory -Force -Path scripts, temp, output
```

### 3. 檢查並初始化 `tasks.json`
檢查 `d:\AI\Video\tasks.json` 是否存在。若不存在，建立如下初始內容：

```json
{
  "tasks": []
}
```

---

## 完成條件 (Exit Criteria)

- [ ] `python` 與 `ffmpeg` 可正常執行
- [ ] 已確認下載引擎（`N_m3u8DL-RE` 可用，或已確認使用 `ffmpeg` 備援）
- [ ] `scripts/`、`temp/`、`output/` 目錄與 `tasks.json` 皆已就緒

滿足以上條件後，AI 應立即進入 **[步驟 2：擷取串流資訊並寫入任務](./02-extract-stream-info.md)**。
