"""
Command-line interface for the audiogram generator
"""
import feedparser
import ssl
import urllib.request
import xml.etree.ElementTree as ET
import re
import logging
import os
import tempfile
import argparse
import shutil
from typing import List
from .audio_utils import download_audio, extract_audio_segment
from .services.assets import download_image
from .rendering.facade import generate_audiogram
from .config import Config
from .core.captioning import build_caption_text
from .core import (
    parse_srt_time,
    format_seconds,
    parse_episode_selection,
    parse_soundbite_selection,
)
from .services import transcript as transcript_svc
from .services import rss as rss_svc


def get_podcast_episodes(feed_url):
    """Fetch the list of episodes from the RSS feed.

    Thin delegator to services.rss to keep backward compatibility while
    moving parsing/network logic into the service layer.
    """
    return rss_svc.get_podcast_episodes(feed_url)


## NOTE: pure helpers moved to audiogram_generator.core
## - parse_srt_time
## - format_seconds


def get_transcript_text(transcript_url, start_time, duration):
    """Scarica il file SRT e estrae il testo nel range temporale.

    Implementation delegates to services.transcript for fetching and parsing.
    """
    try:
        srt_content = transcript_svc.fetch_srt(transcript_url)
        return transcript_svc.get_transcript_text_from_srt(srt_content, start_time, duration)
    except Exception:
        return None


def get_transcript_chunks(transcript_url, start_time, duration):
    """Scarica il file SRT e restituisce chunk di testo con timing per il soundbite.

    Implementation delegates to services.transcript for fetching and parsing.
    """
    try:
        srt_content = transcript_svc.fetch_srt(transcript_url)
        return transcript_svc.parse_srt_to_chunks(srt_content, float(start_time), float(duration))
    except Exception:
        return []


