"""
Test per i moduli del generatore di audiogrammi
"""
import unittest
from audiogram_generator import cli


class TestCliModule(unittest.TestCase):
    """Test per il modulo CLI"""

    def test_parse_srt_time(self):
        """Test conversione timestamp SRT in secondi"""
        # Test formato: 00:00:10,500 -> 10.5 secondi
        self.assertEqual(cli.parse_srt_time("00:00:10,500"), 10.5)
        self.assertEqual(cli.parse_srt_time("00:01:00,000"), 60.0)
        self.assertEqual(cli.parse_srt_time("01:00:00,000"), 3600.0)
        self.assertEqual(cli.parse_srt_time("00:00:00,500"), 0.5)
        self.assertEqual(cli.parse_srt_time("00:05:30,250"), 330.25)

    def test_parse_srt_time_edge_cases(self):
        """Test casi limite per la conversione timestamp SRT"""
        # Timestamp a zero
        self.assertEqual(cli.parse_srt_time("00:00:00,000"), 0.0)

        # Timestamp con millisecondi
        self.assertEqual(cli.parse_srt_time("00:00:01,123"), 1.123)


if __name__ == "__main__":
    unittest.main()
