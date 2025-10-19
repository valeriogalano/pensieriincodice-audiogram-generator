# Pensieri in Codice - Audiogram Generator

Generatore automatico di audiogrammi per il podcast Pensieri in Codice. Il tool scarica episodi dal feed RSS del podcast, estrae i soundbites con le relative trascrizioni, e genera video audiogrammi ottimizzati per tutte le principali piattaforme social.

## Caratteristiche

- **Parsing automatico del feed RSS** del podcast con estrazione di:
  - Informazioni episodi (titolo, descrizione, audio)
  - Soundbites con timing preciso
  - Trascrizioni sincronizzate (formato SRT)
  - Locandina del podcast

- **Generazione audiogrammi** in tre formati ottimizzati per social media:
  - **Verticale 9:16** (1080x1920) - Instagram Reels/Stories, YouTube Shorts, TikTok
  - **Quadrato 1:1** (1080x1080) - Instagram Post, Twitter/X, Mastodon, LinkedIn
  - **Orizzontale 16:9** (1920x1080) - YouTube, Twitter/X orizzontale

- **Trascrizione in tempo reale** sincronizzata con l'audio
- **Waveform animata** che progredisce con l'audio
- **Layout personalizzato** con colori e branding del podcast
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
1. Visualizzazione delle informazioni del podcast (titolo e locandina)
2. Elenco di tutti gli episodi disponibili (dal primo all'ultimo)
3. Selezione dell'episodio desiderato
4. Visualizzazione dei soundbites disponibili con le relative trascrizioni
5. Selezione del soundbite da convertire
6. Generazione automatica di tre video audiogrammi in formati diversi

I video generati vengono salvati nella directory `output/` con naming:
```
ep{numero_episodio}_sb{numero_soundbite}_{formato}.mp4
```

Esempio:
- `ep142_sb1_vertical.mp4` - Per Reels, Stories, Shorts, TikTok
- `ep142_sb1_square.mp4` - Per post Instagram, Twitter, Mastodon
- `ep142_sb1_horizontal.mp4` - Per YouTube

## Dipendenze principali

- **feedparser** (≥6.0.10) - Parsing del feed RSS
- **moviepy** (≥1.0.3) - Generazione e compositing video
- **pillow** (≥10.0.0) - Elaborazione immagini e rendering frame
- **pydub** (≥0.25.1) - Elaborazione e manipolazione audio
- **numpy** (≥1.24.0) - Calcoli numerici per forme d'onda
- **requests** (≥2.31.0) - Download risorse remote

## Struttura audiogram

Ogni video generato include:
- **Header arancione** con testo "ASCOLTA" e icone audio
- **Area centrale** con:
  - Locandina del podcast
  - Waveform animata ai lati sincronizzata con l'audio
- **Trascrizione in tempo reale** nella parte bassa dell'area centrale
- **Footer arancione** con:
  - Titolo del podcast ("Pensieri in codice")
  - Titolo dell'episodio/soundbite

## Licenza

Vedi il file [LICENSE](LICENSE) per i dettagli.
