# Pensieri in Codice - Audiogram Generator

Generatore di audiogrammi per il podcast Pensieri in Codice.

## Struttura del progetto

```
pensieriincodice-audiogram-generator/
├── audiogram_generator/    # Modulo principale
│   ├── __init__.py
│   ├── generator.py         # Logica di generazione audiogramma
│   ├── audio.py             # Gestione audio
│   └── video.py             # Generazione video
├── tests/                   # Test
├── docs/                    # Documentazione
├── requirements.txt         # Dipendenze
└── setup.py                 # Setup del progetto
```

## Installazione

```bash
pip3 install -r requirements.txt
```

## Utilizzo

```bash
python3 -m audiogram_generator
```
