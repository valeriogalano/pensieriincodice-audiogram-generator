"""
Test del flusso CLI in dry-run e verifica suffisso _nosubs nei nomi dei file (mock I/O).
"""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock

from audiogram_generator import cli


class TestCliFlow(unittest.TestCase):
    def _make_selected(self, with_soundbites=True, with_transcript=True, with_image=True):
        return {
            'number': 142,
            'title': 'Titolo episodio',
            'link': 'https://example/ep142',
            'description': 'desc',
            'soundbites': (
                [
                    {'start': 5, 'duration': 4, 'title': "SB1"},
                    {'start': 12, 'duration': 3, 'title': "SB2"},
                ] if with_soundbites else []
            ),
            'transcript_url': 'https://example/srt.srt' if with_transcript else None,
            'audio_url': 'https://example/audio.mp3',
            'keywords': 'ai, coding',
            'image_url': 'https://example/ep_cover.jpg' if with_image else None,
        }

    def test_dry_run_no_soundbites_prints_message(self):
        selected = self._make_selected(with_soundbites=False)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.process_one_episode(
                selected=selected,
                podcast_info={'image_url': 'https://example/podcast.jpg', 'title': 'Podcast'},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                formats_config=cli.Config.DEFAULT_CONFIG['formats'],
                config_hashtags=None,
                show_subtitles=True,
                output_dir='./output',
                soundbites_choice=None,
                dry_run=True,
                use_episode_cover=False,
            )
        out = buf.getvalue()
        self.assertIn("No soundbites available for this episode.", out)

    @patch('audiogram_generator.cli.get_transcript_text', return_value=None)
    def test_dry_run_fallback_to_soundbite_title_when_no_transcript(self, _):
        selected = self._make_selected(with_soundbites=True, with_transcript=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.process_one_episode(
                selected=selected,
                podcast_info={'image_url': 'https://example/podcast.jpg', 'title': 'Podcast'},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                formats_config=cli.Config.DEFAULT_CONFIG['formats'],
                config_hashtags=None,
                show_subtitles=True,
                output_dir='./output',
                soundbites_choice='1',
                dry_run=True,
                use_episode_cover=False,
            )
        out = buf.getvalue()
        # Deve stampare il titolo della SB come fallback (quando transcript=None)
        self.assertIn('SB1', out)
        # Deve stampare anche i tempi formattati
        self.assertIn('00:00:05', out)

    def test_dry_run_invalid_selection_prints_error(self):
        selected = self._make_selected(with_soundbites=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.process_one_episode(
                selected=selected,
                podcast_info={'image_url': 'https://example/podcast.jpg', 'title': 'Podcast'},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                formats_config=cli.Config.DEFAULT_CONFIG['formats'],
                config_hashtags=None,
                show_subtitles=True,
                output_dir='./output',
                soundbites_choice='0',  # non valido
                dry_run=True,
                use_episode_cover=False,
            )
        out = buf.getvalue()
        self.assertIn('Soundbite selection error', out)

    @patch('audiogram_generator.cli.generate_audiogram')
    @patch('audiogram_generator.cli.download_image', return_value='/tmp/cover.jpg')
    @patch('audiogram_generator.cli.extract_audio_segment', return_value='/tmp/seg.mp3')
    @patch('audiogram_generator.cli.download_audio', return_value='/tmp/full.mp3')
    def test_output_filenames_include_nosubs_when_disabled(self, *_mocks):
        selected = self._make_selected(with_soundbites=True, with_transcript=False)
        formats = {
            'vertical': {'width': 1080, 'height': 1920, 'enabled': True},
            'square': {'width': 1080, 'height': 1080, 'enabled': True},
        }
        # Esegui non-dry-run ma con tutto mockato; intercetta le chiamate
        with patch('audiogram_generator.cli.generate_audiogram') as gen:
            cli.process_one_episode(
                selected=selected,
                podcast_info={'image_url': 'https://example/podcast.jpg', 'title': 'Podcast'},
                colors=cli.Config.DEFAULT_CONFIG['colors'],
                formats_config=formats,
                config_hashtags=None,
                show_subtitles=False,  # disabilitati → _nosubs
                output_dir='./output',
                soundbites_choice='1',
                dry_run=False,
                use_episode_cover=True,
            )
            # Verifica che ogni chiamata a generate_audiogram usi un path con _nosubs
            self.assertGreaterEqual(gen.call_count, 1)
            for call in gen.call_args_list:
                args, kwargs = call
                # output_path è il secondo argomento posizionale
                output_path = args[1] if len(args) >= 2 else kwargs.get('output_path')
                self.assertIn('_nosubs', output_path)


if __name__ == '__main__':
    unittest.main()
