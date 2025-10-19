"""
Interfaccia a riga di comando per il generatore di audiogrammi
"""
import feedparser
import ssl
import urllib.request
import xml.etree.ElementTree as ET
import re


def get_podcast_episodes():
    """Recupera la lista degli episodi dal feed RSS"""
    feed_url = "https://pensieriincodice.it/podcast/index.xml"

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
    namespaces = {'podcast': 'https://github.com/Podcastindex-org/podcast-namespace/blob/main/docs/1.0.md'}

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

    # Trova tutti gli item e i loro soundbites, transcript e audio
    transcript_by_guid = {}
    audio_by_guid = {}
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
            'audio_url': audio_by_guid.get(guid, None)
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


def main():
    """Funzione principale CLI"""
    print("Recupero episodi dal feed...")
    episodes, podcast_info = get_podcast_episodes()

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

    # Chiedi quale episodio scegliere
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
                    print(f"     Testo: {transcript_text}")
                else:
                    print(f"     Testo: [Non disponibile]")
    else:
        print("\nNessun soundbite trovato per questo episodio.")


if __name__ == "__main__":
    main()
