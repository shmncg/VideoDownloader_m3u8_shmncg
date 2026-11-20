"""Parse raw URLs or browser DevTools 'Copy as cURL' snippets."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field


@dataclass
class ParsedRequest:
    """Extracted stream request details."""

    url: str = ""
    referer: str = ""
    user_agent: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)


_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]+')


def sanitize_filename(name: str, fallback: str = "video") -> str:
    """Remove characters disallowed in Windows filenames."""
    cleaned = _INVALID_FILENAME_CHARS.sub("_", name).strip(" .")
    return cleaned or fallback


def _extract_url_from_text(text: str) -> str:
    match = re.search(r"https?://[^\s'\"`^]+", text)
    return match.group(0) if match else ""


def parse_curl_or_url(raw_input: str) -> ParsedRequest:
    """Parse a plain URL or a browser 'Copy as cURL' command into request fields."""
    text = raw_input.strip()
    if not text:
        return ParsedRequest()

    if not text.lower().startswith("curl"):
        return ParsedRequest(url=_extract_url_from_text(text))

    # Normalize line continuations for bash (\) and PowerShell (`) and cmd (^)
    normalized = re.sub(r"\s*[\\`^]\r?\n\s*", " ", text)

    # PowerShell Invoke-WebRequest / curl.exe uses -Headers or -H
    try:
        tokens = shlex.split(normalized, posix=True)
    except ValueError:
        # Fallback regex extraction if quotes are unbalanced
        url = _extract_url_from_text(normalized)
        ref_match = re.search(r"(?i)referer:\s*([^\r\n'\"]+)", normalized)
        ua_match = re.search(r"(?i)user-agent:\s*([^\r\n'\"]+)", normalized)
        return ParsedRequest(
            url=url,
            referer=ref_match.group(1).strip() if ref_match else "",
            user_agent=ua_match.group(1).strip() if ua_match else "",
        )

    url = ""
    referer = ""
    user_agent = ""
    extra_headers: dict[str, str] = {}

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-H", "--header") and i + 1 < len(tokens):
            header_line = tokens[i + 1]
            i += 2
            if ":" in header_line:
                key, val = header_line.split(":", 1)
                key_l = key.strip().lower()
                val_s = val.strip()
                if key_l == "referer":
                    referer = val_s
                elif key_l == "user-agent":
                    user_agent = val_s
                elif key_l == "origin" and not referer:
                    referer = val_s.rstrip("/") + "/"
                else:
                    extra_headers[key.strip()] = val_s
            continue

        if tok in ("-A", "--user-agent") and i + 1 < len(tokens):
            user_agent = tokens[i + 1].strip()
            i += 2
            continue

        if tok in ("-e", "--referer") and i + 1 < len(tokens):
            referer = tokens[i + 1].strip()
            i += 2
            continue

        if tok in ("--url",) and i + 1 < len(tokens):
            url = tokens[i + 1].strip()
            i += 2
            continue

        if not tok.startswith("-") and tok.startswith(("http://", "https://")) and not url:
            url = tok

        i += 1

    if not url:
        url = _extract_url_from_text(normalized)

    return ParsedRequest(
        url=url,
        referer=referer,
        user_agent=user_agent,
        extra_headers=extra_headers,
    )
