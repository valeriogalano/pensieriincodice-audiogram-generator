"""
Generatore di video audiogram
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import VideoClip, AudioFileClip
from pydub import AudioSegment
import urllib.request
import ssl
import re
import unicodedata


# Formati video per social media
FORMATS = {
    # Verticale 9:16 - Instagram Reels/Stories, YouTube Shorts, TikTok, Twitter
    'vertical': (1080, 1920),
    # Quadrato 1:1 - Instagram Post, Twitter, Mastodon, LinkedIn
    'square': (1080, 1080),
    # Orizzontale 16:9 - YouTube, Twitter orizzontale
    'horizontal': (1920, 1080)
}

# Colori Pensieri in Codice
COLOR_ORANGE = (242, 101, 34)
COLOR_BEIGE = (235, 213, 197)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (50, 50, 50)

# Spaziatura tra le righe del titolo episodio (header)
# Aumentata per migliorare la leggibilità nelle intestazioni multi‑riga
HEADER_LINE_SPACING = 1.45


def _subtitle_default_style(colors):
    """Ritorna lo stile predefinito per i sottotitoli (trascrizione)."""
    # Colori con alpha per sfondo
    bg = tuple(colors.get('transcript_bg', COLOR_BLACK))
    bg_with_alpha = bg + (190,) if len(bg) == 3 else bg
    return {
        'text_color': tuple(colors.get('text', COLOR_WHITE)),
        'bg_color': bg_with_alpha,      # RGBA
        'padding': 18,                  # px
        'radius': 18,                   # px angoli arrotondati
        'line_spacing': 2,              # moltiplicatore altezza riga
        'shadow': True,                 # ombra soft al box
        'shadow_offset': (0, 4),        # dx, dy
        'shadow_blur': 10,              # raggio blur
        'max_lines': 5,                 # righe massime visualizzate
        'width_ratio': 0.88             # % della larghezza massima
    }


def _strip_punctuation(text: str) -> str:
    """Rimuove la punteggiatura (Unicode) dal testo dei sottotitoli e normalizza gli spazi.
    Esempi rimossi: . , ; : ! ? … – — - ( ) [ ] { } « » “ ” ' " ecc.
    """
    if not text:
        return text
    # Rimuovi tutti i caratteri la cui categoria Unicode inizia con 'P' (punctuation)
    no_punct = ''.join((ch if unicodedata.category(ch)[0] != 'P' else ' ') for ch in text)
    # Collassa spazi multipli e trim
    return re.sub(r"\s+", " ", no_punct).strip()


def _draw_rounded_box_with_shadow(base_img, box, fill, radius=16, shadow=True, shadow_offset=(0, 3), shadow_blur=8):
    """Disegna un rettangolo arrotondato semi-trasparente con ombra su un overlay RGBA e lo compone su base_img.
    box: (x1, y1, x2, y2)
    Ritorna l'immagine risultante (stessa istanza o nuova se necessario).
    """
    # Assicurati che la base sia RGBA per alpha_composite
    if base_img.mode != 'RGBA':
        base_img = base_img.convert('RGBA')

    overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    if shadow:
        sx = box[0] + shadow_offset[0]
        sy = box[1] + shadow_offset[1]
        ex = box[2] + shadow_offset[0]
        ey = box[3] + shadow_offset[1]
        shadow_overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow_overlay)
        sdraw.rounded_rectangle([(sx, sy), (ex, ey)], radius=radius, fill=(0, 0, 0, 140))
        shadow_overlay = shadow_overlay.filter(ImageFilter.GaussianBlur(shadow_blur))
        base_img = Image.alpha_composite(base_img, shadow_overlay)

    odraw.rounded_rectangle([box[:2], box[2:]], radius=radius, fill=fill)
    base_img = Image.alpha_composite(base_img, overlay)
    return base_img


def _render_subtitle_lines(img, draw, text, font, start_y, max_width, style, x_bounds=None):
    """Esegue il word wrap e disegna le righe di sottotitoli più gradevoli entro un'area orizzontale opzionale.
    Ritorna (img, total_height_disegnata).

    Nota: la spaziatura verticale tra le righe usa un'altezza di riga costante
    basata sulle metriche del font, così da evitare differenze dovute ai glifi
    presenti nelle singole righe (ascendenti/descendenti).
    """
    # Word wrap manuale
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + w + " ").strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test + " " if not test.endswith(" ") else test
        else:
            if current.strip():
                lines.append(current.strip())
            current = w + " "
    if current.strip():
        lines.append(current.strip())

    lines = lines[: style.get('max_lines', 5)]

    padding = int(style.get('padding', 0))

    # Limiti orizzontali per il centraggio entro safe area
    if x_bounds is not None:
        left_bound = max(0, int(x_bounds[0]))
        right_bound = min(img.width, int(x_bounds[1]))
        # Riduci i bounds per includere il padding del box, così il box non esce dalla safe area
        inner_left = min(max(left_bound + padding, 0), img.width)
        inner_right = max(min(right_bound - padding, img.width), 0)
        if inner_right < inner_left:
            inner_left, inner_right = inner_right, inner_left  # fallback
        area_width = max(1, inner_right - inner_left)
    else:
        inner_left = 0 + padding
        inner_right = img.width - padding
        area_width = max(1, inner_right - inner_left)

    # Calcola altezza di riga costante basata sul font
    try:
        ascent, descent = font.getmetrics()
        constant_line_height = ascent + descent
    except Exception:
        # Fallback: usa l'altezza del bbox di una stringa campione
        sample_bbox = draw.textbbox((0, 0), "Hg", font=font)
        constant_line_height = (sample_bbox[3] - sample_bbox[1])

    total_height = 0
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        # Centra entro l'area definita (già ridotta del padding)
        line_x = inner_left + (area_width - lw) // 2
        line_y = start_y + int(total_height)

        box = (line_x - padding, line_y - padding, line_x + lw + padding, line_y + lh + padding)
        img = _draw_rounded_box_with_shadow(
            img,
            box,
            style['bg_color'],
            radius=style['radius'],
            shadow=style['shadow'],
            shadow_offset=style['shadow_offset'],
            shadow_blur=style['shadow_blur']
        )

        # Dopo compositing, ricrea draw su eventuale immagine RGBA
        draw = ImageDraw.Draw(img)
        draw.text((line_x, line_y), line, fill=style['text_color'], font=font)

        # Avanzamento verticale costante, indipendente dai glifi della riga
        line_advance = int(constant_line_height * style['line_spacing'])
        total_height += line_advance

    return img, int(total_height)


def _draw_text_with_stroke(draw, position, text, font, fill, stroke_width=2, stroke_fill=(30, 30, 30)):
    """Disegna testo con un sottile contorno per aumentare il contrasto.
    Usa i parametri stroke nativi di PIL se disponibili.
    """
    try:
        draw.text(position, text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
    except TypeError:
        # Fallback per versioni PIL molto vecchie: disegna il contorno manuale
        x, y = position
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-1,1),(1,-1)]:
            draw.text((x+dx, y+dy), text, font=font, fill=stroke_fill)
        draw.text(position, text, font=font, fill=fill)


def _draw_pill_with_text(img, draw, text, font, center_x, y, padding_x=24, padding_y=12,
                         pill_color=(255, 255, 255, 230), radius=22, shadow=True,
                         text_color=(0, 0, 0), stroke_width=0, stroke_fill=(30, 30, 30)):
    """Disegna una 'pill' arrotondata con ombra e testo centrato.
    Ritorna (img, text_x, text_y) per eventuali usi successivi.
    """
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]

    x1 = int(center_x - (tw // 2) - padding_x)
    y1 = int(y - padding_y)
    x2 = int(center_x + (tw // 2) + padding_x)
    y2 = int(y + th + padding_y)

    # Disegna pill con ombra su overlay
    img = _draw_rounded_box_with_shadow(img, (x1, y1, x2, y2), pill_color, radius=radius, shadow=shadow, shadow_offset=(0, 4), shadow_blur=10)
    draw = ImageDraw.Draw(img)

    text_x = int(center_x - tw // 2)
    text_y = int(y)
    if stroke_width > 0:
        _draw_text_with_stroke(draw, (text_x, text_y), text, font, text_color, stroke_width=stroke_width, stroke_fill=stroke_fill)
    else:
        draw.text((text_x, text_y), text, font=font, fill=text_color)
    return img, text_x, text_y


def download_image(url, output_path):
    """Scarica un'immagine da URL"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, context=ssl_context) as response:
        with open(output_path, 'wb') as f:
            f.write(response.read())


