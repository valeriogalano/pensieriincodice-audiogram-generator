"""
Test per il modulo generator
"""
import unittest
from pathlib import Path
from audiogram_generator.generator import AudiogramGenerator


class TestAudiogramGenerator(unittest.TestCase):
    """Test per AudiogramGenerator"""

    def setUp(self):
        """Setup per i test"""
        self.generator = AudiogramGenerator()

    def test_initialization(self):
        """Test inizializzazione del generatore"""
        self.assertIsNotNone(self.generator)
        self.assertIsNotNone(self.generator.video_generator)

    def test_custom_parameters(self):
        """Test inizializzazione con parametri personalizzati"""
        generator = AudiogramGenerator(
            width=1280,
            height=720,
            fps=24,
            background_color=(0, 0, 0),
            waveform_color=(255, 255, 255)
        )
        self.assertEqual(generator.video_generator.width, 1280)
        self.assertEqual(generator.video_generator.height, 720)
        self.assertEqual(generator.video_generator.fps, 24)


if __name__ == "__main__":
    unittest.main()
