import io
import unittest
from unittest.mock import patch, MagicMock

from audiogram_generator.services import assets as assets_svc
from audiogram_generator.services.errors import AssetDownloadError


class TestAssetsService(unittest.TestCase):
    def _mock_urlopen(self, payload: bytes = b"PNGDATA"):
        mm = MagicMock()
        mm.read.return_value = payload
        ctx = MagicMock()
        ctx.__enter__.return_value = mm
        ctx.__exit__.return_value = False
        return ctx

    @patch("urllib.request.urlopen")
    def test_download_image_writes_file_and_returns_path(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen(b"\x89PNG\r\n")

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            path = assets_svc.download_image("https://example/image.png", tmp.name)
            self.assertEqual(path, tmp.name)
            tmp.seek(0)
            data = tmp.read()
            self.assertTrue(data.startswith(b"\x89PNG"))

    @patch("urllib.request.urlopen", side_effect=RuntimeError("network"))
    def test_download_image_propagates_errors(self, mock_urlopen):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            with self.assertRaises(AssetDownloadError):
                assets_svc.download_image("https://example/image.png", tmp.name)


if __name__ == "__main__":
    unittest.main()