def get_waveform_data(audio_path, fps=24):
    """
    Estrae dati waveform dall'audio campionati per frame

    Args:
        audio_path: Percorso del file audio
        fps: Frame per secondo del video

    Returns:
        Array di ampiezze per ogni frame del video
    """
    audio = AudioSegment.from_file(audio_path)
    samples = np.array(audio.get_array_of_samples())

    # Normalizza
    if len(samples) > 0:
        samples = samples.astype(float)
        samples = samples / np.max(np.abs(samples))

    # Calcola quanti campioni audio per frame video
    sample_rate = audio.frame_rate
    duration_seconds = len(audio) / 1000.0
    total_frames = int(duration_seconds * fps)
    samples_per_frame = len(samples) // total_frames if total_frames > 0 else len(samples)

    # Estrai ampiezza media per ogni frame
    frame_amplitudes = []
    for i in range(total_frames):
        start = i * samples_per_frame
        end = min(start + samples_per_frame, len(samples))
        if start < len(samples):
            chunk = samples[start:end]
            frame_amplitudes.append(np.abs(chunk).mean())

    return np.array(frame_amplitudes)


def create_vertical_layout(img, draw, width, height, podcast_logo_path, podcast_title, episode_title,
                           waveform_data, current_time, transcript_chunks, audio_duration, colors, safe_area=None, debug_draw_safe_area=False, apply_safe_area_to_visuals=False):
    """
    Layout specifico per formato verticale 9:16 (1080x1920)
    Ottimizzato per Instagram Reels, Stories, YouTube Shorts, TikTok
    """
    progress_height = 0
    # Safe area (insets) calcolata una volta
    sa = safe_area or {}
    safe_left = int(sa.get('left', 0))
    safe_right = width - int(sa.get('right', 0))
    safe_top = int(sa.get('top', 0))
    safe_bottom = height - int(sa.get('bottom', 0))

    # Debug: disegna il rettangolo della safe area
    if debug_draw_safe_area:
        dbg_color = (0, 255, 0)
        dbg_alpha = 60
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        o = ImageDraw.Draw(overlay)
        o.rectangle([(safe_left, safe_top), (safe_right, safe_bottom)], outline=dbg_color + (255,), width=4, fill=(0, 255, 0, dbg_alpha))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

    # Header (17% altezza) - vuoto, senza titolo episodio
    header_top = progress_height
    header_height = int(height * 0.17)
    draw.rectangle([(0, header_top), (width, header_top + header_height)], fill=colors['primary'])

    # Area centrale (54% altezza) - ridotta per compensare l'header più grande
    central_top = header_top + header_height
    central_height = int(height * 0.54)
    central_bottom = central_top + central_height

    # Visualizzatore waveform tipo equalizer che "balla" con l'audio
    if waveform_data is not None and len(waveform_data) > 0:
        # Configurazione bars
        bar_spacing = 3
        bar_width = 12
        total_bar_width = bar_width + bar_spacing

        # Applica safe area orizzontale se richiesto
        if apply_safe_area_to_visuals:
            x_start = safe_left
            available_width = max(0, safe_right - safe_left)
        else:
            x_start = 0
            available_width = width

        # Calcola quante bars entrano nella larghezza disponibile
        num_bars = available_width // total_bar_width
        # Rendi pari per simmetria
        if num_bars % 2 != 0:
            num_bars -= 1

        # Proteggi contro num_bars troppo piccolo (serve almeno 2 per la simmetria)
        if num_bars >= 2:
            # Ottieni l'ampiezza corrente dell'audio in questo momento
            frame_idx = int((current_time / audio_duration) * len(waveform_data)) if audio_duration > 0 else 0
            frame_idx = min(frame_idx, len(waveform_data) - 1)
            current_amplitude = waveform_data[frame_idx]

            # Crea pattern simmetrico con variazione casuale ma controllata
            # Ogni bar ha una "sensibilità" diversa alle frequenze
            np.random.seed(42)  # Seed fisso per consistenza tra frame
            sensitivities = np.random.uniform(0.6, 1.4, num_bars // 2)
            sensitivities = np.concatenate([sensitivities, sensitivities[::-1]])  # Simmetria

            # Area verticale disponibile per waveform entro la safe area (intersezione con area centrale)
            if apply_safe_area_to_visuals:
                avail_top = max(central_top, safe_top)
                avail_bottom = min(central_bottom, safe_bottom)
            else:
                avail_top = central_top
                avail_bottom = central_bottom
            avail_height = max(0, avail_bottom - avail_top)

            # Disegna le bars da sinistra a destra
            for i in range(num_bars):
                x = x_start + i * total_bar_width

                # Calcola altezza bar con pattern simmetrico dal centro
                center_idx = num_bars // 2
                distance_from_center = abs(i - center_idx)

                # Le bars centrali sono più reattive
                center_boost = 1.0 + (1.0 - distance_from_center / center_idx) * 0.4 if center_idx > 0 else 1.0

                # Ampiezza finale con sensibilità e boost
                bar_amplitude = current_amplitude * sensitivities[i] * center_boost

                # Altezza minima e massima (relativa all'altezza disponibile)
                # Altezza minima ridotta per avere barre più sottili quando non c'è suono
                min_height = int(avail_height * 0.03)
                max_height = int(avail_height * 0.80)
                bar_height = int(min_height + (bar_amplitude * (max_height - min_height))) if max_height > min_height else min_height
                bar_height = max(min_height, min(bar_height, max_height))

                # Centra verticalmente all'interno dell'area disponibile (spostato al 40%)
                if avail_height > 0:
                    y_center = avail_top + int(avail_height * 0.40)
                else:
                    y_center = central_top + int(central_height * 0.40)
                y_top = y_center - bar_height // 2
                y_bottom = y_center + bar_height // 2

                # Clamp finale entro i limiti verticali
                if apply_safe_area_to_visuals:
                    y_top = max(y_top, safe_top)
                    y_bottom = min(y_bottom, safe_bottom)

                # Disegna la bar solo se visibile
                if y_bottom > y_top and (x + bar_width) > x and x < (x_start + available_width):
                    draw.rectangle([(x, y_top), (x + bar_width, y_bottom)], fill=colors['primary'])

    # Logo podcast al centro (sopra la waveform) - spostato più in alto
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        logo_size = int(min(width, central_height) * 0.6)
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # Posizione spostata più in alto (al 35% invece del 50%)
        logo_x = (width - logo_size) // 2
        logo_y = central_top + int(central_height * 0.35) - logo_size // 2
        img.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    # Footer (27% altezza) - vuoto, senza titolo podcast e CTA
    footer_top = central_bottom
    footer_height = int(height * 0.27)
    footer_bottom = footer_top + footer_height
    draw.rectangle([(0, footer_top), (width, footer_bottom)], fill=colors['primary'])

    # Trascrizione in tempo reale (sopra il footer, nell'area centrale bassa)
    if transcript_chunks:
        current_text = ""
        for chunk in transcript_chunks:
            if chunk['start'] <= current_time < chunk['end']:
                current_text = chunk['text']
                break

        if current_text:
            current_text = _strip_punctuation(current_text)
            try:
                font_transcript = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(height * 0.028))
            except:
                font_transcript = ImageFont.load_default()

            # Posizionamento più in basso per aumentare lo spazio dal logo
            base_y = central_top + int(central_height * 0.74)

            # Stile sottotitoli
            style = _subtitle_default_style(colors)

            # Calcola safe area (default nessun margine)
            sa = safe_area or {}
            safe_left = int(sa.get('left', 0))
            safe_right = width - int(sa.get('right', 0))
            safe_top = int(sa.get('top', 0))
            safe_bottom = height - int(sa.get('bottom', 0))
            # Larghezza massima: min tra ratio e larghezza safe
            max_width_ratio = int(width * style['width_ratio'])
            max_width_safe = max(50, safe_right - safe_left)
            max_width = min(max_width_ratio, max_width_safe)

            # Stima altezza box multi-riga per clamp verticale
            bbox_sample = draw.textbbox((0, 0), "Ag", font=font_transcript)
            lh = bbox_sample[3] - bbox_sample[1]
            lines_max = style.get('max_lines', 5)
            line_advance = int(lh * style['line_spacing']) if lh > 0 else lh
            text_block_h = max(lh, line_advance) * lines_max
            est_box_h = text_block_h + style.get('padding', 18) * 2

            # Clamp della Y entro la safe area
            transcript_y = max(safe_top, min(base_y, safe_bottom - est_box_h))

            img, _ = _render_subtitle_lines(
                img,
                draw,
                current_text,
                font_transcript,
                transcript_y,
                max_width,
                style,
                x_bounds=(safe_left, safe_right)
            )
            # Aggiorna draw nel caso l'immagine sia stata convertita in RGBA
            draw = ImageDraw.Draw(img)

    return img


