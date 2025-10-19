# Pensieri in Codice - Audiogram Generator

Generatore automatico di audiogrammi per il podcast Pensieri in Codice. Il tool scarica episodi dal feed RSS del podcast, estrae i soundbites con le relative trascrizioni, e genera video audiogrammi ottimizzati per diversi formati social (Instagram Reel, Post e Story).

## Caratteristiche

- **Parsing automatico del feed RSS** del podcast con estrazione di:
  - Informazioni episodi (titolo, descrizione, audio)
  - Soundbites con timing preciso
  - Trascrizioni sincronizzate (formato SRT)
  - Locandina del podcast

- **Generazione audiogrammi** in tre formati:
  - **Reel** (1080x1920) - Verticale per Instagram Reels
  - **Post** (1080x1080) - Quadrato per post Instagram
  - **Story** (1080x1920) - Verticale per Instagram Stories

- **Sincronizzazione automatica** tra audio e testo della trascrizione
- **Elaborazione audio** con estrazione precisa dei segmenti
- **Interfaccia CLI interattiva** per la selezione di episodi e soundbites

## Struttura del progetto

```
pensieriincodice-audiogram-generator/
├── audiogram_generator/        # Modulo principale
│   ├── __init__.py
│   ├── __main__.py            # Entry point
│   ├── cli.py                 # Interfaccia a riga di comando
│   ├── audio_utils.py         # Download ed estrazione audio
│   └── video_generator.py     # Generazione video audiogrammi
├── tests/                      # Test
│   ├── __init__.py
│   └── test_generator.py
├── output/                     # Directory di output video generati
├── requirements.txt            # Dipendenze Python
└── setup.py                    # Setup del progetto
```

## Requisiti

- Python >= 3.8
- FFmpeg (per l'elaborazione audio/video)

### Installazione FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install ffmpeg
```

**Windows:**
Scarica da [ffmpeg.org](https://ffmpeg.org/download.html)

## Installazione

1. Clona il repository:
```bash
git clone https://github.com/vgalano/pensieriincodice-audiogram-generator.git
cd pensieriincodice-audiogram-generator
```

2. Installa le dipendenze:
```bash
pip3 install -r requirements.txt
```

## Utilizzo

Avvia l'applicazione:
```bash
python3 -m audiogram_generator
```

Il tool ti guiderà attraverso:
1. Visualizzazione degli episodi disponibili
2. Selezione dell'episodio
3. Visualizzazione dei soundbites disponibili con le relative trascrizioni
4. Selezione del soundbite da convertire
5. Generazione automatica di tre video audiogrammi (reel, post, story)

I video generati vengono salvati nella directory `output/` con naming:
```
ep{numero_episodio}_sb{numero_soundbite}_{formato}.mp4
```

## Dipendenze principali

- **feedparser** - Parsing del feed RSS
- **moviepy** - Generazione e compositing video
- **pillow** - Elaborazione immagini
- **pydub** - Elaborazione audio
- **numpy** - Calcoli numerici per forme d'onda
- **requests** - Download risorse

## Licenza

Vedi il file [LICENSE](LICENSE) per i dettagli.
