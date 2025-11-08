"""
Command-line interface for the audiogram generator
"""
import feedparser
import ssl
import urllib.request
import xml.etree.ElementTree as ET
import re
import os
import tempfile
import argparse
from typing import List
from .audio_utils import download_audio, extract_audio_segment
from .video_generator import generate_audiogram, download_image
from .config import Config


def get_podcast_episodes(feed_url):
    """Fetch the list of episodes from the RSS feed"""
    # Crea un contesto SSL che non verifica i certificati
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Scarica il feed con il contesto SSL personalizzato
    request = urllib.request.Request(feed_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, context=ssl_context) as response:
        feed_content = response.read()

    # Parsa XML per estrarre soundbites con testo
    root = ET.fromstring(feed_content)
    soundbites_by_guid = {}

    # Registra namespace
    namespaces = {
        'podcast': 'https://podcastindex.org/namespace/1.0',
        'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'
    }

    # Estrai informazioni del podcast (locandina e titolo)
    podcast_info = {}
    channel = root.find('.//channel')
    if channel is not None:
        # Titolo del podcast
        title_elem = channel.find('title')
        if title_elem is not None and title_elem.text:
            podcast_info['title'] = title_elem.text.strip()

        # Locandina del podcast
        image_elem = channel.find('image')
        if image_elem is not None:
            url_elem = image_elem.find('url')
            if url_elem is not None and url_elem.text:
                podcast_info['image_url'] = url_elem.text.strip()

        # Keywords/tags del podcast
        keywords_elem = channel.find('itunes:keywords', namespaces)
        if keywords_elem is not None and keywords_elem.text:
            podcast_info['keywords'] = keywords_elem.text.strip()

    # Trova tutti gli item e i loro soundbites, transcript, audio e keywords
    transcript_by_guid = {}
    audio_by_guid = {}
    keywords_by_guid = {}
    for item in root.findall('.//item'):
        guid_elem = item.find('guid')
        if guid_elem is not None:
            guid = guid_elem.text.strip() if guid_elem.text else ''

            # Estrai soundbites
            soundbites = []
            for sb in item.findall('podcast:soundbite', namespaces):
                soundbites.append({
                    'start': sb.get('startTime'),
                    'duration': sb.get('duration'),
                    'text': sb.text.strip() if sb.text else 'Senza descrizione'
                })
            if soundbites:
                soundbites_by_guid[guid] = soundbites

            # Estrai URL transcript
            transcript_elem = item.find('podcast:transcript', namespaces)
            if transcript_elem is not None:
                transcript_url = transcript_elem.get('url')
                if transcript_url:
                    transcript_by_guid[guid] = transcript_url

            # Estrai URL audio da enclosure
            enclosure_elem = item.find('enclosure')
            if enclosure_elem is not None:
                audio_url = enclosure_elem.get('url')
                if audio_url:
                    audio_by_guid[guid] = audio_url

            # Estrai keywords dell'episodio
            keywords_elem = item.find('itunes:keywords', namespaces)
            if keywords_elem is not None and keywords_elem.text:
                keywords_by_guid[guid] = keywords_elem.text.strip()

    feed = feedparser.parse(feed_content)

    episodes = []
    total_episodes = len(feed.entries)

    for idx, entry in enumerate(reversed(feed.entries)):
        # Calcola il numero dell'episodio (dal più vecchio al più recente)
        episode_number = idx + 1

        guid = entry.get('guid', entry.get('id', ''))

        episode = {
            'number': episode_number,
            'title': entry.get('title', 'Senza titolo'),
            'link': entry.get('link', ''),
            'description': entry.get('description', ''),
            'soundbites': soundbites_by_guid.get(guid, []),
            'transcript_url': transcript_by_guid.get(guid, None),
            'audio_url': audio_by_guid.get(guid, None),
            'keywords': keywords_by_guid.get(guid, None)
        }
        episodes.append(episode)

    return episodes, podcast_info


