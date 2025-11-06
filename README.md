# Podcast Audiogram Generator

Generatore automatico di audiogrammi per podcast. Il tool scarica episodi dal feed RSS, estrae i soundbites con le relative trascrizioni, e genera video audiogrammi ottimizzati per tutte le principali piattaforme social.

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
podcast-audiogram-generator/
├── audiogram_generator/        # Modulo principale
│   ├── __init__.py
│   ├── __main__.py            # Entry point
│   ├── cli.py                 # Interfaccia a riga di comando
│   ├── config.py              # Gestione configurazione
│   ├── audio_utils.py         # Download ed estrazione audio
│   └── video_generator.py     # Generazione video audiogrammi
├── tests/                      # Test
│   ├── __init__.py
│   ├── test_config.py         # Test modulo configurazione
│   └── test_generator.py      # Test generatore audiogrammi
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
git clone https://github.com/vgalano/podcast-audiogram-generator.git
cd podcast-audiogram-generator
```

2. Installa le dipendenze:
```bash
pip3 install -r requirements.txt
```

## Utilizzo

### Modalità interattiva

Avvia l'applicazione senza argomenti per la modalità interattiva:
```bash
python3 -m audiogram_generator
```

Il tool ti guiderà attraverso:
1. Visualizzazione delle informazioni del podcast (titolo e locandina)
2. Elenco di tutti gli episodi disponibili (dal primo all'ultimo)
3. Selezione dell'episodio desiderato
4. Visualizzazione dei soundbites disponibili con le relative trascrizioni
5. Selezione del soundbite da convertire (singolo, multiplo o tutti)
6. Generazione automatica di tre video audiogrammi in formati diversi

### Modalità riga di comando

Per automatizzare il processo, è possibile specificare tutti i parametri tramite argomenti:

```bash
python3 -m audiogram_generator [opzioni]
```

**Opzioni disponibili:**

- `--config PATH` - Path al file di configurazione YAML
- `--feed-url URL` - URL del feed RSS del podcast (obbligatorio se non specificato nel file di configurazione)
- `--episode EPISODI` - Episodio/i da processare:
  - Numero specifico: `5`
  - Lista separata da virgola: `1,3,5`
  - Tutti gli episodi: `all` o `a`
- `--soundbites SCELTA` - Soundbites da generare:
  - Numero specifico: `1`, `2`, `3`, ecc.
  - Lista separata da virgola: `1,3,5`
  - Tutti i soundbites: `all` o `a`
- `--output-dir PATH` - Directory di output per i video generati (default: `./output`)

**Note sulla precedenza:**
Gli argomenti da riga di comando hanno precedenza sul file di configurazione, che a sua volta ha precedenza sui valori di default.

**Esempi:**

```bash
# Genera tutti i soundbites dell'episodio 142
python3 -m audiogram_generator --episode 142 --soundbites all

# Genera solo i soundbites 1 e 3 dell'episodio 100
python3 -m audiogram_generator --episode 100 --soundbites 1,3

# Genera il soundbite 2 dell'episodio 50 in una directory custom
python3 -m audiogram_generator --episode 50 --soundbites 2 --output-dir ~/videos

# Usa un feed RSS personalizzato
python3 -m audiogram_generator --feed-url https://esempio.com/feed.xml --episode 5 --soundbites all

# Usa un file di configurazione
python3 -m audiogram_generator --config config.yaml

# Usa un file di configurazione e sovrascrivi alcuni parametri
python3 -m audiogram_generator --config config.yaml --episode 150
```

### File di configurazione

È possibile creare un file di configurazione YAML per definire i parametri in modo permanente:

1. Copia il file di esempio:
```bash
cp config.yaml.example config.yaml
```

2. Modifica il file `config.yaml` con i tuoi parametri:
```yaml
# feed_url è OBBLIGATORIO
feed_url: https://pensieriincodice.it/podcast/index.xml
output_dir: ./output
episode: 142
soundbites: "all"

# Personalizza i colori (opzionale)
colors:
  primary: [242, 101, 34]      # Arancione
  background: [235, 213, 197]  # Beige
  text: [255, 255, 255]        # Bianco
  transcript_bg: [0, 0, 0]     # Nero

# Configura i formati video (opzionale)
formats:
  vertical:
    width: 1080
    height: 1920
    enabled: true
  square:
    enabled: true
  horizontal:
    enabled: false  # Disabilita formato orizzontale
