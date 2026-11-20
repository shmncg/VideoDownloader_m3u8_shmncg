"""Unit tests for curl_parser and m3u8_parser."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.curl_parser import parse_curl_or_url, sanitize_filename
from core.m3u8_parser import parse_master_m3u8
from core.sniffer import SniffedStream, _score_stream, sniff_streams_from_page


class TestParsers(unittest.TestCase):
    def test_parse_plain_url(self) -> None:
        res = parse_curl_or_url("https://cdn.example.com/hls/master.m3u8?t=123")
        self.assertEqual(res.url, "https://cdn.example.com/hls/master.m3u8?t=123")
        self.assertEqual(res.referer, "")

    def test_parse_curl_bash(self) -> None:
        curl_cmd = (
            "curl 'https://cdn.example.com/master.m3u8?token=abc' \\\n"
            "  -H 'Referer: https://embed.example.com/' \\\n"
            "  -H 'User-Agent: Mozilla/5.0 TestAgent'"
        )
        res = parse_curl_or_url(curl_cmd)
        self.assertEqual(res.url, "https://cdn.example.com/master.m3u8?token=abc")
        self.assertEqual(res.referer, "https://embed.example.com/")
        self.assertEqual(res.user_agent, "Mozilla/5.0 TestAgent")

    def test_sanitize_filename(self) -> None:
        self.assertEqual(sanitize_filename('Movie: Part 1 / "HD"?'), "Movie_ Part 1 _ _HD_")

    def test_parse_master_m3u8(self) -> None:
        playlist = (
            "#EXTM3U\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=1500000,RESOLUTION=1280x720\n"
            "720p/index.m3u8\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=3500000,RESOLUTION=1920x1080\n"
            "1080p/index.m3u8\n"
        )
        variants = parse_master_m3u8(playlist, "https://cdn.example.com/hls/master.m3u8")
        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0].height, 1080)
        self.assertEqual(variants[0].url, "https://cdn.example.com/hls/1080p/index.m3u8")
        self.assertEqual(variants[1].height, 720)

    def test_sniffer_invalid_url_stops_immediately(self) -> None:
        res = sniff_streams_from_page("not-a-valid-url", max_attempts=3)
        self.assertFalse(res.success)
        self.assertTrue(res.fatal)

    def test_sniffer_stream_scoring(self) -> None:
        master = SniffedStream(url="https://cdn.example.com/hls/master.m3u8")
        ad = SniffedStream(url="https://ads.example.com/ad_preview.m3u8")
        self.assertGreater(_score_stream(master), _score_stream(ad))


if __name__ == "__main__":
    unittest.main()
