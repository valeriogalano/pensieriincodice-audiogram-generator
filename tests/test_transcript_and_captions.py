"""
Test per funzioni di trascrizione e generazione caption in cli.py
"""
import io
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from audiogram_generator import cli


FAKE_SRT = """
1
00:00:00,000 --> 00:00:02,000
Fuori dal range

2
00:00:05,000 --> 00:00:07,000
Dentro l'intervallo uno

3
00:00:07,000 --> 00:00:09,000
Dentro l'intervallo due

4
00:00:09,500 --> 00:00:10,000
Parzialmente dentro (da escludere)
""".strip()


class TestTranscriptAndCaptions(unittest.TestCase):
    """Test parsing SRT e generazione file caption"""

    def _mock_urlopen(self):
        # Restituisce un oggetto simile a HTTPResponse con read() -> bytes
        mm = MagicMock()
        mm.read.return_value = FAKE_SRT.encode("utf-8")
        # Contesto per with ... as response
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mm
        mock_ctx.__exit__.return_value = False
        return mock_ctx

    @patch("urllib.request.urlopen")
    def test_get_transcript_text_range(self, mock_urlopen):
        """Estrae solo i blocchi SRT interamente contenuti nell'intervallo"""
        mock_urlopen.return_value = self._mock_urlopen()
        # Intervallo: start=5s, durata=4s -> [5,9]
        text = cli.get_transcript_text("http://example/srt", 5, 4)
        # Deve includere i blocchi 2 e 3, ma non 1 (fuori) né 4 (parziale)
        self.assertIsNotNone(text)
        self.assertIn("Dentro l'intervallo uno", text)
        self.assertIn("Dentro l'intervallo due", text)
        self.assertNotIn("Fuori", text)
        self.assertNotIn("Parzialmente", text)

    @patch("urllib.request.urlopen")
    def test_get_transcript_text_no_matches(self, mock_urlopen):
        """Restituisce None se nessun blocco è interamente contenuto"""
        mock_urlopen.return_value = self._mock_urlopen()
        text = cli.get_transcript_text("http://example/srt", 20, 3)
        self.assertIsNone(text)

    @patch("urllib.request.urlopen")
    def test_get_transcript_chunks_relative_timing(self, mock_urlopen):
        """I chunk hanno tempi relativi al soundbite e rispettano i limiti"""
        mock_urlopen.return_value = self._mock_urlopen()
        chunks = cli.get_transcript_chunks("http://example/srt", 5, 4)
        self.assertEqual(len(chunks), 2)
        # Primo chunk: [5,7] -> relativo [0,2]
        self.assertAlmostEqual(chunks[0]['start'], 0)
        self.assertAlmostEqual(chunks[0]['end'], 2)
        self.assertIn("intervallo uno", chunks[0]['text'])
        # Secondo chunk: [7,9] -> relativo [2,4]
        self.assertAlmostEqual(chunks[1]['start'], 2)
        self.assertAlmostEqual(chunks[1]['end'], 4)

    def test_generate_caption_file_hashtags_and_defaults(self):
        """Genera file con hashtag normalizzati e di default quando assenti"""
        with tempfile.NamedTemporaryFile("r+", suffix=".txt", delete=True) as tmp:
            cli.generate_caption_file(
                output_path=tmp.name,
                episode_number=42,
                episode_title="Titolo",
                episode_link="https://example/ep",
                soundbite_title="SB",
                transcript_text="Testo",
                podcast_keywords="AI, coding, #Podcast",
                episode_keywords="AI,   Dev Ops",
                config_hashtags=["Podcast", "python"]
            )
            tmp.seek(0)
            content = tmp.read()
            # Intestazione e corpo
            self.assertIn("Episodio 42: Titolo", content)
            self.assertIn("SB", content)
            self.assertIn("Testo", content)
            self.assertIn("Ascolta l'episodio completo: https://example/ep", content)
            # Hashtag: normalizzati, unici, con # e in minuscolo, niente spazi
            self.assertIn("#ai", content)
            self.assertIn("#coding", content)
            self.assertIn("#podcast", content)
            self.assertIn("#devops", content)
            self.assertIn("#python", content)

        # Nessun hashtag disponibile -> usa default #podcast
        with tempfile.NamedTemporaryFile("r+", suffix=".txt", delete=True) as tmp2:
            cli.generate_caption_file(
                output_path=tmp2.name,
                episode_number=1,
                episode_title="x",
                episode_link="y",
                soundbite_title="z",
                transcript_text="t",
                podcast_keywords=None,
                episode_keywords=None,
                config_hashtags=None
            )
            tmp2.seek(0)
            content2 = tmp2.read()
            self.assertIn("#podcast", content2)


if __name__ == "__main__":
    unittest.main()
