import unittest
from unittest.mock import patch

from audiogram_generator.services import transcript as transcript_svc
from audiogram_generator.services import rss as rss_svc
from audiogram_generator.services.errors import SrtFetchError, RssError


class TestServicesErrors(unittest.TestCase):
    @patch("urllib.request.urlopen", side_effect=RuntimeError("boom"))
    def test_fetch_srt_raises_typed_error(self, _):
        with self.assertRaises(SrtFetchError):
            transcript_svc.fetch_srt("https://example/bad.srt")

    @patch("urllib.request.urlopen", side_effect=RuntimeError("boom"))
    def test_fetch_feed_raises_typed_error(self, _):
        with self.assertRaises(RssError):
            rss_svc.fetch_feed("https://example/feed.xml")


if __name__ == "__main__":
    unittest.main()