def parse_srt_time(time_str):
    """Converte un timestamp SRT in secondi"""
    # Formato: 00:00:10,500 -> 10.5 secondi
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def get_transcript_text(transcript_url, start_time, duration):
    """Scarica il file SRT e estrae il testo nel range temporale"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        request = urllib.request.Request(transcript_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(request, context=ssl_context) as response:
            srt_content = response.read().decode('utf-8')

        start_time_sec = float(start_time)
        end_time_sec = start_time_sec + float(duration)

        # Parsa il file SRT
        # Formato: numero\ntimestamp --> timestamp\ntesto\n\n
        entries = re.split(r'\n\n+', srt_content.strip())

        transcript_lines = []
        for entry in entries:
            lines = entry.strip().split('\n')
            if len(lines) >= 3:
                # lines[0] = numero
                # lines[1] = timestamp
                # lines[2+] = testo
                timestamp_line = lines[1]
                if '-->' in timestamp_line:
                    time_parts = timestamp_line.split('-->')
                    entry_start = parse_srt_time(time_parts[0].strip())
                    entry_end = parse_srt_time(time_parts[1].strip())

                    # Verifica se questo entry è nel range del soundbite
                    if (entry_start >= start_time_sec and entry_start < end_time_sec) or \
                       (entry_end > start_time_sec and entry_end <= end_time_sec) or \
                       (entry_start <= start_time_sec and entry_end >= end_time_sec):
                        text = ' '.join(lines[2:])
                        transcript_lines.append(text)

        return ' '.join(transcript_lines) if transcript_lines else None
    except Exception as e:
        return None


def get_transcript_chunks(transcript_url, start_time, duration):
    """Scarica il file SRT e restituisce chunk di testo con timing per il soundbite"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        request = urllib.request.Request(transcript_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(request, context=ssl_context) as response:
            srt_content = response.read().decode('utf-8')

        start_time_sec = float(start_time)
        end_time_sec = start_time_sec + float(duration)

        # Parsa il file SRT
        entries = re.split(r'\n\n+', srt_content.strip())

        transcript_chunks = []
        for entry in entries:
            lines = entry.strip().split('\n')
            if len(lines) >= 3:
                timestamp_line = lines[1]
                if '-->' in timestamp_line:
                    time_parts = timestamp_line.split('-->')
                    entry_start = parse_srt_time(time_parts[0].strip())
                    entry_end = parse_srt_time(time_parts[1].strip())

                    # Verifica se questo entry è nel range del soundbite
                    if (entry_start >= start_time_sec and entry_start < end_time_sec) or \
                       (entry_end > start_time_sec and entry_end <= end_time_sec) or \
                       (entry_start <= start_time_sec and entry_end >= end_time_sec):
                        text = ' '.join(lines[2:])
                        # Converti timing relativi al soundbite (inizia da 0)
                        transcript_chunks.append({
                            'start': max(0, entry_start - start_time_sec),
                            'end': min(float(duration), entry_end - start_time_sec),
                            'text': text
                        })

        return transcript_chunks
    except Exception as e:
        return []