```

3. Usa il file di configurazione:
```bash
python3 -m audiogram_generator --config config.yaml
```

#### Personalizzazione colori e formati

Il file di configurazione permette di personalizzare completamente l'aspetto degli audiogrammi:

**Colori personalizzabili:**
- `primary`: Colore per header, footer e barre waveform (default: arancione)
- `background`: Colore di sfondo dell'area centrale (default: beige)
- `text`: Colore del testo (default: bianco)
- `transcript_bg`: Colore di sfondo della trascrizione (default: nero)

I colori sono specificati come liste RGB `[R, G, B]` con valori 0-255.

**Formati video configurabili:**

Ogni formato può essere:
- Personalizzato nelle dimensioni (`width`, `height`)
- Abilitato o disabilitato (`enabled: true/false`)
- Dotato di una descrizione personalizzata

Formati disponibili:
- `vertical`: 9:16 per Reels, Stories, Shorts, TikTok
- `square`: 1:1 per Post Instagram, Twitter, Mastodon
- `horizontal`: 16:9 per YouTube

**Hashtag personalizzabili:**

È possibile specificare una lista di hashtag aggiuntivi nel file di configurazione:

```yaml
hashtags:
  - podcast
  - tech
  - sviluppo
  - programmazione
  - coding
```

Gli hashtag specificati nel file di configurazione verranno combinati con le keywords estratte dal feed RSS (sia a livello di podcast che di episodio). Gli hashtag duplicati vengono automaticamente rimossi, preservando l'ordine di inserimento (prima keywords del podcast, poi keywords dell'episodio, infine hashtag dal file di configurazione).

### Output

I video e i file caption generati vengono salvati nella directory specificata (default: `output/`) con naming:

**Video:**
```
ep{numero_episodio}_sb{numero_soundbite}_{formato}.mp4
```

**Caption per social media:**
```
ep{numero_episodio}_sb{numero_soundbite}_caption.md
```

Esempio per il soundbite 1 dell'episodio 142:
- `ep142_sb1_vertical.mp4` - Video verticale per Reels, Stories, Shorts, TikTok
- `ep142_sb1_square.mp4` - Video quadrato per post Instagram, Twitter, Mastodon
- `ep142_sb1_horizontal.mp4` - Video orizzontale per YouTube
- `ep142_sb1_caption.md` - File con caption pronta per il post social

#### File caption

Ogni file `_caption.md` contiene:
- Titolo e numero dell'episodio
- Titolo del soundbite
- Testo completo della trascrizione
- Link all'episodio completo
- Hashtag suggeriti (combinazione di keywords dal feed RSS e hashtag configurati)

Puoi copiare il contenuto direttamente per creare i tuoi post sui social media.

## Dipendenze principali

- **feedparser** (≥6.0.10) - Parsing del feed RSS
- **moviepy** (≥1.0.3) - Generazione e compositing video
- **pillow** (≥10.0.0) - Elaborazione immagini e rendering frame
- **pydub** (≥0.25.1) - Elaborazione e manipolazione audio
- **numpy** (≥1.24.0) - Calcoli numerici per forme d'onda
- **requests** (≥2.31.0) - Download risorse remote
- **pyyaml** (≥6.0) - Parsing file di configurazione YAML

## Struttura audiogram

Ogni video generato include:
- **Header arancione** con testo "ASCOLTA" e icone audio
- **Area centrale** con:
  - Locandina del podcast
  - Waveform animata ai lati sincronizzata con l'audio
- **Trascrizione in tempo reale** nella parte bassa dell'area centrale
- **Footer arancione** con:
  - Titolo del podcast
  - Titolo dell'episodio/soundbite

## Test

Il progetto include una suite di test per verificare il corretto funzionamento dei componenti.

### Eseguire i test

Per eseguire tutti i test:
```bash
python3 -m unittest discover tests
```

Per eseguire i test di un modulo specifico:
```bash
# Test del modulo di configurazione
python3 -m unittest tests.test_config -v

# Test del generatore di audiogrammi
python3 -m unittest tests.test_generator -v
```

Per eseguire un singolo test:
```bash
python3 -m unittest tests.test_config.TestConfig.test_configuration_precedence -v
```

### Test disponibili

- **test_config.py** - 14 test per il modulo di configurazione:
  - Caricamento da file YAML
  - Override da argomenti CLI
  - Gestione valori di default
  - Precedenza configurazione (default < file < CLI)
  - Gestione errori e casi limite

- **test_generator.py** - Test per il generatore di audiogrammi

## TODO

- [ ] Migliorare le proporzioni della grafica degli audiogrammi
- [x] Rendere configurabile la grafica degli audiogrammi
- [ ] Aggiungere la possibilità di estrarre soundbite utilizzando IA
- [ ] Aggiungere la trascrizione tramite IA se non presente nel feed
- [x] Permettere la configurazione per più podcast tramite file di configurazione
- [x] Implementare batteria di test per verificare che i meccanismi di configurazione funzionino correttamente 
- [ ] Tradurre documentazione, commenti, ecc. in inglese

## Licenza

Vedi il file [LICENSE](LICENSE) per i dettagli.
