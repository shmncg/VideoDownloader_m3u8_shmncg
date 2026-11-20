"""Fetch and parse HLS master playlists (.m3u8) for resolution selection."""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass
class StreamVariant:
    """A single video variant inside an HLS master playlist."""

    resolution: str  # e.g., "1920x1080"
    height: int      # e.g., 1080
    bandwidth: int   # bits per second
    url: str

    @property
    def label(self) -> str:
        if self.height > 0:
            return f"{self.height}p ({self.resolution})"
        return f"bandwidth {self.bandwidth}"


def fetch_text(url: str, referer: str = "", user_agent: str = "", timeout: int = 15) -> str:
    """Download a text resource (m3u8/vtt) with optional Referer and User-Agent."""
    headers: dict[str, str] = {}
    if referer:
        headers["Referer"] = referer
    if user_agent:
        headers["User-Agent"] = user_agent
    else:
        headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_master_m3u8(content: str, base_url: str) -> list[StreamVariant]:
    """Parse #EXT-X-STREAM-INF entries from a master m3u8 playlist."""
    variants: list[StreamVariant] = []
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXT-X-STREAM-INF:"):
            attrs = line[len("#EXT-X-STREAM-INF:"):]
            res_match = re.search(r"RESOLUTION=(\d+x\d+)", attrs, re.IGNORECASE)
            bw_match = re.search(r"BANDWIDTH=(\d+)", attrs, re.IGNORECASE)

            resolution = res_match.group(1) if res_match else ""
            height = int(resolution.split("x")[1]) if "x" in resolution else 0
            bandwidth = int(bw_match.group(1)) if bw_match else 0

            # Next non-comment line is the variant URI
            j = i + 1
            while j < len(lines) and lines[j].startswith("#"):
                j += 1
            if j < len(lines):
                variant_url = urljoin(base_url, lines[j])
                variants.append(
                    StreamVariant(
                        resolution=resolution,
                        height=height,
                        bandwidth=bandwidth,
                        url=variant_url,
                    )
                )
            i = j + 1
            continue
        i += 1

    variants.sort(key=lambda v: (v.height, v.bandwidth), reverse=True)
    return variants


def get_available_variants(
    m3u8_url: str,
    referer: str = "",
    user_agent: str = "",
) -> list[StreamVariant]:
    """Fetch a master m3u8 URL and return sorted StreamVariant options."""
    content = fetch_text(m3u8_url, referer=referer, user_agent=user_agent)
    return parse_master_m3u8(content, m3u8_url)


def resolve_target_url(
    m3u8_url: str,
    target_resolution: str = "best",
    referer: str = "",
    user_agent: str = "",
) -> tuple[str, str]:
    """Return (resolved_url, description) matching the requested resolution.

    If target_resolution is 'best' or the playlist has no variants, returns the
    original m3u8_url. Otherwise picks the exact height match, or closest lower
    resolution, or highest available.
    """
    req = (target_resolution or "best").strip().lower()
    if req in ("", "best"):
        return m3u8_url, "best"

    m = re.search(r"(\d+)", req)
    if not m:
        return m3u8_url, "best"
    target_height = int(m.group(1))

    try:
        variants = get_available_variants(m3u8_url, referer=referer, user_agent=user_agent)
    except Exception:
        return m3u8_url, "best (fallback)"

    if not variants:
        return m3u8_url, "single stream"

    exact = [v for v in variants if v.height == target_height]
    if exact:
        return exact[0].url, exact[0].label

    lower = [v for v in variants if 0 < v.height <= target_height]
    if lower:
        return lower[0].url, f"{lower[0].label} (closest)"

    return variants[0].url, f"{variants[0].label} (fallback best)"
