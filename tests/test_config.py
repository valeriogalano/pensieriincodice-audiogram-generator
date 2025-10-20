"""
Test per il modulo di configurazione
"""
import unittest
import tempfile
import os
import yaml
from audiogram_generator.config import Config


class TestConfig(unittest.TestCase):
    """Test per la classe Config"""

    def test_default_configuration(self):
        """Test che i valori di default siano correttamente impostati"""
        config = Config()

        self.assertIsNone(config.get('feed_url'))
        self.assertEqual(config.get('output_dir'), './output')
        self.assertIsNone(config.get('episode'))
        self.assertIsNone(config.get('soundbites'))

    def test_get_with_default_value(self):
        """Test del metodo get con valore di default"""
        config = Config()

        # Chiave esistente
        self.assertEqual(config.get('output_dir'), './output')

        # Chiave non esistente con default
        self.assertEqual(config.get('non_existent_key', 'default_value'), 'default_value')

        # Chiave non esistente senza default
        self.assertIsNone(config.get('non_existent_key'))

    def test_get_all_configuration(self):
        """Test del metodo get_all"""
        config = Config()
        all_config = config.get_all()

        self.assertIsInstance(all_config, dict)
        self.assertIn('feed_url', all_config)
        self.assertIn('output_dir', all_config)
        self.assertIn('episode', all_config)
        self.assertIn('soundbites', all_config)

    def test_load_from_valid_yaml_file(self):
        """Test caricamento configurazione da file YAML valido"""
        # Crea un file temporaneo con configurazione
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = {
                'feed_url': 'https://example.com/feed.xml',
                'output_dir': './custom_output',
                'episode': 42,
                'soundbites': 'all'
            }
            yaml.dump(yaml_content, f)
            temp_file = f.name

        try:
            config = Config(config_file=temp_file)

            self.assertEqual(config.get('feed_url'), 'https://example.com/feed.xml')
            self.assertEqual(config.get('output_dir'), './custom_output')
            self.assertEqual(config.get('episode'), 42)
            self.assertEqual(config.get('soundbites'), 'all')
        finally:
            os.unlink(temp_file)

    def test_load_from_partial_yaml_file(self):
        """Test caricamento configurazione parziale da file YAML"""
        # Crea un file temporaneo con configurazione parziale
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = {
                'feed_url': 'https://example.com/feed.xml',
                'episode': 100
            }
            yaml.dump(yaml_content, f)
            temp_file = f.name

        try:
            config = Config(config_file=temp_file)

            # Valori dal file
            self.assertEqual(config.get('feed_url'), 'https://example.com/feed.xml')
            self.assertEqual(config.get('episode'), 100)

            # Valori di default non sovrascritti
            self.assertEqual(config.get('output_dir'), './output')
            self.assertIsNone(config.get('soundbites'))
        finally:
            os.unlink(temp_file)

    def test_load_from_nonexistent_file(self):
        """Test che il caricamento di un file inesistente non sollevi eccezioni"""
        # Il file non esiste, ma non dovrebbe sollevare eccezioni
        config = Config(config_file='/path/to/nonexistent/file.yaml')

        # Dovrebbe usare i valori di default
        self.assertIsNone(config.get('feed_url'))
        self.assertEqual(config.get('output_dir'), './output')

    def test_load_from_invalid_yaml_file(self):
        """Test gestione errori con file YAML non valido"""
        # Crea un file temporaneo con contenuto non valido
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_file = f.name

        try:
            with self.assertRaises(Exception) as context:
                Config(config_file=temp_file)

            self.assertIn("Errore nel caricamento del file di configurazione", str(context.exception))
        finally:
            os.unlink(temp_file)

    def test_load_from_empty_yaml_file(self):
        """Test caricamento da file YAML vuoto"""
        # Crea un file temporaneo vuoto
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_file = f.name

        try:
            config = Config(config_file=temp_file)

            # Dovrebbe usare i valori di default
            self.assertIsNone(config.get('feed_url'))
            self.assertEqual(config.get('output_dir'), './output')
        finally:
            os.unlink(temp_file)

    def test_update_from_args(self):
        """Test aggiornamento configurazione da argomenti CLI"""
        config = Config()

        # Aggiorna con argomenti CLI
        config.update_from_args({
            'feed_url': 'https://cli.example.com/feed.xml',
            'episode': 123,
            'output_dir': './cli_output'
        })

        self.assertEqual(config.get('feed_url'), 'https://cli.example.com/feed.xml')
        self.assertEqual(config.get('episode'), 123)
        self.assertEqual(config.get('output_dir'), './cli_output')

    def test_update_from_args_with_none_values(self):
        """Test che valori None da CLI non sovrascrivano la configurazione"""
        # Crea configurazione con file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = {
                'feed_url': 'https://example.com/feed.xml',
                'episode': 42
            }
            yaml.dump(yaml_content, f)
            temp_file = f.name

        try:
            config = Config(config_file=temp_file)

            # Aggiorna con argomenti CLI (alcuni None)
            config.update_from_args({
                'feed_url': None,
                'episode': 100,
                'output_dir': None
            })

            # feed_url dovrebbe rimanere quello del file (None non sovrascrive)
            self.assertEqual(config.get('feed_url'), 'https://example.com/feed.xml')

            # episode dovrebbe essere aggiornato
            self.assertEqual(config.get('episode'), 100)

            # output_dir dovrebbe rimanere il default
            self.assertEqual(config.get('output_dir'), './output')
        finally:
            os.unlink(temp_file)

    def test_configuration_precedence(self):
        """Test della precedenza: default < file < CLI"""
        # Crea un file di configurazione
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = {
                'feed_url': 'https://file.example.com/feed.xml',
                'output_dir': './file_output',
                'episode': 50
            }
            yaml.dump(yaml_content, f)
            temp_file = f.name

        try:
            # Carica configurazione da file
            config = Config(config_file=temp_file)

            # Valori dal file dovrebbero sovrascrivere i default
            self.assertEqual(config.get('feed_url'), 'https://file.example.com/feed.xml')
            self.assertEqual(config.get('output_dir'), './file_output')
            self.assertEqual(config.get('episode'), 50)
            self.assertIsNone(config.get('soundbites'))  # default

            # Aggiorna con argomenti CLI
            config.update_from_args({
                'feed_url': 'https://cli.example.com/feed.xml',
                'episode': 100,
                'soundbites': 'all'
            })

            # Valori CLI dovrebbero sovrascrivere quelli del file
            self.assertEqual(config.get('feed_url'), 'https://cli.example.com/feed.xml')
            self.assertEqual(config.get('episode'), 100)
            self.assertEqual(config.get('soundbites'), 'all')

            # output_dir dovrebbe rimanere quello del file (non specificato in CLI)
            self.assertEqual(config.get('output_dir'), './file_output')
        finally:
            os.unlink(temp_file)

    def test_yaml_with_null_values(self):
        """Test caricamento YAML con valori null/None"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = {
                'feed_url': 'https://example.com/feed.xml',
                'episode': None,
                'soundbites': None
            }
            yaml.dump(yaml_content, f)
            temp_file = f.name

        try:
            config = Config(config_file=temp_file)

            self.assertEqual(config.get('feed_url'), 'https://example.com/feed.xml')
            self.assertIsNone(config.get('episode'))
            self.assertIsNone(config.get('soundbites'))
        finally:
            os.unlink(temp_file)

    def test_yaml_with_additional_keys(self):
        """Test che chiavi aggiuntive nel YAML siano accettate"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = {
                'feed_url': 'https://example.com/feed.xml',
                'custom_key': 'custom_value',
                'another_key': 123
            }
            yaml.dump(yaml_content, f)
            temp_file = f.name

        try:
            config = Config(config_file=temp_file)

            self.assertEqual(config.get('feed_url'), 'https://example.com/feed.xml')
            self.assertEqual(config.get('custom_key'), 'custom_value')
            self.assertEqual(config.get('another_key'), 123)
        finally:
            os.unlink(temp_file)

    def test_config_immutability_via_get_all(self):
        """Test che get_all restituisca una copia e non modifichi l'originale"""
        config = Config()

        # Ottieni una copia della configurazione
        config_copy = config.get_all()

        # Modifica la copia
        config_copy['feed_url'] = 'https://modified.com/feed.xml'
        config_copy['new_key'] = 'new_value'

        # Verifica che l'originale non sia stato modificato
        self.assertIsNone(config.get('feed_url'))
        self.assertIsNone(config.get('new_key'))


if __name__ == "__main__":
    unittest.main()