def create_square_layout(img, draw, width, height, podcast_logo_path, podcast_title, episode_title,
                         waveform_data, current_time, transcript_chunks, audio_duration, colors):
    """
    Layout specifico per formato quadrato 1:1 (1080x1080)
    Ottimizzato per Instagram Post, Twitter, Mastodon, LinkedIn
    Logo e waveform centrati verticalmente
    """
    progress_height = 0

    # Header (12% altezza) - vuoto, senza titolo episodio
    header_top = progress_height
    header_height = int(height * 0.12)
    draw.rectangle([(0, header_top), (width, header_top + header_height)], fill=colors['primary'])
    
    # Area centrale (66% altezza) - più grande per square
    central_top = header_top + header_height
    central_height = int(height * 0.66)
    central_bottom = central_top + central_height

    # Visualizzatore waveform CENTRATO VERTICALMENTE
    if waveform_data is not None and len(waveform_data) > 0:
        bar_spacing = 3
        bar_width = 12
        total_bar_width = bar_width + bar_spacing

        num_bars = width // total_bar_width
        if num_bars % 2 != 0:
            num_bars -= 1

        if num_bars >= 2:
            frame_idx = int((current_time / audio_duration) * len(waveform_data)) if audio_duration > 0 else 0
            frame_idx = min(frame_idx, len(waveform_data) - 1)
            current_amplitude = waveform_data[frame_idx]

            np.random.seed(42)
            sensitivities = np.random.uniform(0.6, 1.4, num_bars // 2)
            sensitivities = np.concatenate([sensitivities, sensitivities[::-1]])

            for i in range(num_bars):
                x = i * total_bar_width

                center_idx = num_bars // 2
                distance_from_center = abs(i - center_idx)
                center_boost = 1.0 + (1.0 - distance_from_center / center_idx) * 0.4 if center_idx > 0 else 1.0
                bar_amplitude = current_amplitude * sensitivities[i] * center_boost

                # Altezza minima ridotta per avere barre più sottili quando non c'è suono
                min_height = int(central_height * 0.03)
                max_height = int(central_height * 0.70)
                bar_height = int(min_height + (bar_amplitude * (max_height - min_height)))
                bar_height = max(min_height, min(bar_height, max_height))

                # CENTRATO VERTICALMENTE al 50%
                y_center = central_top + central_height // 2
                y_top = y_center - bar_height // 2
                y_bottom = y_center + bar_height // 2

                draw.rectangle([(x, y_top), (x + bar_width, y_bottom)], fill=colors['primary'])

    # Logo podcast CENTRATO VERTICALMENTE
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        logo_size = int(min(width, central_height) * 0.5)
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # CENTRATO VERTICALMENTE al 50%
        logo_x = (width - logo_size) // 2
        logo_y = central_top + (central_height - logo_size) // 2
        img.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    # Footer (20% altezza) - vuoto, senza titolo podcast e CTA
    footer_top = central_bottom
    footer_height = int(height * 0.20)
    footer_bottom = footer_top + footer_height
    draw.rectangle([(0, footer_top), (width, footer_bottom)], fill=colors['primary'])

    # Trascrizione in basso nell'area centrale
    if transcript_chunks:
        current_text = ""
        for chunk in transcript_chunks:
            if chunk['start'] <= current_time < chunk['end']:
                current_text = chunk['text']
                break

        if current_text:
            current_text = _strip_punctuation(current_text)
            try:
                font_transcript = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(height * 0.030))
            except:
                font_transcript = ImageFont.load_default()

            transcript_y = central_bottom - int(central_height * 0.15)
            style = _subtitle_default_style(colors)
            style['max_lines'] = min(style.get('max_lines', 5), 3)  # per square al massimo 3 righe
            max_width = int(width * style['width_ratio'])

            img, _ = _render_subtitle_lines(
                img,
                draw,
                current_text,
                font_transcript,
                transcript_y,
                max_width,
                style
            )
            draw = ImageDraw.Draw(img)

    return img


