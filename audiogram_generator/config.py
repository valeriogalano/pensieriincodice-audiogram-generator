"""
Modulo per la gestione della configurazione del generatore di audiogrammi
"""
import os
import yaml
from typing import Dict, Any, Optional


class Config:
    """Classe per gestire la configurazione dell'applicazione"""

    DEFAULT_CONFIG = {
        'feed_url': None,
        'output_dir': './output',
        'episode': None,
        'soundbites': None,
    }

    def __init__(self, config_file: Optional[str] = None):
        """
        Inizializza la configurazione

        Args:
            config_file: Path al file di configurazione YAML (opzionale)
        """
        self.config = self.DEFAULT_CONFIG.copy()

        if config_file and os.path.exists(config_file):
            self.load_from_file(config_file)

    def load_from_file(self, config_file: str) -> None:
        """
        Carica la configurazione da file YAML

        Args:
            config_file: Path al file di configurazione
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    self.config.update(file_config)
        except Exception as e:
            raise Exception(f"Errore nel caricamento del file di configurazione: {e}")

    def update_from_args(self, args: Dict[str, Any]) -> None:
        """
        Aggiorna la configurazione con argomenti da CLI
        Gli argomenti CLI hanno precedenza sul file di configurazione

        Args:
            args: Dizionario con gli argomenti da CLI
        """
        for key, value in args.items():
            if value is not None:
                self.config[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Ottiene un valore di configurazione

        Args:
            key: Chiave della configurazione
            default: Valore di default se la chiave non esiste

        Returns:
            Il valore della configurazione
        """
        return self.config.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """
        Ottiene tutta la configurazione

        Returns:
            Dizionario con tutta la configurazione
        """
        return self.config.copy()