def generate_caption_file(output_path, episode_number, episode_title, episode_link,
                          soundbite_title, transcript_text, podcast_keywords=None,
                          episode_keywords=None, config_hashtags=None):
    """
    Genera un file .md con la caption per il post social

    Args:
        output_path: Path del file .md da creare
        episode_number: Numero dell'episodio
        episode_title: Titolo dell'episodio
        episode_link: Link all'episodio
        soundbite_title: Titolo del soundbite
        transcript_text: Testo della trascrizione
        podcast_keywords: Keywords dal feed del podcast (opzionale)
        episode_keywords: Keywords dal feed dell'episodio (opzionale)
        config_hashtags: Lista di hashtag dal file di configurazione (opzionale)
    """
    # Combina tutti gli hashtag disponibili
    hashtags = []

    # Aggiungi keywords dal feed del podcast
    if podcast_keywords:
        feed_tags = [tag.strip() for tag in podcast_keywords.split(',')]
        hashtags.extend(feed_tags)

    # Aggiungi keywords dall'episodio
    if episode_keywords:
        episode_tags = [tag.strip() for tag in episode_keywords.split(',')]
        hashtags.extend(episode_tags)

    # Aggiungi hashtag dal file di configurazione
    if config_hashtags:
        hashtags.extend(config_hashtags)

    # Rimuovi duplicati preservando l'ordine
    seen = set()
    unique_hashtags = []
    for tag in hashtags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_hashtags.append(tag)

    # Formatta hashtag con il simbolo #
    hashtag_string = ' '.join([f'#{tag}' for tag in unique_hashtags]) if unique_hashtags else '#podcast'

    caption = f"""# Social Media Caption

## Episode {episode_number}: {episode_title}

{soundbite_title}

{transcript_text}

🎧 Listen to the full episode: {episode_link}

---

**Suggested hashtags:**
{hashtag_string}
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(caption)


def parse_episode_selection(value, max_episode: int) -> List[int]:
    """Parsa la selezione episodio: numero, lista separata da virgole, o 'all'/'a'"""
    if value is None:
        return []
    if isinstance(value, int):
        if 1 <= value <= max_episode:
            return [value]
        raise ValueError('Numero episodio fuori intervallo')
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ('all', 'a'):
            return list(range(1, max_episode + 1))
        parts = [p.strip() for p in v.split(',') if p.strip()]
        nums: List[int] = []
        for p in parts:
            if not p.isdigit():
                raise ValueError('Valore non numerico nella lista')
            n = int(p)
            if not (1 <= n <= max_episode):
                raise ValueError('Numero episodio fuori intervallo')
            if n not in nums:
                nums.append(n)
        if not nums:
            raise ValueError('Nessun episodio valido specificato')
        return nums
    raise ValueError('Formato episodio non supportato')


def process_one_episode(selected, podcast_info, colors, formats_config, config_hashtags, cta_text, show_progress_bar, output_dir, soundbites_choice):
    print(f"\nEpisodio {selected['number']}: {selected['title']}")
    if selected['audio_url']:
        print(f"Audio: {selected['audio_url']}")

    # Mostra soundbites se esistono
    if selected['soundbites']:
        print(f"\nSoundbites trovati ({len(selected['soundbites'])}):")
        for i, soundbite in enumerate(selected['soundbites'], 1):
            print(f"\n  {i}. [Inizio: {soundbite['start']}s, Durata: {soundbite['duration']}s]")
            print(f"     Titolo: {soundbite['text']}")

            # Estrai testo dalla trascrizione se disponibile
            if selected['transcript_url']:
                transcript_text = get_transcript_text(
                    selected['transcript_url'],
                    soundbite['start'],
                    soundbite['duration']
                )
                if transcript_text:
                    print(f"     Testo: {transcript_text[:100]}..." if len(transcript_text) > 100 else f"     Testo: {transcript_text}")
                else:
                    print(f"     Testo: [Non disponibile]")

        # Chiedi quale soundbite generare se non specificato
        print("\n" + "="*60)
        if soundbites_choice is None:
            choice = input("\nVuoi generare audiogram per un soundbite? (numero, 'a' per tutti, o 'n' per uscire): ")
        else:
            choice = str(soundbites_choice)

        if choice.lower() == 'a' or choice.lower() == 'all':
            # Genera tutti i soundbites
            print(f"\nGenerazione audiogram per tutti i {len(selected['soundbites'])} soundbites...")

            # Crea directory temporanea
            with tempfile.TemporaryDirectory() as temp_dir:
                # Scarica audio completo una sola volta
                print("\nDownload audio...")
                full_audio_path = os.path.join(temp_dir, "full_audio.mp3")
                download_audio(selected['audio_url'], full_audio_path)

                # Scarica logo una sola volta
                print("Download locandina...")
                logo_path = os.path.join(temp_dir, "logo.png")
                download_image(podcast_info['image_url'], logo_path)

                # Crea directory output
                os.makedirs(output_dir, exist_ok=True)

                # Processa ogni soundbite
                for soundbite_num, soundbite in enumerate(selected['soundbites'], 1):
                    print(f"\n{'='*60}")
                    print(f"Soundbite {soundbite_num}/{len(selected['soundbites'])}: {soundbite['text']}")
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
                        output_path = os.path.join(
                            output_dir,
                            f"ep{selected['number']}_sb{soundbite_num}_{format_name}.mp4"
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
                            cta_text,
                            show_progress_bar
                        )

                        print(f"✓ {format_name}: {output_path}")

                    # Genera file caption .md
                    print("Generazione file caption...")
                    caption_path = os.path.join(
                        output_dir,
                        f"ep{selected['number']}_sb{soundbite_num}_caption.md"
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
                            output_path = os.path.join(
                                output_dir,
                                f"ep{selected['number']}_sb{soundbite_num}_{format_name}.mp4"
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
                                cta_text,
                                show_progress_bar
                            )

                            print(f"✓ {format_name}: {output_path}")

                        # Genera file caption .md
                        print("Generazione file caption...")
                        caption_path = os.path.join(
                            output_dir,
                            f"ep{selected['number']}_sb{soundbite_num}_caption.md"
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


def main():
    """Funzione principale CLI"""
    # Argument parsing
    parser = argparse.ArgumentParser(description='Audiogram generator from podcast RSS')
    parser.add_argument('--config', type=str, help='Path to the YAML configuration file')
    parser.add_argument('--feed-url', type=str, help='URL of the podcast RSS feed')
    parser.add_argument('--episode', type=str, help="Episode(s) to process: number (e.g., 5), list (e.g., 1,3,5) or 'all'/'a' for all")
    parser.add_argument('--soundbites', type=str, help='Soundbites to generate: specific number, "all" for all, or comma-separated list (e.g., 1,3,5)')
    parser.add_argument('--output-dir', type=str, help='Output directory for generated files')

    args = parser.parse_args()

    # Carica configurazione
    config = Config(config_file=args.config)

    # Aggiorna configurazione con argomenti CLI (hanno precedenza)
    config.update_from_args({
        'feed_url': args.feed_url,
        'episode': args.episode,
        'soundbites': args.soundbites,
        'output_dir': args.output_dir
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
    cta_text = config.get('cta_text')
    show_progress_bar = config.get('show_progress_bar', False)

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
                choice = input(f"\nSeleziona episodio: numero (es. 5), lista (es. 1,3,5) o 'all'/'a' per tutti: ").strip()
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
            cta_text=cta_text,
            show_progress_bar=show_progress_bar,
            output_dir=output_dir,
            soundbites_choice=soundbites_choice
        )

    return

    # Chiedi quale episodio scegliere se non specificato
    if episode_num is None:
        while True:
            try:
                choice = input(f"\nScegli il numero dell'episodio (1-{len(episodes)}): ")
                episode_num = int(choice)
                if 1 <= episode_num <= len(episodes):
                    break
                print(f"Inserisci un numero tra 1 e {len(episodes)}")
            except ValueError:
                print("Inserisci un numero valido")
            except KeyboardInterrupt:
                print("\nOperazione annullata.")
                return
    else:
        if not (1 <= episode_num <= len(episodes)):
            print(f"Errore: numero episodio deve essere tra 1 e {len(episodes)}")
            return

    # Trova l'episodio selezionato
    selected = None
    for ep in episodes:
        if ep['number'] == episode_num:
            selected = ep
            break

    print(f"\nEpisodio {selected['number']}: {selected['title']}")
    if selected['audio_url']:
        print(f"Audio: {selected['audio_url']}")

    # Mostra soundbites se esistono
    if selected['soundbites']:
        print(f"\nSoundbites trovati ({len(selected['soundbites'])}):")
        for i, soundbite in enumerate(selected['soundbites'], 1):
            print(f"\n  {i}. [Inizio: {soundbite['start']}s, Durata: {soundbite['duration']}s]")
            print(f"     Titolo: {soundbite['text']}")

            # Estrai testo dalla trascrizione se disponibile
            if selected['transcript_url']:
                transcript_text = get_transcript_text(
                    selected['transcript_url'],
                    soundbite['start'],
                    soundbite['duration']
                )
                if transcript_text:
                    print(f"     Testo: {transcript_text[:100]}..." if len(transcript_text) > 100 else f"     Testo: {transcript_text}")
                else:
                    print(f"     Testo: [Non disponibile]")

        # Chiedi quale soundbite generare se non specificato
        print("\n" + "="*60)
        if soundbites_choice is None:
            choice = input("\nVuoi generare audiogram per un soundbite? (numero, 'a' per tutti, o 'n' per uscire): ")
        else:
            choice = str(soundbites_choice)

        if choice.lower() == 'a' or choice.lower() == 'all':
            # Genera tutti i soundbites
            print(f"\nGenerazione audiogram per tutti i {len(selected['soundbites'])} soundbites...")

            # Crea directory temporanea
            with tempfile.TemporaryDirectory() as temp_dir:
                # Scarica audio completo una sola volta
                print("\nDownload audio...")
                full_audio_path = os.path.join(temp_dir, "full_audio.mp3")
                download_audio(selected['audio_url'], full_audio_path)

                # Scarica logo una sola volta
                print("Download locandina...")
                logo_path = os.path.join(temp_dir, "logo.png")
                download_image(podcast_info['image_url'], logo_path)

                # Crea directory output
                os.makedirs(output_dir, exist_ok=True)

                # Processa ogni soundbite
                for soundbite_num, soundbite in enumerate(selected['soundbites'], 1):
                    print(f"\n{'='*60}")
                    print(f"Soundbite {soundbite_num}/{len(selected['soundbites'])}: {soundbite['text']}")
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
                        output_path = os.path.join(
                            output_dir,
                            f"ep{selected['number']}_sb{soundbite_num}_{format_name}.mp4"
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
                            cta_text,
                            show_progress_bar
                        )

                        print(f"✓ {format_name}: {output_path}")

                    # Genera file caption .md
                    print("Generazione file caption...")
                    caption_path = os.path.join(
                        output_dir,
                        f"ep{selected['number']}_sb{soundbite_num}_caption.md"
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
                            output_path = os.path.join(
                                output_dir,
                                f"ep{selected['number']}_sb{soundbite_num}_{format_name}.mp4"
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
                                cta_text,
                                show_progress_bar
                            )

                            print(f"✓ {format_name}: {output_path}")

                        # Genera file caption .md
                        print("Generazione file caption...")
                        caption_path = os.path.join(
                            output_dir,
                            f"ep{selected['number']}_sb{soundbite_num}_caption.md"
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