def generate_caption_file(output_path, episode_number, episode_title, episode_link,
                          soundbite_title, transcript_text, podcast_keywords=None,
                          episode_keywords=None, config_hashtags=None):
    """
    Generate a plain-text .txt caption file for social posts (no markdown).

    This function delegates the pure string generation to
    ``core.captioning.build_caption_text`` and only performs file I/O here.
    """
    caption = build_caption_text(
        episode_number=episode_number,
        episode_title=episode_title,
        episode_link=episode_link,
        soundbite_title=soundbite_title,
        transcript_text=transcript_text,
        podcast_keywords=podcast_keywords,
        episode_keywords=episode_keywords,
        config_hashtags=config_hashtags,
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(caption)


## NOTE: selection parsers moved to audiogram_generator.core
## - parse_episode_selection
## - parse_soundbite_selection


def process_one_episode(selected, podcast_info, colors, formats_config, config_hashtags, show_subtitles, output_dir, soundbites_choice, dry_run=False, use_episode_cover=False):
    print(f"\nEpisode {selected['number']}: {selected['title']}")
    if selected['audio_url']:
        print(f"Audio: {selected['audio_url']}")

    # Scegli URL locandina da usare (episodio se richiesto e disponibile, altrimenti podcast)
    artwork_url = None
    if use_episode_cover and selected.get('image_url'):
        artwork_url = selected['image_url']
    else:
        artwork_url = podcast_info.get('image_url')

    # Dry-run mode: print intervals and subtitles only, then exit
    if dry_run:
        sbs = selected.get('soundbites') or []
        print(f"\nFound soundbites ({len(sbs)}):")
        if not sbs:
            print("No soundbites available for this episode.")
            return
        # Determina quali soundbite stampare
        try:
            nums = parse_soundbite_selection(soundbites_choice, len(sbs))
        except ValueError as e:
            print(f"Soundbite selection error: {e}")
            return
        print("\n" + "="*60)
        print("Dry-run: print start/end time and subtitle text")
        print("="*60)
        for idx in nums:
            sb = sbs[idx - 1]
            try:
                start_s = float(sb['start'])
                dur_s = float(sb['duration'])
            except Exception:
                print(f"Soundbite {idx}: invalid timing values (start={sb.get('start')}, duration={sb.get('duration')})")
                continue
            end_s = start_s + dur_s
            # Recupera testo trascrizione oppure fallback al titolo del soundbite
            transcript_text = None
            if selected.get('transcript_url'):
                transcript_text = get_transcript_text(
                    selected['transcript_url'],
                    sb['start'],
                    sb['duration']
                )
            text = (transcript_text or sb.get('text') or sb.get('title') or '').strip()

            print(f"\nSoundbite {idx}")
            print(f"- Start: {start_s:.3f}s ({format_seconds(start_s)})")
            print(f"- Duration: {dur_s:.3f}s ({format_seconds(dur_s)})")
            print(f"- End:   {end_s:.3f}s ({format_seconds(end_s)})")
            print(f"- Subtitle text:")
            print(text if text else "[Not available]")
        # Non generare nulla in dry-run
        return

    # Mostra soundbites se esistono
    if selected['soundbites']:
        print(f"\nFound soundbites ({len(selected['soundbites'])}):")
        for i, soundbite in enumerate(selected['soundbites'], 1):
            print(f"\n  {i}. [Start: {soundbite['start']}s, Duration: {soundbite['duration']}s]")
            print(f"     Title: {soundbite.get('text') or soundbite.get('title')}")

            # Estrai testo dalla trascrizione se disponibile
            if selected['transcript_url']:
                transcript_text = get_transcript_text(
                    selected['transcript_url'],
                    soundbite['start'],
                    soundbite['duration']
                )
                if transcript_text:
                    print(f"     Text: {transcript_text[:100]}..." if len(transcript_text) > 100 else f"     Text: {transcript_text}")
                else:
                    print(f"     Text: [Not available]")

        # Chiedi quale soundbite generare se non specificato
        print("\n" + "="*60)
        if soundbites_choice is None:
            choice = input("\nDo you want to generate an audiogram for a soundbite? (number, 'a' for all, or 'n' to exit): ")
        else:
            choice = str(soundbites_choice)

        if choice.lower() == 'a' or choice.lower() == 'all':
            # Generate all soundbites
            print(f"\nGenerating audiograms for all {len(selected['soundbites'])} soundbites...")

            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download full audio once
                print("\nDownloading audio...")
                full_audio_path = os.path.join(temp_dir, "full_audio.mp3")
                download_audio(selected['audio_url'], full_audio_path)

                # Download artwork once
                print("Downloading artwork...")
                logo_path = os.path.join(temp_dir, "logo.png")
                if artwork_url:
                    download_image(artwork_url, logo_path)

                # Create output directory
                os.makedirs(output_dir, exist_ok=True)

                # Process each soundbite
                for soundbite_num, soundbite in enumerate(selected['soundbites'], 1):
                    print(f"\n{'='*60}")
                    print(f"Soundbite {soundbite_num}/{len(selected['soundbites'])}: {soundbite.get('text') or soundbite.get('title')}")
                    print(f"{'='*60}")

                    # Extract audio segment
                    print("Extracting audio segment...")
                    segment_path = os.path.join(temp_dir, f"segment_{soundbite_num}.mp3")
                    extract_audio_segment(
                        full_audio_path,
                        soundbite['start'],
                        soundbite['duration'],
                        segment_path
                    )

                    # Build transcript chunks
                    print("Processing transcript...")
                    transcript_chunks = []
                    transcript_text = ""
                    if selected['transcript_url']:
                        transcript_chunks = get_transcript_chunks(
                            selected['transcript_url'],
                            soundbite['start'],
                            soundbite['duration']
                        )
                        # Estrai testo completo per caption
                        transcript_text = get_transcript_text(
                            selected['transcript_url'],
                            soundbite['start'],
                            soundbite['duration']
                        ) or (soundbite.get('text') or soundbite.get('title'))
                    else:
                        transcript_text = soundbite.get('text') or soundbite.get('title')

                    # Genera audiogram per ogni formato abilitato
                    formats_info = {}
                    for fmt_name, fmt_config in formats_config.items():
                        if fmt_config.get('enabled', True):
                            formats_info[fmt_name] = fmt_config.get('description', fmt_name)

                    for format_name, format_desc in formats_info.items():
                        print(f"Generating audiogram {format_desc}...")
                        # Add a suffix to filename if subtitles are disabled
                        nosubs_suffix = "_nosubs" if not show_subtitles else ""
                        output_path = os.path.join(
                            output_dir,
                            f"ep{selected['number']}_sb{soundbite_num}{nosubs_suffix}_{format_name}.mp4"
                        )

                        generate_audiogram(
                            segment_path,
                            output_path,
                            format_name,
                            logo_path,
                            podcast_info['title'],
                            selected['title'],
                            transcript_chunks,
                            float(soundbite['duration']),
                            formats_config,
                            colors,
                            show_subtitles
                        )

                        print(f"✓ {format_name}: {output_path}")

                    # Genera file caption .txt
                    print("Generazione file caption...")
                    caption_path = os.path.join(
                        output_dir,
                        f"ep{selected['number']}_sb{soundbite_num}_caption.txt"
                    )
                    generate_caption_file(
                        caption_path,
                        selected['number'],
                        selected['title'],
                        selected['link'],
                        soundbite.get('text') or soundbite.get('title') or '',
                        transcript_text,
                        podcast_info.get('keywords'),
                        selected.get('keywords'),
                        config_hashtags
                    )
                    print(f"✓ Caption: {caption_path}")

                print(f"\n{'='*60}")
                print(f"All audiograms generated successfully into the 'output' folder!")
                print(f"Total: {len(selected['soundbites'])} soundbites × {len(formats_info)} formats = {len(selected['soundbites']) * len(formats_info)} videos")
                print(f"{'='*60}")

        elif choice.lower() != 'n':
            try:
                # Supporta lista di numeri separati da virgola
                if ',' in choice:
                    soundbite_nums = [int(n.strip()) for n in choice.split(',')]
                else:
                    soundbite_nums = [int(choice)]

                # Valida tutti i numeri
                for num in soundbite_nums:
                    if not (1 <= num <= len(selected['soundbites'])):
                        print(f"Error: invalid number {num}. Choose between 1 and {len(selected['soundbites'])}")
                        return

                # Genera audiogram per i soundbites selezionati
                print(f"\nGenerating audiogram for {len(soundbite_nums)} soundbite(s)...")

                # Crea directory temporanea
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Scarica audio completo una sola volta
                    print("Downloading audio...")
                    full_audio_path = os.path.join(temp_dir, "full_audio.mp3")
                    download_audio(selected['audio_url'], full_audio_path)

                    # Scarica logo una sola volta
                    print("Downloading artwork...")
                    logo_path = os.path.join(temp_dir, "logo.png")
                    if artwork_url:
                        download_image(artwork_url, logo_path)

                    # Crea directory output
                    os.makedirs(output_dir, exist_ok=True)

                    # Processa ogni soundbite selezionato
                    for soundbite_num in soundbite_nums:
                        soundbite = selected['soundbites'][soundbite_num - 1]

                        print(f"\n{'='*60}")
                        print(f"Soundbite {soundbite_num}: {soundbite.get('text') or soundbite.get('title')}")
                        print(f"{'='*60}")

                        # Estrai segmento
                        print("Extracting audio segment...")
                        segment_path = os.path.join(temp_dir, f"segment_{soundbite_num}.mp3")
                        extract_audio_segment(
                            full_audio_path,
                            soundbite['start'],
                            soundbite['duration'],
                            segment_path
                        )

                        # Ottieni chunk trascrizione
                        print("Processing transcript...")
                        transcript_chunks = []
                        transcript_text = ""
                        if selected['transcript_url']:
                            transcript_chunks = get_transcript_chunks(
                                selected['transcript_url'],
                                soundbite['start'],
                                soundbite['duration']
                            )
                            # Estrai testo completo per caption
                            transcript_text = get_transcript_text(
                                selected['transcript_url'],
                                soundbite['start'],
                                soundbite['duration']
                            ) or (soundbite.get('text') or soundbite.get('title'))
                        else:
                            transcript_text = soundbite.get('text') or soundbite.get('title')

                        # Genera audiogram per ogni formato abilitato
                        formats_info = {}
                        for fmt_name, fmt_config in formats_config.items():
                            if fmt_config.get('enabled', True):
                                formats_info[fmt_name] = fmt_config.get('description', fmt_name)

                        for format_name, format_desc in formats_info.items():
                            print(f"Generating audiogram {format_desc}...")
                            # Add a suffix to filename if subtitles are disabled
                            nosubs_suffix = "_nosubs" if not show_subtitles else ""
                            output_path = os.path.join(
                                output_dir,
                                f"ep{selected['number']}_sb{soundbite_num}{nosubs_suffix}_{format_name}.mp4"
                            )

                            generate_audiogram(
                                segment_path,
                                output_path,
                                format_name,
                                logo_path,
                                podcast_info['title'],
                                selected['title'],
                                transcript_chunks,
                                float(soundbite['duration']),
                                formats_config,
                                colors,
                                show_subtitles
                            )

                            print(f"✓ {format_name}: {output_path}")

                        # Genera file caption .txt
                        print("Generating caption file...")
                        caption_path = os.path.join(
                            output_dir,
                            f"ep{selected['number']}_sb{soundbite_num}_caption.txt"
                        )
                        generate_caption_file(
                            caption_path,
                            selected['number'],
                            selected['title'],
                            selected['link'],
                            soundbite.get('text') or soundbite.get('title') or '',
                            transcript_text,
                            podcast_info.get('keywords'),
                            selected.get('keywords'),
                            config_hashtags
                        )
                        print(f"✓ Caption: {caption_path}")

                    print(f"\n{'='*60}")
                    print(f"Audiograms successfully generated in folder: {output_dir}")
                    print(f"{'='*60}")
            except ValueError:
                print("Invalid input")
            except Exception as e:
                print(f"Error during generation: {e}")
    else:
        print("\nNo soundbites found for this episode.")


def main():
    """Funzione principale CLI"""
    # Argument parsing
    # Minimal logging setup; services use logging for diagnostics.
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Audiogram generator from podcast RSS')
    parser.add_argument('--config', type=str, help='Path to the YAML configuration file')
    parser.add_argument('--feed-url', type=str, help='URL of the podcast RSS feed')
    parser.add_argument('--episode', type=str, help="Episode(s) to process: number (e.g., 5), list (e.g., 1,3,5), 'all'/'a' for all, or 'last' for the most recent episode")
    parser.add_argument('--soundbites', type=str, help='Soundbites to generate: specific number, "all" for all, or comma-separated list (e.g., 1,3,5)')
    parser.add_argument('--output-dir', type=str, help='Output directory for generated files')
    parser.add_argument('--dry-run', action='store_true', help='Stampa solo intervalli e sottotitoli dei soundbite senza generare file')
    # Sottotitoli on/off
    subs_group = parser.add_mutually_exclusive_group()
    subs_group.add_argument('--show-subtitles', dest='show_subtitles', action='store_true', help='Abilita la visualizzazione dei sottotitoli nel video')
    subs_group.add_argument('--no-subtitles', dest='show_subtitles', action='store_false', help='Disabilita la visualizzazione dei sottotitoli nel video')
    parser.set_defaults(show_subtitles=None)

    # Copertina episodio on/off
    cover_group = parser.add_mutually_exclusive_group()
    cover_group.add_argument('--use-episode-cover', dest='use_episode_cover', action='store_true', help="Usa la copertina specifica dell'episodio se disponibile")
    cover_group.add_argument('--no-use-episode-cover', dest='use_episode_cover', action='store_false', help="Non usare la copertina episodio, usa quella del podcast")
    parser.set_defaults(use_episode_cover=None)

    args = parser.parse_args()

    # Carica configurazione
    # Se non viene passato --config, prova a usare un file di default (config.yml o config.yaml)
    default_config_path = None
    if not args.config:
        # Cerca nella directory corrente
        cwd = os.getcwd()
        candidates = [
            os.path.join(cwd, 'config.yml'),
            os.path.join(cwd, 'config.yaml'),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                default_config_path = candidate
                break
    config = Config(config_file=args.config or default_config_path)

    # Aggiorna configurazione con argomenti CLI (hanno precedenza)
    config.update_from_args({
        'feed_url': args.feed_url,
        'episode': args.episode,
        'soundbites': args.soundbites,
        'output_dir': args.output_dir,
        'dry_run': args.dry_run,
        'show_subtitles': args.show_subtitles,
        'use_episode_cover': args.use_episode_cover
    })

    # Usa argomenti o richiedi input interattivo
    feed_url = config.get('feed_url')
    episode_input = config.get('episode')
    soundbites_choice = config.get('soundbites')
    output_dir = config.get('output_dir', os.path.join(os.getcwd(), 'output'))

    # Carica configurazione colori, formati, hashtags e CTA
    colors = config.get('colors')
    formats_config = config.get('formats')
    config_hashtags = config.get('hashtags', [])
    show_subtitles = config.get('show_subtitles', True)
    dry_run = config.get('dry_run', False)
    use_episode_cover = config.get('use_episode_cover', False)

    # Chiedi feed_url interattivamente se non specificato
    if feed_url is None:
        try:
            while True:
                user_input = input("\nEnter the podcast RSS feed URL: ").strip()
                if user_input:
                    feed_url = user_input
                    print(f"Usando feed: {feed_url}")
                    break
                else:
                    print("L'URL del feed non può essere vuoto. Riprova.")
        except KeyboardInterrupt:
            print("\nOperazione annullata.")
            return

    print("\nRecupero episodi dal feed...")
    episodes, podcast_info = get_podcast_episodes(feed_url)

    if not episodes:
        print("Nessun episodio trovato nel feed.")
        return

    # Mostra informazioni podcast
    print(f"\n{'='*60}")
    print(f"Podcast: {podcast_info.get('title', 'N/A')}")
    if podcast_info.get('image_url'):
        print(f"Locandina: {podcast_info['image_url']}")
    print(f"{'='*60}")

    # Mostra episodi dal primo all'ultimo
    print(f"\nTrovati {len(episodes)} episodi:\n")
    for episode in episodes:
        print(f"{episode['number']}. {episode['title']}")

    # Determina quali episodi processare (singolo, lista o tutti)
    max_episode = len(episodes)
    try:
        selected_episode_numbers = parse_episode_selection(episode_input, max_episode)
    except ValueError as e:
        print(f"Errore input episodio: {e}")
        return

    if not selected_episode_numbers:
        # Modalità interattiva
        while True:
            try:
                choice = input(f"\nSeleziona episodio: numero (es. 5), lista (es. 1,3,5), 'all'/'a' per tutti, oppure 'last' per l'ultimo: ").strip()
                try:
                    selected_episode_numbers = parse_episode_selection(choice, max_episode)
                    break
                except ValueError as e:
                    print(f"Input non valido: {e}")
            except KeyboardInterrupt:
                print("\nOperazione annullata.")
                return

    # Processa gli episodi selezionati
    for episode_num in selected_episode_numbers:
        selected = None
        for ep in episodes:
            if ep['number'] == episode_num:
                selected = ep
                break
        if selected is None:
            print(f"Episodio {episode_num} non trovato nel feed. Skip.")
            continue

        process_one_episode(
            selected=selected,
            podcast_info=podcast_info,
            colors=colors,
            formats_config=formats_config,
            config_hashtags=config_hashtags,
            show_subtitles=show_subtitles,
            output_dir=output_dir,
            soundbites_choice=soundbites_choice,
            dry_run=dry_run,
            use_episode_cover=use_episode_cover
        )

    return

    # Chiedi quale episodio scegliere se non specificato
    if episode_num is None:
        while True:
            try:
                choice = input(f"\nChoose the episode number (1-{len(episodes)}): ")
                episode_num = int(choice)
                if 1 <= episode_num <= len(episodes):
                    break
                print(f"Enter a number between 1 and {len(episodes)}")
            except ValueError:
                print("Enter a valid number")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return
    else:
        if not (1 <= episode_num <= len(episodes)):
            print(f"Error: episode number must be between 1 and {len(episodes)}")
            return

    # Trova l'episodio selezionato
    selected = None
    for ep in episodes:
        if ep['number'] == episode_num:
            selected = ep
            break

    print(f"\nEpisode {selected['number']}: {selected['title']}")
    if selected['audio_url']:
        print(f"Audio: {selected['audio_url']}")

    # Mostra soundbites se esistono
    if selected['soundbites']:
        print(f"\nFound soundbites ({len(selected['soundbites'])}):")
        for i, soundbite in enumerate(selected['soundbites'], 1):
            print(f"\n  {i}. [Start: {soundbite['start']}s, Duration: {soundbite['duration']}s]")
            print(f"     Title: {soundbite.get('text') or soundbite.get('title')}")

            # Estrai testo dalla trascrizione se disponibile
            if selected['transcript_url']:
                transcript_text = get_transcript_text(
                    selected['transcript_url'],
                    soundbite['start'],
                    soundbite['duration']
                )
                if transcript_text:
                    print(f"     Text: {transcript_text[:100]}..." if len(transcript_text) > 100 else f"     Text: {transcript_text}")
                else:
                    print(f"     Text: [Not available]")

        # Chiedi quale soundbite generare se non specificato
        print("\n" + "="*60)
        if soundbites_choice is None:
            choice = input("\nDo you want to generate an audiogram for a soundbite? (number, 'a' for all, or 'n' to exit): ")
        else:
            choice = str(soundbites_choice)

        if choice.lower() == 'a' or choice.lower() == 'all':
            # Genera tutti i soundbites
            print(f"\nGenerating audiograms for all {len(selected['soundbites'])} soundbites...")

            # Crea directory temporanea
            with tempfile.TemporaryDirectory() as temp_dir:
                # Scarica audio completo una sola volta
                print("\nDownloading audio...")
                full_audio_path = os.path.join(temp_dir, "full_audio.mp3")
                download_audio(selected['audio_url'], full_audio_path)

                # Scarica logo una sola volta
                print("Downloading artwork...")
                logo_path = os.path.join(temp_dir, "logo.png")
                if artwork_url:
                    download_image(artwork_url, logo_path)

                # Crea directory output
                os.makedirs(output_dir, exist_ok=True)

                # Process each soundbite
                for soundbite_num, soundbite in enumerate(selected['soundbites'], 1):
                    print(f"\n{'='*60}")
                    print(f"Soundbite {soundbite_num}/{len(selected['soundbites'])}: {soundbite.get('text') or soundbite.get('title')}")
                    print(f"{'='*60}")

                    # Extract segment
                    print("Extracting audio segment...")
                    segment_path = os.path.join(temp_dir, f"segment_{soundbite_num}.mp3")
                    extract_audio_segment(
                        full_audio_path,
                        soundbite['start'],
                        soundbite['duration'],
                        segment_path
                    )

                    # Build transcript chunks
                    print("Processing transcript...")
                    transcript_chunks = []
                    transcript_text = ""
                    if selected['transcript_url']:
                        transcript_chunks = get_transcript_chunks(
                            selected['transcript_url'],
                            soundbite['start'],
                            soundbite['duration']
                        )
                        # Extract full text for caption
                        transcript_text = get_transcript_text(
                            selected['transcript_url'],
                            soundbite['start'],
                            soundbite['duration']
                        ) or (soundbite.get('text') or soundbite.get('title'))
                    else:
                        transcript_text = soundbite.get('text') or soundbite.get('title')

                    # Genera audiogram per ogni formato abilitato
                    formats_info = {}
                    for fmt_name, fmt_config in formats_config.items():
                        if fmt_config.get('enabled', True):
                            formats_info[fmt_name] = fmt_config.get('description', fmt_name)

                    for format_name, format_desc in formats_info.items():
                        print(f"Generating audiogram {format_desc}...")
                        # Add a suffix to filename if subtitles are disabled
                        nosubs_suffix = "_nosubs" if not show_subtitles else ""
                        output_path = os.path.join(
                            output_dir,
                            f"ep{selected['number']}_sb{soundbite_num}{nosubs_suffix}_{format_name}.mp4"
                        )

                        generate_audiogram(
                            segment_path,
                            output_path,
                            format_name,
                            logo_path,
                            podcast_info['title'],
                            selected['title'],
                            transcript_chunks,
                            float(soundbite['duration']),
                            formats_config,
                            colors,
                            show_subtitles
                        )

                        print(f"✓ {format_name}: {output_path}")

                    # Genera file caption .txt
                    print("Generazione file caption...")
                    caption_path = os.path.join(
                        output_dir,
                        f"ep{selected['number']}_sb{soundbite_num}_caption.txt"
                    )
                    generate_caption_file(
                        caption_path,
                        selected['number'],
                        selected['title'],
                        selected['link'],
                        soundbite['text'],
                        transcript_text,
                        podcast_info.get('keywords'),
                        selected.get('keywords'),
                        config_hashtags
                    )
                    print(f"✓ Caption: {caption_path}")

                print(f"\n{'='*60}")
                print(f"Tutti gli audiogram generati con successo nella cartella 'output'!")
                print(f"Totale: {len(selected['soundbites'])} soundbites × {len(formats_info)} formati = {len(selected['soundbites']) * len(formats_info)} video")
                print(f"{'='*60}")

        elif choice.lower() != 'n':
            try:
                # Supporta lista di numeri separati da virgola
                if ',' in choice:
                    soundbite_nums = [int(n.strip()) for n in choice.split(',')]
                else:
                    soundbite_nums = [int(choice)]

                # Valida tutti i numeri
                for num in soundbite_nums:
                    if not (1 <= num <= len(selected['soundbites'])):
                        print(f"Errore: numero {num} non valido. Scegli tra 1 e {len(selected['soundbites'])}")
                        return

                # Genera audiogram per i soundbites selezionati
                print(f"\nGenerazione audiogram per {len(soundbite_nums)} soundbite(s)...")

                # Crea directory temporanea
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Scarica audio completo una sola volta
                    print("Download audio...")
                    full_audio_path = os.path.join(temp_dir, "full_audio.mp3")
                    download_audio(selected['audio_url'], full_audio_path)

                    # Scarica logo una sola volta
                    print("Download locandina...")
                    logo_path = os.path.join(temp_dir, "logo.png")
                    download_image(podcast_info['image_url'], logo_path)

                    # Crea directory output
                    os.makedirs(output_dir, exist_ok=True)

                    # Processa ogni soundbite selezionato
                    for soundbite_num in soundbite_nums:
                        soundbite = selected['soundbites'][soundbite_num - 1]

                        print(f"\n{'='*60}")
                        print(f"Soundbite {soundbite_num}: {soundbite['text']}")
                        print(f"{'='*60}")

                    # Scarica logo una sola volta
                    print("Download locandina...")
                    logo_path = os.path.join(temp_dir, "logo.png")
                    download_image(podcast_info['image_url'], logo_path)

                    # Crea directory output
                    os.makedirs(output_dir, exist_ok=True)

                    # Processa ogni soundbite selezionato
                    for soundbite_num in soundbite_nums:
                        soundbite = selected['soundbites'][soundbite_num - 1]

                        print(f"\n{'='*60}")
                        print(f"Soundbite {soundbite_num}: {soundbite['text']}")
                        print(f"{'='*60}")

                        # Estrai segmento
                        print("Estrazione segmento audio...")
                        segment_path = os.path.join(temp_dir, f"segment_{soundbite_num}.mp3")
                        extract_audio_segment(
                            full_audio_path,
                            soundbite['start'],
                            soundbite['duration'],
                            segment_path
                        )

                        # Ottieni chunk trascrizione
                        print("Elaborazione trascrizione...")
                        transcript_chunks = []
                        transcript_text = ""
                        if selected['transcript_url']:
                            transcript_chunks = get_transcript_chunks(
                                selected['transcript_url'],
                                soundbite['start'],
                                soundbite['duration']
                            )
                            # Estrai testo completo per caption
                            transcript_text = get_transcript_text(
                                selected['transcript_url'],
                                soundbite['start'],
                                soundbite['duration']
                            ) or soundbite['text']
                        else:
                            transcript_text = soundbite['text']

                        # Genera audiogram per ogni formato abilitato
                        formats_info = {}
                        for fmt_name, fmt_config in formats_config.items():
                            if fmt_config.get('enabled', True):
                                formats_info[fmt_name] = fmt_config.get('description', fmt_name)

                        for format_name, format_desc in formats_info.items():
                            print(f"Generazione audiogram {format_desc}...")
                            # Aggiunge un suffisso al nome file se i sottotitoli sono disabilitati
                            nosubs_suffix = "_nosubs" if not show_subtitles else ""
                            output_path = os.path.join(
                                output_dir,
                                f"ep{selected['number']}_sb{soundbite_num}{nosubs_suffix}_{format_name}.mp4"
                            )

                            generate_audiogram(
                                segment_path,
                                output_path,
                                format_name,
                                logo_path,
                                podcast_info['title'],
                                selected['title'],
                                transcript_chunks,
                                float(soundbite['duration']),
                                formats_config,
                                colors,
                                show_subtitles
                            )

                            print(f"✓ {format_name}: {output_path}")

                        # Genera file caption .txt
                        print("Generazione file caption...")
                        caption_path = os.path.join(
                            output_dir,
                            f"ep{selected['number']}_sb{soundbite_num}_caption.txt"
                        )
                        generate_caption_file(
                            caption_path,
                            selected['number'],
                            selected['title'],
                            selected['link'],
                            soundbite['text'],
                            transcript_text,
                            podcast_info.get('keywords'),
                            selected.get('keywords'),
                            config_hashtags
                        )
                        print(f"✓ Caption: {caption_path}")

                    print(f"\n{'='*60}")
                    print(f"Audiogram generati con successo nella cartella: {output_dir}")
                    print(f"{'='*60}")
            except ValueError:
                print("Input non valido")
            except Exception as e:
                print(f"Errore durante la generazione: {e}")
    else:
        print("\nNessun soundbite trovato per questo episodio.")


if __name__ == "__main__":
    main()
