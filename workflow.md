# 半自動網路影片下載流程 (AI 執行指南 / Workflow)

本文件是提供給 **AI 助理** 與 **使用者** 協作的標準作業流程（SOP）。  
未來當使用者提出「我要下載某部影片」時，AI 應嚴格參照本文件，依序讀取並執行 `steps/` 下的每一個步驟文件，直到影片成功下載並通過驗收。

---

## AI 執行總則

1. **循序執行**：必須依照 `步驟 1 → 步驟 2 → 步驟 3 → 步驟 4` 的順序推進；若某步驟的前置檢查已滿足（例如步驟 1 的環境與目錄皆已存在），AI 可快速驗證通過後直接進入下一步。
2. **人機分工（半自動原則）**：
   * **AI 負責**：環境檢查、檔案與腳本建立、解析使用者提供的串流資訊並寫入 `tasks.json`、執行下載指令、錯誤排查、`ffprobe` 驗收與清理歸檔。
   * **使用者負責**：在瀏覽器開啟目標頁面、完成必要的人機驗證或點擊播放、從 DevTools 複製串流請求資訊（URL / Headers / cURL）提供給 AI，以及最後實際播放抽查。
3. **不繞過驗證**：遇到登入、Cloudflare 或人機驗證時，AI 應請使用者於瀏覽器自行完成，不得嘗試繞過安全機制。
4. **狀態追蹤**：每完成一個步驟，AI 須對照該步驟的「完成條件（Exit Criteria）」確認無誤後，才可進入下一步。

---

## 流程總覽與步驟索引

| 順序 | 步驟文件 | 執行主體 | 核心任務 | 完成條件 (Exit Criteria) |
| :--- | :--- | :--- | :--- | :--- |
| 1 | [01-environment-setup.md](./steps/01-environment-setup.md) | **AI 主導** | 檢查 `python` / `ffmpeg` / `N_m3u8DL-RE`，確認目錄與 `tasks.json` 就緒 | 工具可用、資料夾與 `tasks.json` 存在 |
| 2 | [02-extract-stream-info.md](./steps/02-extract-stream-info.md) | **使用者取流 → AI 寫入** | 使用者提供 `.m3u8` / Headers（或 cURL），AI 解析並寫入 `tasks.json` | `tasks.json` 存在有效的 `pending` 任務 |
| 3 | [03-download-and-mux.md](./steps/03-download-and-mux.md) | **AI 主導** | 確保 `scripts/download.py` 存在並執行下載、合併與字幕封裝 | `output/` 產出目標影片檔 |
| 4 | [04-verify-and-organize.md](./steps/04-verify-and-organize.md) | **AI 驗收 + 使用者抽查** | AI 執行 `ffprobe` 檢查、清理 `temp/`、更新 `tasks.json` 狀態 | 檔案驗證通過且狀態為 `completed` |

---

## 目錄結構

```text
d:\AI\Video\
├── workflow.md                  # 本流程總覽（AI 入口文件）
├── steps/                       # 各階段 AI 執行步驟
│   ├── 01-environment-setup.md
│   ├── 02-extract-stream-info.md
│   ├── 03-download-and-mux.md
│   └── 04-verify-and-organize.md
├── scripts/
│   └── download.py              # 本地自動下載與封裝腳本
├── tasks.json                   # 任務佇列與狀態紀錄
├── temp/                        # 下載暫存分片（步驟 4 清理）
└── output/                      # 最終影片輸出目錄
```
