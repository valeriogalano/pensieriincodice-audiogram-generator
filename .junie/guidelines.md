# Project Development Guidelines

This document captures project-specific knowledge to speed up future development and debugging of the Audiogram Generator.

## Build and Configuration

- Python: 3.8+
- System dependency: FFmpeg must be installed and on PATH (moviepy/pydub rely on it).
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - Windows: download from ffmpeg.org and add to PATH

Recommended setup steps:
- Create a virtualenv and install deps:
  - `python3 -m venv .venv && source .venv/bin/activate`
  - `python -m pip install -U pip`
  - `pip install -r requirements.txt`

Configuration sources and precedence:
- Precedence: CLI flags > YAML config file > hardcoded defaults in `audiogram_generator.config.Config.DEFAULT_CONFIG`.
- Example base config: copy `config.yaml.example` to `config.yaml` and edit.
- Deep-merge behavior: nested structures for `colors` and `formats` are deep-merged when loaded from YAML. Non-dict keys overwrite normally. See `Config._deep_merge`.

Notable config keys (defaults visible in code):
- `feed_url`: RSS feed URL (required unless provided via CLI)
- `output_dir`: output folder, default `./output`
- `episode`: single number, list-like string, or `all`
- `soundbites`: single number, list-like string, or `all`
- `dry_run`: if true, no media is rendered (useful when FFmpeg is unavailable)
- `show_subtitles`: global show/hide toggle; CLI can force with `--show-subtitles/--no-subtitles`
- `colors`: RGB triplets for primary/background/text/transcript_bg
- `formats`: three presets: `vertical`, `square`, `horizontal`, each with `width`, `height`, `enabled`, and `description`

Entry points:
- Interactive: `python -m audiogram_generator`
- Command-line mode: `python -m audiogram_generator [options]` (see `README.md` for examples and the full set of flags)

Network and external I/O:
- The CLI pulls podcast metadata and media via HTTP(S) from the RSS `feed_url`. Ensure network availability and handle rate limits if automating bulk runs.
- Transcript handling attempts to fetch SRTs when present in the feed; otherwise it falls back to soundbite titles.

FFmpeg and runtime notes:
- Rendering uses moviepy/pydub; both need working FFmpeg. In constrained environments, use `--dry-run` to validate episode/soundbite selection and transcript extraction without rendering.

## Testing

The project uses Python’s `unittest` discovery. No pytest-specific features are used.

Run tests:
- Full suite: `python3 -m unittest -v`
- Single module: `python3 -m unittest -v tests.test_generator`
- Single test case: `python3 -m unittest -v tests.test_generator.TestCliModule`
- Single test method: `python3 -m unittest -v tests.test_generator.TestCliModule.test_parse_srt_time`

Add tests:
- Place test modules under `tests/` with names like `test_*.py`.
- Derive from `unittest.TestCase`.
- Prefer testing pure logic (e.g., `Config` and CLI helper functions) to avoid external I/O.
- For configuration tests, use `tempfile.NamedTemporaryFile` and `yaml.safe_dump` to create ephemeral YAML inputs. Avoid network access and FFmpeg-dependent flows in unit tests.

Verified demo (executed during guideline authoring):
- We created a minimal test to demonstrate adding and running tests, executed it, and then removed it to keep the repository clean.
- Demo command executed successfully:
  - `python3 -m unittest -v tests.test_demo_guidelines`
- Example content of the demo test (kept here for reference):
  ```python
  import unittest
  from audiogram_generator.config import Config

  class TestDemoGuidelines(unittest.TestCase):
      def test_default_output_dir(self):
          cfg = Config()
          self.assertEqual(cfg.get('output_dir'), './output')
  ```

Note: The above file is not committed to the repository; it served as a temporary demonstration of the workflow.

## Development Notes and Code Style

- Follow existing code style and patterns:
  - Modules use explicit functions; `config.py` is type-annotated and uses deep-merge for nested config.
  - Tests prefer clear, descriptive Italian docstrings; mirror existing style and naming.
  - Use RGB integer lists for color configs to stay consistent with current defaults.
- CLI helpers worth unit-testing without side effects:
  - `parse_srt_time` in `audiogram_generator/cli.py` (already covered)
  - Selection parsers: `parse_episode_selection` and `parse_soundbite_selection`
  - Formattingutils: `format_seconds`
- Avoid relying on external binaries/network in unit tests; isolate such behavior behind flags (e.g., `--dry-run`) or mock requests where appropriate.
- When introducing new config keys nested under `colors` or `formats`, ensure deep-merge semantics remain consistent. Update defaults in `Config.DEFAULT_CONFIG` and adjust tests to cover precedence and merging.

Troubleshooting tips:
- If rendering fails, confirm `ffmpeg -version` works and that the Python process can find FFmpeg on PATH.
- If YAML parsing raises errors, check indentation and scalar formats; the loader is `yaml.safe_load`.
- MoviePy may emit `ImageMagick`-related warnings on some platforms; current pipeline relies on FFmpeg via MoviePy, not on ImageMagick.
