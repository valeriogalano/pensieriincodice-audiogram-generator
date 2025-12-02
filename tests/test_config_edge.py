"""
Test aggiuntivi per Config: precedenza CLI>YAML>default, deep-merge e casi bordo.
"""
import tempfile
import os
import unittest
import yaml

from audiogram_generator.config import Config


class TestConfigEdge(unittest.TestCase):
    """Casi bordo su caricamento e merge configurazione"""

    def test_update_from_args_does_not_override_with_none(self):
        # YAML iniziale
        with tempfile.NamedTemporaryFile('w+', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'feed_url': 'https://example.com/feed.xml',
                            'output_dir': './from_yaml'}, f)
            path = f.name
        try:
            cfg = Config(path)
            # Applica args dove uno è None → non deve sovrascrivere
            cfg.update_from_args({'feed_url': None, 'output_dir': './from_args'})
            self.assertEqual(cfg.get('feed_url'), 'https://example.com/feed.xml')
            self.assertEqual(cfg.get('output_dir'), './from_args')
        finally:
            os.unlink(path)

    def test_deep_merge_formats_partial_override(self):
        # YAML che disabilita solo il formato square
        with tempfile.NamedTemporaryFile('w+', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'formats': {'square': {'enabled': False}}}, f)
            path = f.name
        try:
            cfg = Config(path)
            formats = cfg.get('formats')
            # width/height di square devono rimanere dai default
            self.assertIn('width', formats['square'])
            self.assertIn('height', formats['square'])
            self.assertIs(formats['square']['enabled'], False)
            # vertical non toccato, ancora enabled True per default
            self.assertIs(formats['vertical']['enabled'], True)
        finally:
            os.unlink(path)

    def test_unknown_keys_are_preserved(self):
        with tempfile.NamedTemporaryFile('w+', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'unknown_key': 123}, f)
            path = f.name
        try:
            cfg = Config(path)
            self.assertEqual(cfg.get('unknown_key'), 123)
        finally:
            os.unlink(path)

    def test_yaml_crlf_and_null_values(self):
        # Contenuto con CRLF e valori nulli
        content = 'feed_url: https://example.com\r\nepisode: null\r\n'
        with tempfile.NamedTemporaryFile('w+', suffix='.yaml', delete=False) as f:
            f.write(content)
            path = f.name
        try:
            cfg = Config(path)
            self.assertEqual(cfg.get('feed_url'), 'https://example.com')
            # Valore null rimane None e non rompe i default
            self.assertIsNone(cfg.get('episode'))
            self.assertEqual(cfg.get('output_dir'), './output')
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
