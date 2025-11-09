# Podcast Audiogram Generator

Automatic audiogram generator for podcasts. The tool downloads episodes from an RSS feed, extracts soundbites with their transcripts, and generates audiogram videos optimized for major social platforms.

## Features

- **Automatic RSS feed parsing** with extraction of:
  - Episode details (title, description, audio)
  - Soundbites with precise timing
  - Synchronized transcripts (SRT format)
  - Podcast cover art

- **Audiogram generation** in three formats optimized for social media:
  - **Vertical 9:16** (1080x1920) — Instagram Reels/Stories, YouTube Shorts, TikTok
  - **Square 1:1** (1080x1080) — Instagram Post, Twitter/X, Mastodon, LinkedIn
  - **Horizontal 16:9** (1920x1080) — YouTube, horizontal Twitter/X

- **Live transcript** synchronized with audio
- **Animated waveform** that progresses with the audio
- **Customizable layout** with podcast colors and branding
- **Audio processing** with precise segment extraction
- **Interactive CLI** for selecting episodes and soundbites
- **Dry-run mode** to preview start/end times and subtitles without generating files
- **Subtitles toggle**: enable/disable on-video subtitles via CLI or config

## Project structure

```
podcast-audiogram-generator/
├── audiogram_generator/        # Main module
│   ├── __init__.py
│   ├── __main__.py            # Entry point
│   ├── cli.py                 # Command-line interface
│   ├── config.py              # Configuration management
│   ├── audio_utils.py         # Audio download and extraction
│   └── video_generator.py     # Audiogram video generation
├── tests/                      # Tests
│   ├── __init__.py
│   ├── test_config.py         # Configuration module tests
│   └── test_generator.py      # Audiogram generator tests
├── output/                     # Output directory for generated videos
├── requirements.txt            # Python dependencies
└── setup.py                    # Project setup
```

## Requirements

- Python >= 3.8
- FFmpeg (for audio/video processing)

### FFmpeg installation

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/vgalano/podcast-audiogram-generator.git
cd podcast-audiogram-generator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Interactive mode

Launch the application without arguments for interactive mode:
```bash
python -m audiogram_generator
```

The tool will guide you through:
1. Showing podcast info (title and cover)
2. Listing all available episodes (from oldest to newest)
3. Selecting the desired episode(s)
4. Showing available soundbites with their transcripts
5. Selecting which soundbite(s) to convert (single, multiple, or all)
6. Automatically generating three audiogram videos in different formats

### Command-line mode

To automate the process, you can pass all parameters as arguments:

```bash
python -m audiogram_generator [options]
```

**Available options:**

- `--config PATH` — Path to the YAML configuration file
- `--feed-url URL` — URL of the podcast RSS feed (required if not set in the config file)
- `--episode EPISODES` — Episode(s) to process:
  - Specific number: `5`
  - Comma-separated list: `1,3,5`
  - All episodes: `all` or `a`
- `--soundbites CHOICE` — Soundbites to generate:
  - Specific number: `1`, `2`, `3`, etc.
  - Comma-separated list: `1,3,5`
  - All soundbites: `all` or `a`
- `--output-dir PATH` — Output directory for generated videos (default: `./output`)
- `--dry-run` — Print start/end time and subtitles for selected soundbites without generating files
- `--show-subtitles` — Force-enable on-video subtitles (overrides config)
- `--no-subtitles` — Disable on-video subtitles (overrides config)

**Precedence notes:**
Command-line arguments take precedence over the configuration file, which in turn takes precedence over default values.

**Examples:**

```bash
# Generate all soundbites for episode 142
python -m audiogram_generator --episode 142 --soundbites all

# Generate only soundbites 1 and 3 for episode 100
python -m audiogram_generator --episode 100 --soundbites 1,3

# Generate soundbite 2 for episode 50 into a custom directory
python -m audiogram_generator --episode 50 --soundbites 2 --output-dir ~/videos

# Use a custom RSS feed
python -m audiogram_generator --feed-url https://example.com/feed.xml --episode 5 --soundbites all

# Use a configuration file
python -m audiogram_generator --config config.yaml

# Use a configuration file and override some parameters
python -m audiogram_generator --config config.yaml --episode 150
```

### Dry-run mode

Preview soundbite details without generating any files. This is useful to verify timings and transcript content before producing videos.

- What it does:
  - Prints, for each selected soundbite, the start time, end time, and the aggregated subtitle text from the SRT transcript when available (falls back to the soundbite title if no transcript is found).
  - Does not download/generate audio/video files. It may download the transcript SRT to extract text.

- How to use from CLI:
  ```bash
  python -m audiogram_generator --config config.yaml --episode 142 --soundbites all --dry-run
  
  # Or without a config file
  python -m audiogram_generator --feed-url <RSS_URL> --episode 1 --soundbites 1,3 --dry-run
  ```

- Enable via config file (optional):
  ```yaml
  dry_run: true
  ```
  Note: CLI arguments take precedence over the configuration file.

- Expected output (example):
  ```
  Episode 142: <title>
  Audio: <url>
  
  Soundbites found (3):
  
  ============================================================
  Dry-run: print start/end time and subtitles
  ============================================================
  
  Soundbite 1
  - Start:    12.000s (00:00:12.000)
  - Duration: 15.500s (00:00:15.500)
  - End:      27.500s (00:00:27.500)
  - Subtitles:
  <text joined from SRT segments in range>
  ```

### Subtitles on/off

You can enable or disable on-video subtitles either via CLI flags or the YAML config.

