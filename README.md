# VideoDownloader — 通用 HLS / m3u8 串流下載工具

結合 **Chrome / Edge 瀏覽器擴充功能** 與 **Windows 本機桌面程式** 的輕量級串流下載工具，支援解析度選擇、外掛字幕抓取、即時進度條、暫停/繼續與中斷清理。

---

## 功能特色

* **瀏覽器端即時偵測**：透過 Manifest V3 擴充功能於背景偵測當前分頁的 `.m3u8` / `.mpd` 串流與 `.vtt` / `.srt` 字幕，並自動帶入 `Referer` 與 `User-Agent`。
* **手動挑選傳送**：在擴充功能清單中點擊目標串流（自動置頂標記 `master.m3u8` 總清單），才傳送至本機程式。
* **畫質選擇與封裝**：自動讀取 `master.m3u8` 中的可用解析度（如 `1080p`、`720p`、`480p` 或 `best`），支援輸出 `.mp4` / `.mkv`。
* **完整下載控制**：支援即時進度百分比與檔案大小顯示、**暫停 / 繼續**、**停止下載**（自動清理未完成檔案與字幕），以及 `ffprobe` 完整性驗證。

---

## 一般使用者安裝與使用（免安裝可攜版）

1. 前往本專案右側的 **Releases** 下載最新的 `VideoDownloader_Portable.zip` 並解壓縮。
2. **首次設定（只需一次）**：
   * 在 Chrome 前往 `chrome://extensions`（Edge 前往 `edge://extensions`）。
   * 開啟「**開發人員模式**」（必須保持開啟，未上架商店的擴充功能才能運作）。
   * 點擊「**載入未封裝項目**」，選擇解壓縮資料夾內的 `extension/`。
3. **開始下載**：
   * 雙擊開啟 `VideoDownloader\VideoDownloader.exe`（若 Windows 跳出未知發行者提示，點「其他資訊 → 仍要執行」）。
   * 在瀏覽器播放合法授權的串流影片後，點開右上角擴充功能圖示並點擊目標串流傳送至程式。
   * 選擇解析度後點「**開始下載**」，完成後點擊「**開啟資料夾**」即可在 `output\` 查看成品。

---

## 開發者從原始碼執行

### 環境需求
* Python 3.10+
* `ffmpeg` 與 `ffprobe`（加入系統 `PATH` 或放入 `bin/`）
* （選用）`N_m3u8DL-RE` 放入 `bin/` 可啟用多線程下載引擎

### 指令
```powershell
# 啟動桌面介面
python app.py

# 執行單元測試
python -m unittest discover -s tests -v

# 打包 Windows 可執行檔
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

---

## 免責聲明與授權 (Disclaimer & License)

* **合法使用**：本工具僅作為網路串流技術學習與**合法授權內容（如無版權限制、創用 CC 授權或個人擁有權限之影音）**的備份用途。
* **合規限制**：請勿將本工具用於未經授權之受版權保護內容；本工具不具備、亦不提供任何繞過 DRM（數位版權管理）或人機驗證之功能。使用者須自行遵守目標網站之服務條款及當地著作權相關法規。
* **第三方元件**：Releases 中附帶的可攜版包含 `FFmpeg` 二進位檔，其授權依 FFmpeg 官方條款為準。
