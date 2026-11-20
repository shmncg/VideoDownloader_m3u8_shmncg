"""Ultra-minimal desktop GUI for HLS video downloading."""

from __future__ import annotations

import json
import os
import re
import threading
import tkinter as tk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import messagebox, scrolledtext, ttk

from core.curl_parser import parse_curl_or_url, sanitize_filename
from core.downloader import (
    ProgressInfo,
    find_executable,
    get_app_root,
    resume_process,
    run_download_task,
    suspend_process,
)
from core.m3u8_parser import get_available_variants


class VideoDownloaderApp(tk.Tk):
    """Minimal Tkinter window focused on resolution selection and progress."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Video Downloader")
        self.geometry("560x285")
        self.minsize(500, 260)

        self.app_root = get_app_root()
        (self.app_root / "bin").mkdir(exist_ok=True)
        (self.app_root / "temp").mkdir(exist_ok=True)
        (self.app_root / "output").mkdir(exist_ok=True)

        self._is_running = False
        self._is_paused = False
        self._cancel_requested = False
        self._active_proc = None
        self._advanced_visible = False
        self._build_ui()
        self._refresh_tool_status()
        self._start_local_receiver()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.url_var = tk.StringVar()
        self.referer_var = tk.StringVar()
        self.ua_var = tk.StringVar()
        self.sub_var = tk.StringVar()
        self.title_var = tk.StringVar(value="尚未收到影片（請在 Chrome 播放）")
        self.format_var = tk.StringVar(value="mp4")
        self.resolution_var = tk.StringVar(value="best")
        self.auto_download_var = tk.BooleanVar(value=False)
        self.tool_status_var = tk.StringVar(value="")

        # Main compact card
        main_frame = ttk.Frame(self, padding=(14, 12, 14, 6))
        main_frame.pack(fill="x")
        main_frame.columnconfigure(1, weight=1)

        ttk.Label(main_frame, text="目前影片:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(
            main_frame, textvariable=self.title_var, foreground="#1a73e8"
        ).grid(row=0, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=4)

        ttk.Label(main_frame, text="串流網址:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(main_frame, textvariable=self.url_var).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=4
        )

        ttk.Label(main_frame, text="選擇解析度:").grid(row=2, column=0, sticky="w", pady=6)
        self.res_combo = ttk.Combobox(
            main_frame,
            textvariable=self.resolution_var,
            values=["best", "2160p", "1080p", "720p", "480p", "360p"],
            state="readonly",
            width=26,
        )
        self.res_combo.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=6)

        ttk.Checkbutton(
            main_frame,
            text="收到後自動下載",
            variable=self.auto_download_var,
        ).grid(row=2, column=2, sticky="e", pady=6)

        # Action buttons
        btn_frame = ttk.Frame(self, padding=(14, 4))
        btn_frame.pack(fill="x")
        self.download_btn = ttk.Button(
            btn_frame, text="開始下載", command=self._on_start_download
        )
        self.download_btn.pack(side="left")
        self.pause_btn = ttk.Button(
            btn_frame, text="暫停", command=self._on_toggle_pause, state="disabled"
        )
        self.pause_btn.pack(side="left", padx=(8, 0))
        self.stop_btn = ttk.Button(
            btn_frame, text="停止下載", command=self._on_stop_download, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(8, 0))
        ttk.Button(
            btn_frame, text="開啟資料夾", command=self._on_open_output
        ).pack(side="left", padx=(8, 0))
        self.adv_btn = ttk.Button(
            btn_frame, text="進階 ▾", command=self._toggle_advanced
        )
        self.adv_btn.pack(side="right")

        # Progress bar & live size/speed
        prog_frame = ttk.Frame(self, padding=(14, 8, 14, 10))
        prog_frame.pack(fill="x")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            prog_frame, variable=self.progress_var, maximum=100.0, mode="determinate"
        )
        self.progress_bar.pack(fill="x", pady=(0, 4))
        self.progress_label_var = tk.StringVar(value="待機中")
        ttk.Label(prog_frame, textvariable=self.progress_label_var).pack(anchor="w")

        # Collapsible advanced panel (hidden by default)
        self.adv_frame = ttk.LabelFrame(self, text="進階設定與執行紀錄")
        self.adv_frame.columnconfigure(1, weight=1)

        ttk.Label(self.adv_frame, textvariable=self.tool_status_var).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(4, 4)
        )
        ttk.Label(self.adv_frame, text="輸出片名:").grid(row=1, column=0, sticky="w", padx=8, pady=2)
        ttk.Entry(self.adv_frame, textvariable=self.title_var).grid(
            row=1, column=1, sticky="ew", padx=8, pady=2
        )
        ttk.Combobox(
            self.adv_frame,
            textvariable=self.format_var,
            values=["mp4", "mkv"],
            state="readonly",
            width=6,
        ).grid(row=1, column=2, padx=(0, 8), pady=2)

        ttk.Label(self.adv_frame, text="手動 cURL:").grid(row=2, column=0, sticky="nw", padx=8, pady=2)
        self.curl_text = scrolledtext.ScrolledText(self.adv_frame, height=2, wrap="word")
        self.curl_text.grid(row=2, column=1, sticky="ew", padx=8, pady=2)
        ttk.Button(self.adv_frame, text="解析", command=self._on_parse_curl).grid(
            row=2, column=2, padx=(0, 8), pady=2
        )

        self.log_box = scrolledtext.ScrolledText(
            self.adv_frame, height=6, state="disabled", wrap="word"
        )
        self.log_box.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=8, pady=(4, 8))
        self.adv_frame.rowconfigure(3, weight=1)

    def _toggle_advanced(self) -> None:
        if self._advanced_visible:
            self.adv_frame.pack_forget()
            self.adv_btn.configure(text="進階 ▾")
            self.geometry("560x285")
            self._advanced_visible = False
        else:
            self.geometry("620x480")
            self.adv_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))
            self.adv_btn.configure(text="進階 ▴")
            self._advanced_visible = True

    def _log(self, msg: str) -> None:
        def append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, append)

    def _refresh_tool_status(self) -> None:
        n_dl = find_executable("N_m3u8DL-RE", self.app_root)
        ffmpeg = find_executable("ffmpeg", self.app_root)
        ffprobe = find_executable("ffprobe", self.app_root)
        engine = "N_m3u8DL-RE" if n_dl else ("ffmpeg" if ffmpeg else "缺少下載工具")
        self.tool_status_var.set(
            f"引擎: {engine}  |  ffprobe: {'OK' if ffprobe else '未找到'}  |  接收埠: 18765"
        )

    def _on_parse_curl(self) -> None:
        raw = self.curl_text.get("1.0", "end").strip()
        if not raw:
            return
        parsed = parse_curl_or_url(raw)
        if not parsed.url:
            messagebox.showerror("解析失敗", "無法從內容中辨識出有效的 http/https 網址。")
            return
        self.url_var.set(parsed.url)
        self.referer_var.set(parsed.referer)
        self.ua_var.set(parsed.user_agent)
        if self.title_var.get().startswith("尚未收到"):
            self.title_var.set("Video_Download")
        self._log(f"[手動解析完成] {parsed.url[:80]}...")
        self._probe_resolutions()

    def _probe_resolutions(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            return

        def worker() -> None:
            try:
                variants = get_available_variants(
                    url,
                    referer=self.referer_var.get().strip(),
                    user_agent=self.ua_var.get().strip(),
                )
                if not variants:
                    self.after(0, lambda: self.res_combo.configure(values=["best"]))
                    self.after(0, lambda: self.resolution_var.set("best"))
                else:
                    options = ["best"] + [v.label for v in variants]
                    self._log("可用畫質: " + ", ".join(v.label for v in variants))
                    self.after(0, lambda: self.res_combo.configure(values=options))
                    self.after(0, lambda: self.resolution_var.set(options[1]))
            except Exception as exc:
                self._log(f"[讀取畫質失敗] {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_start_download(self) -> None:
        if self._is_running:
            return
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "尚未收到影片，請先在 Chrome 播放影片。")
            return

        raw_res = self.resolution_var.get().strip()
        m = re.search(r"(\d+p)", raw_res)
        target_res = m.group(1) if m else "best"
        title = self.title_var.get().strip()
        if not title or title.startswith("尚未收到"):
            title = "Video_Download"

        self._is_running = True
        self._is_paused = False
        self._cancel_requested = False
        self.download_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="暫停")
        self.stop_btn.configure(state="normal")
        self.progress_var.set(0.0)
        self.progress_label_var.set("準備下載中...")
        self._log(f"\n=== 開始下載: {title} ({target_res}) ===")

        def on_progress(info: ProgressInfo) -> None:
            def update_ui() -> None:
                size_mb = info.downloaded_bytes / (1024 * 1024)
                pct_str = f"{info.percent:.1f}%" if info.percent is not None else "處理中"
                if info.percent is not None:
                    self.progress_var.set(info.percent)
                cur_m, cur_s = divmod(int(info.current_sec), 60)
                tot_m, tot_s = divmod(int(info.total_sec), 60)
                time_str = (
                    f"{cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d}"
                    if info.total_sec > 0
                    else f"{cur_m:02d}:{cur_s:02d}"
                )
                spd = f" | {info.speed}" if info.speed else ""
                self.progress_label_var.set(
                    f"{pct_str}  |  已下載 {size_mb:.1f} MB  |  {time_str}{spd}"
                )

            self.after(0, update_ui)

        def worker() -> None:
            try:
                result = run_download_task(
                    title=title,
                    m3u8_url=url,
                    referer=self.referer_var.get().strip(),
                    user_agent=self.ua_var.get().strip(),
                    subtitle_url=self.sub_var.get().strip(),
                    resolution=target_res,
                    output_format=self.format_var.get(),
                    app_root=self.app_root,
                    log_cb=self._log,
                    progress_cb=on_progress,
                    cancel_check=lambda: self._cancel_requested,
                    proc_cb=lambda p: setattr(self, "_active_proc", p),
                )
                if result.success:
                    self._log(f"[完成] {result.message}")
                    self.after(0, lambda: self.progress_var.set(100.0))
                    self.after(0, lambda: self.progress_label_var.set(result.message))
                    self.after(0, lambda: messagebox.showinfo("下載完成", result.message))
                else:
                    self._log(f"[結束] {result.message}")
                    status_msg = "已中斷下載" if self._cancel_requested else "下載失敗"
                    self.after(0, lambda: self.progress_label_var.set(status_msg))
                    if not self._cancel_requested:
                        self.after(0, lambda: messagebox.showerror("下載失敗", result.message))
            finally:
                self._is_running = False
                self._is_paused = False
                self._active_proc = None
                self.after(0, lambda: self.download_btn.configure(state="normal"))
                self.after(0, lambda: self.pause_btn.configure(state="disabled", text="暫停"))
                self.after(0, lambda: self.stop_btn.configure(state="disabled"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_toggle_pause(self) -> None:
        if not self._is_running or self._active_proc is None:
            return
        pid = self._active_proc.pid
        if not self._is_paused:
            if suspend_process(pid):
                self._is_paused = True
                self.pause_btn.configure(text="繼續")
                self.progress_label_var.set("已暫停（點擊「繼續」可恢復下載）")
                self._log("[已暫停下載]")
        else:
            if resume_process(pid):
                self._is_paused = False
                self.pause_btn.configure(text="暫停")
                self.progress_label_var.set("恢復下載中...")
                self._log("[繼續下載]")

    def _on_stop_download(self) -> None:
        if not self._is_running:
            return
        self._cancel_requested = True
        self.pause_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        self.progress_label_var.set("正在中斷下載...")
        proc = self._active_proc
        if proc is not None:
            try:
                if self._is_paused:
                    resume_process(proc.pid)
                proc.terminate()
            except Exception:
                pass

    def _start_local_receiver(self) -> None:
        app_ref = self

        class IngestHandler(BaseHTTPRequestHandler):
            def _send_cors(self, status: int = 200, body: bytes = b'{"ok":true}') -> None:
                self.send_response(status)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self) -> None:  # noqa: N802
                self._send_cors(204, b"")

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/ingest":
                    self._send_cors(404, b'{"error":"not found"}')
                    return
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception:
                    self._send_cors(400, b'{"error":"invalid json"}')
                    return

                app_ref.after(0, lambda: app_ref._apply_extension_payload(payload))
                self._send_cors(200, b'{"ok":true}')

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

        def serve() -> None:
            try:
                server = ThreadingHTTPServer(("127.0.0.1", 18765), IngestHandler)
                app_ref._log("[就緒] 等待 Chrome 擴充功能傳入影片...")
                server.serve_forever()
            except OSError as exc:
                app_ref._log(f"[接收端未啟動] 18765 埠被佔用: {exc}")

        threading.Thread(target=serve, daemon=True).start()

    def _apply_extension_payload(self, payload: dict) -> None:
        url = (payload.get("url") or "").strip()
        if not url:
            return
        if self._is_running:
            self._log("[略過] 目前已有下載任務進行中")
            return
        self.url_var.set(url)
        self.referer_var.set((payload.get("referer") or "").strip())
        self.ua_var.set((payload.get("user_agent") or "").strip())
        self.sub_var.set((payload.get("subtitle_url") or "").strip())
        raw_title = (payload.get("title") or "").strip()
        self.title_var.set(sanitize_filename(raw_title) if raw_title else "Video_Download")
        self.progress_label_var.set("已收到影片！請選擇解析度後點「開始下載」")
        self._log(f"\n[已接收影片] {self.title_var.get()}")
        self.lift()
        if self.auto_download_var.get():
            self._on_start_download()
        else:
            self._probe_resolutions()

    def _on_open_output(self) -> None:
        out_dir = self.app_root / "output"
        out_dir.mkdir(exist_ok=True)
        os.startfile(str(out_dir))

    def _on_close(self) -> None:
        self._cancel_requested = True
        proc = self._active_proc
        if proc is not None:
            try:
                if self._is_paused:
                    resume_process(proc.pid)
                proc.terminate()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = VideoDownloaderApp()
    app.mainloop()
