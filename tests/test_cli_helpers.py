"""
Test per le funzioni helper del modulo CLI (senza I/O esterno)
"""
import unittest
from audiogram_generator import cli


class TestCliHelpers(unittest.TestCase):
    """Test per funzioni pure e di parsing"""

    def test_format_seconds(self):
        """Test formattazione secondi in stringa HH:MM:SS.mmm"""
        self.assertEqual(cli.format_seconds(0), "00:00:00.000")
        self.assertEqual(cli.format_seconds(10.5), "00:00:10.500")
        self.assertEqual(cli.format_seconds(3661.007), "01:01:01.007")
        self.assertEqual(cli.format_seconds(-0.1), "-00:00:00.100")

    def test_parse_episode_selection_variants(self):
        """Test varianti per selezione episodi"""
        # None -> lista vuota
        self.assertEqual(cli.parse_episode_selection(None, 5), [])
        # Intero valido
        self.assertEqual(cli.parse_episode_selection(3, 5), [3])
        # Lista con spazi e duplicati (mantiene ordine e rimuove duplicati)
        self.assertEqual(cli.parse_episode_selection("1, 2, 2, 3", 5), [1, 2, 3])
        # all/a case-insensitive
        self.assertEqual(cli.parse_episode_selection("ALL", 3), [1, 2, 3])
        self.assertEqual(cli.parse_episode_selection(" a ", 2), [1, 2])
        # last
        self.assertEqual(cli.parse_episode_selection("last", 7), [7])

    def test_parse_episode_selection_invalid(self):
        """Errori su valori non validi per episodi"""
        with self.assertRaises(ValueError):
            cli.parse_episode_selection(0, 5)
        with self.assertRaises(ValueError):
            cli.parse_episode_selection("0", 5)
        with self.assertRaises(ValueError):
            cli.parse_episode_selection("abc", 5)
        with self.assertRaises(ValueError):
            cli.parse_episode_selection("", 5)

    def test_parse_soundbite_selection_variants(self):
        """Test varianti per selezione soundbite"""
        # None -> tutti
        self.assertEqual(cli.parse_soundbite_selection(None, 3), [1, 2, 3])
        # Intero valido
        self.assertEqual(cli.parse_soundbite_selection(2, 3), [2])
        # Lista stringa con spazi e duplicati
        self.assertEqual(cli.parse_soundbite_selection("1, 1, 3", 3), [1, 3])
        # all/a case-insensitive
        self.assertEqual(cli.parse_soundbite_selection("ALL", 4), [1, 2, 3, 4])

    def test_parse_soundbite_selection_invalid(self):
        """Errori su valori non validi per soundbite"""
        with self.assertRaises(ValueError):
            cli.parse_soundbite_selection(0, 3)
        with self.assertRaises(ValueError):
            cli.parse_soundbite_selection("0", 3)
        with self.assertRaises(ValueError):
            cli.parse_soundbite_selection("x,y", 3)
        with self.assertRaises(ValueError):
            cli.parse_soundbite_selection("", 3)


if __name__ == "__main__":
    unittest.main()
