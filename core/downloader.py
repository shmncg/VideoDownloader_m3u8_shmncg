"""Download, mux, verify, and clean up HLS video tasks."""

from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.curl_parser import sanitize_filename
from core.m3u8_parser import resolve_target_url

_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
_PROCESS_SUSPEND_RESUME = 0x0800


def suspend_process(pid: int) -> bool:
    """Suspend a Windows process by PID."""
    if os.name != "nt":
        return False
    handle = ctypes.windll.kernel32.OpenProcess(_PROCESS_SUSPEND_RESUME, False, pid)
    if not handle:
        return False
    try:
        return ctypes.windll.ntdll.NtSuspendProcess(handle) == 0
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def resume_process(pid: int) -> bool:
    """Resume a suspended Windows process by PID."""
    if os.name != "nt":
        return False
    handle = ctypes.windll.kernel32.OpenProcess(_PROCESS_SUSPEND_RESUME, False, pid)
    if not handle:
        return False
    try:
        return ctypes.windll.ntdll.NtResumeProcess(handle) == 0
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def get_app_root() -> Path:
    """Return project root (or executable directory when packaged with PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def find_executable(name: str, app_root: Path | None = None) -> str | None:
    """Locate an executable in bin/, scripts/, app root, or system PATH."""
    root = app_root or get_app_root()
    exe_name = f"{name}.exe" if os.name == "nt" and not name.lower().endswith(".exe") else name

    candidates = [
        root / "bin" / exe_name,
        root / "scripts" / exe_name,
        root / exe_name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    return shutil.which(name) or shutil.which(exe_name)


@dataclass
class DownloadResult:
    success: bool
    output_file: str = ""
    message: str = ""
    duration_sec: float = 0.0
    size_bytes: int = 0


@dataclass
class ProgressInfo:
    percent: float | None = None
    downloaded_bytes: int = 0
    current_sec: float = 0.0
    total_sec: float = 0.0
    speed: str = ""
    status_text: str = ""


def _probe_m3u8_duration(
    ffprobe_path: str | None,
    url: str,
    referer: str = "",
    user_agent: str = "",
) -> float:
    if not ffprobe_path:
        return 0.0
    header_lines = []
    if referer:
        header_lines.append(f"Referer: {referer}")
    if user_agent:
        header_lines.append(f"User-Agent: {user_agent}")
    cmd = [ffprobe_path, "-v", "error"]
    if header_lines:
        cmd.extend(["-headers", "\r\n".join(header_lines) + "\r\n"])
    cmd.extend([
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        url,
    ])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_SUBPROCESS_FLAGS,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return float(proc.stdout.strip())
    except Exception:
        pass
    return 0.0


def _download_subtitle(
    subtitle_url: str,
    dest_path: Path,
    referer: str = "",
    user_agent: str = "",
) -> Path | None:
    if not subtitle_url:
        return None
    headers: dict[str, str] = {}
    if referer:
        headers["Referer"] = referer
    if user_agent:
        headers["User-Agent"] = user_agent
    req = urllib.request.Request(subtitle_url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        dest_path.write_bytes(resp.read())
    return dest_path


def verify_video(ffprobe_path: str | None, video_path: Path) -> tuple[bool, float, int, str]:
    """Verify video has streams and non-zero duration/size."""
    if not video_path.is_file():
        return False, 0.0, 0, "找不到輸出檔案"

    size_bytes = video_path.stat().st_size
    if size_bytes < 1024:
        return False, 0.0, size_bytes, f"檔案過小 ({size_bytes} bytes)"

    if not ffprobe_path:
        return True, 0.0, size_bytes, "未安裝 ffprobe，僅檢查檔案大小通過"

    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_entries", "format=duration,size:stream=codec_type",
        "-of", "json",
        str(video_path),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_SUBPROCESS_FLAGS,
    )
    if proc.returncode != 0:
        return False, 0.0, size_bytes, f"ffprobe 檢查失敗: {proc.stderr.strip()}"

    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return False, 0.0, size_bytes, "ffprobe 輸出解析失敗"

    streams = info.get("streams", [])
    types = {s.get("codec_type") for s in streams}
    if "video" not in types:
        return False, 0.0, size_bytes, "缺少視訊軌 (video stream)"

    duration = float(info.get("format", {}).get("duration") or 0.0)
    return True, duration, size_bytes, "驗證通過"


def run_download_task(
    *,
    title: str,
    m3u8_url: str,
    referer: str = "",
    user_agent: str = "",
    subtitle_url: str = "",
    resolution: str = "best",
    output_format: str = "mp4",
    app_root: Path | None = None,
    log_cb: Callable[[str], None] | None = None,
    progress_cb: Callable[[ProgressInfo], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
    proc_cb: Callable[[subprocess.Popen[str] | None], None] | None = None,
) -> DownloadResult:
    """Execute a full download + mux + verify + temp-cleanup cycle."""
    log = log_cb or print
    report_progress = progress_cb or (lambda _: None)
    is_cancelled = cancel_check or (lambda: False)
    set_proc = proc_cb or (lambda _: None)
    root = app_root or get_app_root()
    temp_dir = root / "temp"
    output_dir = root / "output"
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_title = sanitize_filename(title)
    fmt = (output_format or "mp4").lower().lstrip(".")
    if fmt not in ("mp4", "mkv"):
        fmt = "mp4"

    n_m3u8dl = find_executable("N_m3u8DL-RE", root)
    ffmpeg = find_executable("ffmpeg", root)
    ffprobe = find_executable("ffprobe", root)

    if not n_m3u8dl and not ffmpeg:
        return DownloadResult(
            success=False,
            message="找不到 N_m3u8DL-RE 或 ffmpeg，請先安裝並放入 PATH 或 bin/ 目錄。",
        )

    log(f"[1/4] 解析畫質設定 ({resolution})...")
    target_url, chosen_desc = resolve_target_url(
        m3u8_url, target_resolution=resolution, referer=referer, user_agent=user_agent
    )
    log(f"      選擇串流: {chosen_desc}")

    output_file = output_dir / f"{safe_title}.{fmt}"
    sub_file: Path | None = None
    if subtitle_url.strip():
        ext = ".srt" if ".srt" in subtitle_url.lower() else ".vtt"
        sub_dest = output_dir / f"{safe_title}{ext}"
        try:
            log("[2/4] 下載外掛字幕...")
            sub_file = _download_subtitle(subtitle_url.strip(), sub_dest, referer, user_agent)
            log(f"      字幕已儲存: {sub_file.name}")
        except Exception as exc:
            log(f"      字幕下載失敗（略過）: {exc}")

    log("[3/4] 開始下載與封裝影片...")
    total_sec = _probe_m3u8_duration(ffprobe, target_url, referer, user_agent)
    if total_sec > 0:
        log(f"      預估總片長: {int(total_sec // 60)} 分 {int(total_sec % 60)} 秒")

    if n_m3u8dl:
        cmd = [
            n_m3u8dl,
            target_url,
            "--tmp-dir", str(temp_dir),
            "--save-dir", str(output_dir),
            "--save-name", safe_title,
            "-sv", "best",
            "-sa", "best",
            "--mux-after-done", f"format={fmt}",
        ]
        if ffmpeg:
            cmd.extend(["--ffmpeg-binary-path", ffmpeg])
        if referer:
            cmd.extend(["-H", f"Referer: {referer}"])
        if user_agent:
            cmd.extend(["-H", f"User-Agent: {user_agent}"])
    else:
        assert ffmpeg is not None
        header_lines = []
        if referer:
            header_lines.append(f"Referer: {referer}")
        if user_agent:
            header_lines.append(f"User-Agent: {user_agent}")
        cmd = [ffmpeg, "-y"]
        if header_lines:
            cmd.extend(["-headers", "\r\n".join(header_lines) + "\r\n"])
        cmd.extend([
            "-i", target_url,
            "-c", "copy",
            "-progress", "pipe:1",
            "-nostats",
            str(output_file),
        ])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_SUBPROCESS_FLAGS,
    )
    set_proc(proc)
    assert proc.stdout is not None
    last_lines: list[str] = []
    cur_bytes = 0
    cur_sec = 0.0
    cur_speed = ""

    try:
        for line in proc.stdout:
            if is_cancelled():
                proc.terminate()
                break
            stripped = line.strip()
            if not stripped:
                continue

            if not n_m3u8dl and "=" in stripped:
                k, v = stripped.split("=", 1)
                if k == "total_size" and v.isdigit():
                    cur_bytes = int(v)
                elif k == "out_time_us" and v.lstrip("-").isdigit():
                    cur_sec = max(0.0, int(v) / 1_000_000.0)
                elif k == "speed":
                    cur_speed = v
                elif k == "progress":
                    pct = min(100.0, (cur_sec / total_sec) * 100.0) if total_sec > 0 else None
                    report_progress(ProgressInfo(
                        percent=pct,
                        downloaded_bytes=cur_bytes,
                        current_sec=cur_sec,
                        total_sec=total_sec,
                        speed=cur_speed,
                        status_text="下載中...",
                    ))
                continue

            log(f"      {stripped}")
            last_lines.append(stripped)
            if len(last_lines) > 20:
                last_lines.pop(0)
    finally:
        rc = proc.wait()
        set_proc(None)

    if is_cancelled():
        for leftover in (output_file, sub_file):
            if leftover is not None and leftover.is_file():
                try:
                    leftover.unlink()
                except Exception:
                    pass
        return DownloadResult(success=False, message="已由使用者中斷下載。")

    if rc != 0:
        err_hint = "\n".join(last_lines[-5:])
        if "403" in err_hint or "401" in err_hint:
            return DownloadResult(
                success=False,
                message="伺服器回傳 403/401，可能是 Referer 不符或 m3u8 Token 已過期，請重新複製 cURL。",
            )
        return DownloadResult(
            success=False,
            message=f"下載程序失敗 (exit code {rc})。最後輸出:\n{err_hint}",
        )

    # Locate actual output file (N_m3u8DL-RE may output .mp4/.mkv)
    if not output_file.is_file():
        alt = output_dir / f"{safe_title}.{'mkv' if fmt == 'mp4' else 'mp4'}"
        if alt.is_file():
            output_file = alt

    log("[4/4] 驗證影片完整性並清理暫存...")
    ok, duration, size_bytes, verify_msg = verify_video(ffprobe, output_file)
    if not ok:
        return DownloadResult(success=False, output_file=str(output_file), message=verify_msg)

    # Clean temp directory
    for item in temp_dir.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
        except Exception:
            pass

    size_mb = size_bytes / (1024 * 1024)
    return DownloadResult(
        success=True,
        output_file=str(output_file),
        message=f"完成！{verify_msg}（大小 {size_mb:.1f} MB，時長 {duration:.0f} 秒）",
        duration_sec=duration,
        size_bytes=size_bytes,
    )