- CLI flags (override config):
  - Disable subtitles:
    ```bash
    python -m audiogram_generator --no-subtitles
    ```
  - Enable subtitles explicitly (useful if YAML has them disabled):
    ```bash
    python -m audiogram_generator --show-subtitles
    ```

- YAML configuration:
  Add the `show_subtitles` key to your `config.yaml` (default is `true`):
  ```yaml
  show_subtitles: false
  ```

Note: Command-line flags always take precedence over the YAML configuration.

### Configuration file

You can create a YAML configuration file to define parameters permanently:

1. Copy the example file:
```bash
cp config.yaml.example config.yaml
```

2. Edit `config.yaml` with your parameters:
```yaml
# feed_url is REQUIRED
feed_url: https://pensieriincodice.it/podcast/index.xml
output_dir: ./output
episode: 142
soundbites: "all"
# Optional: preview timings and subtitles without generating files
dry_run: false
# Show or hide on-video subtitles (default: true)
show_subtitles: true

# Customize colors (optional)
colors:
  primary: [242, 101, 34]      # Orange
  background: [235, 213, 197]  # Beige
  text: [255, 255, 255]        # White
  transcript_bg: [0, 0, 0]     # Black

# Configure video formats (optional)
formats:
  vertical:
    width: 1080
    height: 1920
    enabled: true
  square:
    enabled: true
  horizontal:
    enabled: false  # Disable horizontal format
```

3. Use the configuration file:
```bash
python -m audiogram_generator --config config.yaml
```

#### Customizing colors and formats

The configuration file allows you to fully customize the appearance of the audiograms:

**Customizable colors:**
- `primary`: Color for header, footer, and waveform bars (default: orange)
- `background`: Background color for the central area (default: beige)
- `text`: Text color (default: white)
- `transcript_bg`: Background color for the transcript (default: black)

Colors are defined as RGB lists `[R, G, B]` with values 0–255.

**Configurable video formats:**

Each format can be:
- Customized in size (`width`, `height`)
- Enabled or disabled (`enabled: true/false`)
- Given a custom description

Available formats:
- `vertical`: 9:16 for Reels, Stories, Shorts, TikTok
- `square`: 1:1 for Instagram posts, Twitter/X, Mastodon
- `horizontal`: 16:9 for YouTube

**Custom hashtags:**

You can specify a list of additional hashtags in the configuration file:

```yaml
hashtags:
  - podcast
  - tech
  - development
  - programming
  - coding
```

Hashtags specified in the configuration file will be combined with keywords extracted from the RSS feed (both at the podcast and episode levels). Duplicate hashtags are automatically removed while preserving insertion order (first podcast keywords, then episode keywords, then config file hashtags).

### Output

Videos and caption files are saved in the specified directory (default: `output/`) with the following naming:

**Videos:**
```
ep{episode_number}_sb{soundbite_number}_{format}.mp4
```

**Social caption file:**
```
ep{episode_number}_sb{soundbite_number}_caption.txt
```

Example for soundbite 1 of episode 142:
- `ep142_sb1_vertical.mp4` — Vertical video for Reels, Stories, Shorts, TikTok
- `ep142_sb1_square.mp4` — Square video for Instagram, Twitter/X, Mastodon
- `ep142_sb1_horizontal.mp4` — Horizontal video for YouTube
- `ep142_sb1_caption.txt` — Caption file ready for social posting

#### Caption file

Each `_caption.txt` file contains:
- Episode title and number
- Soundbite title
- Full transcript text
- Link to the full episode
- Suggested hashtags (combination of feed keywords and configured hashtags)

You can copy the content directly to create your social posts.

## Main dependencies

- **feedparser** (≥6.0.10) — RSS feed parsing
- **moviepy** (≥1.0.3) — Video generation and compositing
- **pillow** (≥10.0.0) — Image processing and frame rendering
- **pydub** (≥0.25.1) — Audio processing and manipulation
- **numpy** (≥1.24.0) — Numerical calculations for waveforms
- **requests** (≥2.31.0) — Downloading remote resources
- **pyyaml** (≥6.0) — YAML configuration parsing

## Audiogram structure

Each generated video includes:
- **Orange header** with "LISTEN" text and audio icons
- **Central area** with:
  - Podcast cover art
  - Animated waveform on the sides synchronized with audio
- **Live transcript** at the bottom of the central area
- **Orange footer** with:
  - Podcast title
  - Episode/soundbite title

## Tests

The project includes a test suite to verify the correct functioning of components.

### Run tests

To run all tests:
```bash
python -m unittest discover tests
```

To run tests for a specific module:
```bash
# Configuration module tests
python -m unittest tests.test_config -v

# Audiogram generator tests
python -m unittest tests.test_generator -v
```

To run a single test:
```bash
python -m unittest tests.test_config.TestConfig.test_configuration_precedence -v
```

### Available tests

- **test_config.py** — 14 tests for the configuration module:
  - Loading from YAML file
  - CLI argument overrides
  - Default value handling
  - Configuration precedence (default < file < CLI)
  - Error handling and edge cases

- **test_generator.py** — Tests for the audiogram generator

## TODO

- [x] Improve audiogram layout proportions
- [x] Make audiogram graphics configurable
- [x] Allow configuration for multiple podcasts via config file
- [x] Implement test suite to verify configuration mechanisms
- [x] Translate documentation, comments, etc. into English
- [ ] Better document subtitles configuration capabilities
- [ ] Let user choose if use podcast cover or episode cover
- [ ] Postfix audiograms with no subtitles
- [ ] Update usage doc (this file)

## License

See the [LICENSE](LICENSE) file for details.