def create_horizontal_layout(img, draw, width, height, podcast_logo_path, podcast_title, episode_title,
                             waveform_data, current_time, transcript_chunks, audio_duration, colors):
    """
    Layout specifico per formato orizzontale 16:9 (1920x1080)
    Ottimizzato per YouTube
    Logo e waveform centrati verticalmente
    """
    progress_height = 0

    # Header (15% altezza) - vuoto, senza titolo episodio
    header_top = progress_height
    header_height = int(height * 0.15)
    draw.rectangle([(0, header_top), (width, header_top + header_height)], fill=colors['primary'])

    # Area centrale (68% altezza)
    central_top = header_top + header_height
    central_height = int(height * 0.68)
    central_bottom = central_top + central_height

    # Waveform CENTRATA VERTICALMENTE
    if waveform_data is not None and len(waveform_data) > 0:
        bar_spacing = 3
        bar_width = 12
        total_bar_width = bar_width + bar_spacing

        num_bars = width // total_bar_width
        if num_bars % 2 != 0:
            num_bars -= 1

        if num_bars >= 2:
            frame_idx = int((current_time / audio_duration) * len(waveform_data)) if audio_duration > 0 else 0
            frame_idx = min(frame_idx, len(waveform_data) - 1)
            current_amplitude = waveform_data[frame_idx]

            np.random.seed(42)
            sensitivities = np.random.uniform(0.6, 1.4, num_bars // 2)
            sensitivities = np.concatenate([sensitivities, sensitivities[::-1]])

            for i in range(num_bars):
                x = i * total_bar_width

                center_idx = num_bars // 2
                distance_from_center = abs(i - center_idx)
                center_boost = 1.0 + (1.0 - distance_from_center / center_idx) * 0.4 if center_idx > 0 else 1.0
                bar_amplitude = current_amplitude * sensitivities[i] * center_boost

                # Altezza minima ridotta per avere barre più sottili quando non c'è suono
                min_height = int(central_height * 0.03)
                max_height = int(central_height * 0.70)
                bar_height = int(min_height + (bar_amplitude * (max_height - min_height)))
                bar_height = max(min_height, min(bar_height, max_height))

                # CENTRATA VERTICALMENTE al 50%
                y_center = central_top + central_height // 2
                y_top = y_center - bar_height // 2
                y_bottom = y_center + bar_height // 2

                draw.rectangle([(x, y_top), (x + bar_width, y_bottom)], fill=colors['primary'])

    # Logo CENTRATO VERTICALMENTE
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        logo_size = int(min(width * 0.3, central_height * 0.6))
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # CENTRATO VERTICALMENTE al 50%
        logo_x = (width - logo_size) // 2
        logo_y = central_top + (central_height - logo_size) // 2
        img.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    # Footer (15% altezza) - vuoto, senza titolo podcast e CTA
    footer_top = central_bottom
    footer_height = height - footer_top
    draw.rectangle([(0, footer_top), (width, height)], fill=colors['primary'])

    # Trascrizione in basso nell'area centrale
    if transcript_chunks:
        current_text = ""
        for chunk in transcript_chunks:
            if chunk['start'] <= current_time < chunk['end']:
                current_text = chunk['text']
                break

        if current_text:
            current_text = _strip_punctuation(current_text)
            try:
                font_transcript = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(height * 0.030))
            except:
                font_transcript = ImageFont.load_default()

            # Spostato leggermente più in basso per aumentare distanza dal logo
            transcript_y = central_bottom - int(central_height * 0.12)
            style = _subtitle_default_style(colors)
            style['max_lines'] = min(style.get('max_lines', 5), 2)  # per horizontal max 2 righe
            max_width = int(width * style['width_ratio'])

            img, _ = _render_subtitle_lines(
                img,
                draw,
                current_text,
                font_transcript,
                transcript_y,
                max_width,
                style
            )
            draw = ImageDraw.Draw(img)

    return img


