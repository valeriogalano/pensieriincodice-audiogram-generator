"""
Interfaccia a riga di comando per il generatore di audiogrammi
"""
import feedparser
import ssl
import urllib.request
import xml.etree.ElementTree as ET


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

    # Trova tutti gli item e i loro soundbites
    for item in root.findall('.//item'):
        guid_elem = item.find('guid')
        if guid_elem is not None:
            guid = guid_elem.text.strip() if guid_elem.text else ''
            soundbites = []
            for sb in item.findall('podcast:soundbite', namespaces):
                soundbites.append({
                    'start': sb.get('startTime'),
                    'duration': sb.get('duration'),
                    'text': sb.text.strip() if sb.text else 'Senza descrizione'
                })
            if soundbites:
                soundbites_by_guid[guid] = soundbites

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
            'soundbites': soundbites_by_guid.get(guid, [])
        }
        episodes.append(episode)

    return episodes


def main():
    """Funzione principale CLI"""
    print("Recupero episodi dal feed...")
    episodes = get_podcast_episodes()

    if not episodes:
        print("Nessun episodio trovato nel feed.")
        return

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

    # Mostra soundbites se esistono
    if selected['soundbites']:
        print(f"\nSoundbites trovati ({len(selected['soundbites'])}):")
        for i, soundbite in enumerate(selected['soundbites'], 1):
            print(f"  {i}. [Inizio: {soundbite['start']}s, Durata: {soundbite['duration']}s] {soundbite['text']}")
    else:
        print("\nNessun soundbite trovato per questo episodio.")


if __name__ == "__main__":
    main()
