"""CLI runner that executes pending tasks in tasks.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.downloader import run_download_task


def main() -> int:
    tasks_file = ROOT_DIR / "tasks.json"
    if not tasks_file.is_file():
        print("找不到 tasks.json，請先依步驟 1 建立 tasks.json。")
        return 1

    data = json.loads(tasks_file.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    pending = [t for t in tasks if t.get("status") == "pending" and t.get("m3u8_url")]

    if not pending:
        print("tasks.json 中沒有 status 為 'pending' 的任務。")
        return 0

    for task in pending:
        title = task.get("title") or task.get("id") or "video"
        print(f"\n=== 開始處理任務: {title} ===")
        result = run_download_task(
            title=title,
            m3u8_url=task.get("m3u8_url", ""),
            referer=task.get("referer", ""),
            user_agent=task.get("user_agent", ""),
            subtitle_url=task.get("subtitle_url", ""),
            resolution=task.get("resolution", "best"),
            output_format=task.get("output_format", "mp4"),
            app_root=ROOT_DIR,
        )

        if result.success:
            task["status"] = "completed"
            task["output_file"] = result.output_file
            task.pop("error", None)
            print(f"[成功] {result.message}")
        else:
            task["status"] = "failed"
            task["error"] = result.message
            print(f"[失敗] {result.message}")

        tasks_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