def create_audiogram_frame(width, height, podcast_logo_path, podcast_title, episode_title,
                           waveform_data, current_time, transcript_chunks, audio_duration, formats=None, colors=None, format_name='vertical'):
    """
    Crea un singolo frame dell'audiogram delegando al layout specifico per formato

    Args:
        width, height: Dimensioni del frame
        podcast_logo_path: Percorso logo podcast
        podcast_title: Titolo del podcast
        episode_title: Titolo dell'episodio
        waveform_data: Dati della waveform
        current_time: Tempo corrente in secondi
        transcript_chunks: Lista di chunk di trascrizione con timing
        audio_duration: Durata totale dell'audio
        colors: Dizionario con i colori personalizzati (opzionale)
        format_name: Nome del formato ('vertical', 'square', 'horizontal')
    """
    # Usa colori di default o personalizzati
    if colors is None:
        colors = {
            'primary': COLOR_ORANGE,
            'background': COLOR_BEIGE,
            'text': COLOR_WHITE,
            'transcript_bg': COLOR_BLACK
        }
    else:
        # Converti liste in tuple se necessario
        colors = {
            'primary': tuple(colors.get('primary', COLOR_ORANGE)),
            'background': tuple(colors.get('background', COLOR_BEIGE)),
            'text': tuple(colors.get('text', COLOR_WHITE)),
            'transcript_bg': tuple(colors.get('transcript_bg', COLOR_BLACK))
        }

    # Crea immagine di base
    img = Image.new('RGB', (width, height), colors['background'])
    draw = ImageDraw.Draw(img)

    # Delega al layout specifico per il formato
    if format_name == 'vertical':
        # Recupera safe area da configurazione formati (se presente)
        safe_area = None
        if formats and isinstance(formats, dict):
            fmt_cfg = formats.get('vertical') or formats.get(format_name)
            if isinstance(fmt_cfg, dict):
                safe_area = fmt_cfg.get('safe_area')
        # Flag debug per disegnare la safe area
        debug_draw = False
        if isinstance(fmt_cfg, dict):
            debug_draw = bool(fmt_cfg.get('debug_draw_safe_area', False))
        img = create_vertical_layout(img, draw, width, height, podcast_logo_path, podcast_title,
                                     episode_title, waveform_data, current_time, transcript_chunks,
                                     audio_duration, colors, safe_area=safe_area, debug_draw_safe_area=debug_draw)
    elif format_name == 'square':
        img = create_square_layout(img, draw, width, height, podcast_logo_path, podcast_title,
                                   episode_title, waveform_data, current_time, transcript_chunks,
                                   audio_duration, colors)
    elif format_name == 'horizontal':
        img = create_horizontal_layout(img, draw, width, height, podcast_logo_path, podcast_title,
                                       episode_title, waveform_data, current_time, transcript_chunks,
                                       audio_duration, colors)
    else:
        # Default: usa vertical
        img = create_vertical_layout(img, draw, width, height, podcast_logo_path, podcast_title,
                                     episode_title, waveform_data, current_time, transcript_chunks,
                                     audio_duration, colors)

    # Assicurati che l'array sia in RGB per MoviePy
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return np.array(img)


def generate_audiogram(audio_path, output_path, format_name, podcast_logo_path,
                      podcast_title, episode_title, transcript_chunks, duration,
                      formats=None, colors=None,
                      show_subtitles=True):
    """
    Genera un video audiogram completo

    Args:
        audio_path: Percorso del file audio
        output_path: Percorso del file video di output
        format_name: Nome del formato ('vertical', 'square', 'horizontal')
        podcast_logo_path: Percorso logo podcast
        podcast_title: Titolo del podcast
        episode_title: Titolo dell'episodio
        transcript_chunks: Lista di chunk di trascrizione con timing
        duration: Durata del video
        formats: Dizionario con i formati personalizzati (opzionale)
        colors: Dizionario con i colori personalizzati (opzionale)
    """
    # Usa formati personalizzati o di default
    if formats is None or format_name not in formats:
        width, height = FORMATS[format_name]
    else:
        format_config = formats[format_name]
        width = format_config.get('width', FORMATS[format_name][0])
        height = format_config.get('height', FORMATS[format_name][1])

    fps = 24  # Riduci da 30 a 24 fps per velocizzare

    print(f"  - Estrazione waveform...")
    # Estrai waveform una sola volta, campionata per frame
    waveform_data = get_waveform_data(audio_path, fps=fps)

    print(f"  - Pre-caricamento logo...")
    # Pre-carica e ridimensiona il logo una sola volta
    logo_img = None
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        central_height = int(height * 0.60)
        logo_size = int(min(width, central_height) * 0.4)
        logo_img = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

    print(f"  - Generazione frame video...")
    # Prepara chunks sottotitoli in base al flag
    chunks_for_render = transcript_chunks if show_subtitles else []
    # Funzione per generare frame
    def make_frame(t):
        return create_audiogram_frame(
            width, height,
            podcast_logo_path,  # Passiamo il path per compatibilità
            podcast_title,
            episode_title,
            waveform_data,
            t,
            chunks_for_render,
            duration,
            formats,
            colors,
            format_name,  # Passa il formato per usare il layout corretto
        )

    # Crea video clip
    video = VideoClip(make_frame, duration=duration)
    video.fps = fps

    print(f"  - Aggiunta audio...")
    # Aggiungi audio
    audio = AudioFileClip(audio_path)
    video = video.with_audio(audio)

    print(f"  - Rendering video...")
    # Esporta con threads per velocizzare
    video.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        fps=fps,
        threads=4,
        preset='medium'  # Bilancia velocità/qualità
    )
