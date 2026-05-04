"""
Power Plays Asset Fetcher v5
Complete rebuild based on full project review (Laws 1-20, 25).

Changes from v4:
  - Strips [brackets], cast tracker, and script metadata before parsing
  - Extracts [B-ROLL SUGGESTION:] content as high-quality search queries
  - Known single-word and stage name registry (Drake, 50 Cent, Jay-Z, etc.)
  - Dynamic scene queries — no more hardcoded Law 4 patterns
  - Expanded video scene patterns (halftime, sex tape, Oprah, prison, etc.)
  - Short quote filter (≤6 words without $ = likely song title / section header)
  - Per-episode output folders (auto-detected from filename)
  - 1080p minimum video quality
  - yt-dlp progress suppression
  - Expanded quote attribution verbs
  - Duplicate file detection

Install: pip install ddgs yt-dlp requests
Usage:  py asset_fetcher.py --script "Law 5.docx" --dry-run
        py asset_fetcher.py --script "Law 5.docx" --images-per 3
        py asset_fetcher_gui.py  (GUI mode)
"""

import os
import re
import sys
import json
import argparse
import time
import requests
from ddgs import DDGS

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  KNOWN NAMES REGISTRY
# ═══════════════════════════════════════════════════════════════════

# Single-word celebrities the regex pattern can't catch
KNOWN_SINGLE_NAMES = {
    'Drake', 'Beyoncé', 'Beyonce', 'Eminem', 'Bono', 'Banksy',
    'Rihanna', 'Adele', 'Lizzo', 'Zendaya', 'Madonna', 'Usher',
    'Shakira', 'Lorde', 'Pharrell',
    'Sia', 'Kesha', 'Beck', 'Pitbull', 'Ludacris',
    'Timbaland', 'Nelly', 'Ciara',
}

# Stage names, hyphenated names, number names, short names
# Maps variant spellings → canonical name
KNOWN_STAGE_NAMES = {
    '50 Cent': '50 Cent',
    'Jay-Z': 'Jay-Z', 'Jay Z': 'Jay-Z', 'JAY-Z': 'Jay-Z',
    'DJ Khaled': 'DJ Khaled',
    'Dr Dre': 'Dr Dre', 'Dr. Dre': 'Dr Dre',
    'Ja Rule': 'Ja Rule',
    'Kid Cudi': 'Kid Cudi',
    'Lil Wayne': 'Lil Wayne', 'Lil Nas X': 'Lil Nas X',
    'A$AP Rocky': 'ASAP Rocky', 'ASAP Rocky': 'ASAP Rocky',
    'MrBeast': 'MrBeast', 'Mr. Beast': 'MrBeast',
    'JoJo Siwa': 'JoJo Siwa',
    'Sacha Baron Cohen': 'Sacha Baron Cohen',
    'Tyler the Creator': 'Tyler the Creator',
    'Tyler, the Creator': 'Tyler the Creator',
    'Gucci Mane': 'Gucci Mane',
    'Metro Boomin': 'Metro Boomin',
    'Waka Flocka Flame': 'Waka Flocka Flame',
    'Meek Mill': 'Meek Mill',
    'Young Thug': 'Young Thug',
    'Nicki Minaj': 'Nicki Minaj',
    'Cardi B': 'Cardi B',
    'Ice Cube': 'Ice Cube',
    'Snoop Dogg': 'Snoop Dogg',
    'Kanye West': 'Kanye West',
    'The Rock': 'Dwayne Johnson',
    'Dwayne "The Rock" Johnson': 'Dwayne Johnson',
}


# ═══════════════════════════════════════════════════════════════════
#  SCRIPT PRE-PROCESSOR
# ═══════════════════════════════════════════════════════════════════

def preprocess_script(raw_text):
    """
    Clean script text before parsing:
    1. Extract B-ROLL SUGGESTION content (before stripping brackets)
    2. Strip [bracketed metadata] — FACT-CHECK FIX, POTENTIAL SHORT, ON SCREEN TEXT, etc.
    3. Strip the SERIES CAST TRACKER section (characters from OTHER episodes)
    4. Strip SCRIPT NOTES, PACKAGING, title options (not narrative content)
    """
    broll_queries = []
    onscreen_texts = []

    # 1. Extract B-ROLL SUGGESTION content BEFORE stripping brackets
    broll_matches = re.findall(
        r'\[B-ROLL SUGGESTION[S]?:\s*(.+?)\]',
        raw_text, re.IGNORECASE
    )
    for suggestion in broll_matches:
        for item in re.split(r'[;,]', suggestion):
            cleaned = item.strip()
            if len(cleaned) > 5:
                broll_queries.append(cleaned)

    # 1b. Extract ON SCREEN TEXT content BEFORE stripping brackets
    onscreen_matches = re.findall(
        r'\[ON SCREEN TEXT:\s*["\u201c]?(.+?)["\u201d]?\s*\]',
        raw_text, re.IGNORECASE
    )
    for ost in onscreen_matches:
        cleaned = ost.strip().strip('"').strip('\u201c\u201d')
        if len(cleaned) > 3:
            onscreen_texts.append(cleaned)

    # 2. Strip all bracketed metadata
    text = re.sub(r'`?\[.*?\]`?', '', raw_text)

    # 3. Strip everything after SERIES CAST TRACKER
    tracker_patterns = [
        r'##?\s*SERIES CAST TRACKER.*',
        r'##?\s*CAST TRACKER.*',
        r'##?\s*SCRIPT NOTES.*',
        r'##?\s*PACKAGING.*',
        r'\*\*Total unique lead/pattern.*',
    ]
    for pattern in tracker_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            text = text[:match.start()]

    # 4. Strip markdown formatting artifacts
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)       # italic
    text = re.sub(r'---+\s*Pause\s*---+', '', text, flags=re.IGNORECASE)  # ---Pause---
    text = re.sub(r'---+', '', text)                   # horizontal rules
    text = re.sub(r'##?\s+', '', text)                 # headers
    text = re.sub(r'\n{3,}', '\n\n', text)             # collapse multiple blank lines

    return text.strip(), broll_queries, onscreen_texts


# ═══════════════════════════════════════════════════════════════════
#  FILE READER
# ═══════════════════════════════════════════════════════════════════

def read_script_file(script_path):
    """Read text from .md, .txt, or .docx files."""
    ext = os.path.splitext(script_path)[1].lower()

    if ext == '.docx':
        from zipfile import ZipFile
        from xml.etree import ElementTree

        text_parts = []
        with ZipFile(script_path) as zf:
            with zf.open('word/document.xml') as xml_file:
                tree = ElementTree.parse(xml_file)
                root = tree.getroot()
                ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                for paragraph in root.iter(f'{ns}p'):
                    para_text = []
                    for run in paragraph.iter(f'{ns}r'):
                        text_elem = run.find(f'{ns}t')
                        if text_elem is not None and text_elem.text:
                            para_text.append(text_elem.text)
                    if para_text:
                        text_parts.append(''.join(para_text))
        return '\n'.join(text_parts)
    else:
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(script_path, 'r', encoding='latin-1') as f:
                return f.read()


# ═══════════════════════════════════════════════════════════════════
#  IMAGE FETCHER
# ═══════════════════════════════════════════════════════════════════

def download_images(query, max_results=2, output_folder="assets/images", query_type="general"):
    """Fetches images via DuckDuckGo. Retries on rate limit. query_type: person/location/document/general."""
    os.makedirs(output_folder, exist_ok=True)
    print(f"  🔍 Images: {query}")

    # Retry logic for DuckDuckGo rate limiting
    results = None
    for attempt in range(3):
        try:
            ddgs = DDGS()
            search_kwargs = {'max_results': max_results, 'safesearch': 'moderate'}
            if query_type == "location":
                search_kwargs['size'] = 'Large'
                search_kwargs['layout'] = 'Wide'
            elif query_type == "person":
                search_kwargs['type_image'] = 'photo'

            results = list(ddgs.images(query, **search_kwargs))
            break  # Success — exit retry loop
        except Exception as e:
            if attempt < 2:
                wait = (attempt + 1) * 3  # 3s, 6s
                print(f"    ⚠ Rate limited, retrying in {wait}s... (attempt {attempt + 1}/3)")
                time.sleep(wait)
            else:
                print(f"    ✗ Failed after 3 attempts: {e}")
                return []

    if not results:
        print(f"    ⚠ No results found")
        return []

    downloaded = []
    img_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://duckduckgo.com/',
    }
    for i, img in enumerate(results):
        img_url = img["image"]
        file_ext = img_url.split(".")[-1].split("?")[0]
        if len(file_ext) > 4:
            file_ext = "jpg"
        filename = f"{query.replace(' ', '_').lower()[:80]}_{i+1}.{file_ext}"
        filename = re.sub(r'[<>:"/\\|?*\'$]', '', filename)
        filepath = os.path.join(output_folder, filename)
        if os.path.exists(filepath):
            print(f"    ⏭ Already exists: {filename}")
            downloaded.append(filepath)
            continue
        try:
            img_data = requests.get(img_url, headers=img_headers, timeout=15).content
            with open(filepath, "wb") as f:
                f.write(img_data)
            print(f"    ✓ {filename}")
            downloaded.append(filepath)
        except Exception as e:
            print(f"    ✗ Failed: {e}")
    return downloaded


# ═══════════════════════════════════════════════════════════════════
#  VIDEO FETCHER
# ═══════════════════════════════════════════════════════════════════

def download_youtube_clip(query, max_results=1, output_folder="assets/videos"):
    """Uses yt-dlp to search and download. Minimum 1080p, no progress spam."""
    os.makedirs(output_folder, exist_ok=True)
    print(f"  🎬 Video: {query}")
    ydl_opts = {
        'format': 'bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a]/best[height>=1080]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        'outtmpl': f'{output_folder}/%(title)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
    }
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"ytsearch{max_results}:{query}"])
            print("    ✓ Download complete")
    except Exception as e:
        print(f"    ✗ Error: {e}")


# ═══════════════════════════════════════════════════════════════════
#  QUOTE / ARTICLE FETCHER
# ═══════════════════════════════════════════════════════════════════

def extract_quotes(text):
    """Extract sourced quotes — filters out song titles, section headers, dialogue."""
    quotes = []
    quote_patterns = [r'["\u201c]([^"\u201d]{10,200})["\u201d]']

    script_lines = {
        "i'm just here so i won't get fined",
        "you know why i'm here",
        "we're on to cincinnati",
        "the number represented a fair premium",
        "funding secured",
        "investor support is confirmed",
    }

    generic_patterns = [
        r'^(what|how|can you|do you|are you|is there|tell me|where)',
        r'^(you\'ve had|you\'re|you seem|you look)',
        r'^(we |i |my |let\'s)',
        r',?\s*can you\s',
    ]

    seen_quotes = set()

    for pattern in quote_patterns:
        for match in re.finditer(pattern, text):
            quote_text = match.group(1).strip()

            if len(quote_text) < 15:
                continue

            # Skip script structure words
            if any(skip in quote_text.lower() for skip in [
                'pause', 'power plays', 'next week', 'law ',
                'this is', 'every episode',
            ]):
                continue

            if quote_text.lower().rstrip('.!?,') in script_lines:
                continue

            # Skip generic dialogue
            is_generic = False
            for gp in generic_patterns:
                if re.match(gp, quote_text.strip(), re.IGNORECASE):
                    is_generic = True
                    break
            if is_generic:
                continue

            # Skip name-addressed questions
            if re.match(r'^[A-Z][a-z]+,\s', quote_text) and '?' in quote_text:
                continue

            # SHORT QUOTE FILTER: ≤6 words without $ = likely song title or header
            words = quote_text.split()
            if len(words) <= 6 and '$' not in quote_text:
                continue

            # QUALITY FILTER: needs distinctive searchable content
            has_proper_noun = bool(re.search(r'\b[A-Z][a-z]{2,}\b', quote_text))
            has_money = bool(re.search(r'\$[\d,.]+', quote_text))
            has_number = bool(re.search(r'\b\d{2,}\b', quote_text))
            has_specific_term = bool(re.search(
                r'(?:SEC|NFL|NBA|UFC|ESPN|CNN|FBI|MTV|Oprah|Grammy|Oscar|'
                r'Tesla|funding|secured|settlement|fraud|complaint|'
                r'shareholder|private|stock|tweet|fine|trademark|'
                r'doping|trafficking|indictment|verdict)',
                quote_text, re.IGNORECASE
            ))
            if not (has_money or has_number or has_specific_term):
                # Proper nouns alone aren't enough — too many false positives
                if not (has_proper_noun and len(words) > 10):
                    continue

            # Deduplicate
            normalized = quote_text.lower()[:50]
            if normalized in seen_quotes:
                continue
            seen_quotes.add(normalized)

            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end]
            source = identify_quote_source(quote_text, context)

            quotes.append({
                'text': quote_text,
                'context': context.strip(),
                'source': source,
            })

    # Document reference patterns (unquoted)
    doc_pats = [
        r'(?:complaint|filing|report|document|email)\s+(?:said|stated|quoted|showed|revealed|indicated)\s+(.{20,150}?)[.]',
        r'according to (?:the |his |her |their )?(?:complaint|filing|report|email)[,:]?\s+(.{20,150}?)[.]',
    ]
    for pattern in doc_pats:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            claim = match.group(1).strip()
            start = max(0, match.start() - 100)
            context = text[start:match.end() + 100]
            quotes.append({
                'text': claim,
                'context': context.strip(),
                'source': 'document reference',
            })

    return quotes


def identify_quote_source(quote_text, context):
    """Try to figure out who said a quote or where it came from."""
    attribution_patterns = [
        r'(\w+ \w+)\s+(?:said|stated|testified|wrote|tweeted|posted|told|asked|replied|acknowledged|admitted|recalled|described|disclosed|revealed|confirmed|noted|observed|explained|insisted|argued|confessed|conceded|maintained)',
        r'(?:said|stated|testified|wrote|tweeted|told|acknowledged|admitted|revealed|confirmed)\s+(\w+ \w+)',
        r"(?:SEC|SEC's|complaint|filing|report|email)\s+(?:said|stated|quoted)",
    ]
    for pattern in attribution_patterns:
        match = re.search(pattern, context, re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex else 'SEC/legal document'
    return 'unknown'


def search_for_article(quote_text, source_hint="", people=None):
    """Search DuckDuckGo for articles containing a specific quote."""
    words = quote_text.split()
    if len(words) > 8:
        start = len(words) // 4
        search_chunk = ' '.join(words[start:start+8])
    else:
        search_chunk = quote_text

    query = f'"{search_chunk}"'

    if source_hint and source_hint not in ('unknown', 'document reference'):
        query += f' {source_hint}'

    # Add nearest person name from context
    if people:
        for person in people:
            last = person.split()[-1] if ' ' in person else person
            if last.lower() in quote_text.lower() and last not in query:
                query += f' {person}'
                break

    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=3))
        return results
    except Exception as e:
        print(f"    ✗ Search error: {e}")
        return []


def fetch_article(url, output_folder="assets/articles"):
    """Download an article page as HTML. Full browser headers to avoid 403s."""
    os.makedirs(output_folder, exist_ok=True)

    filename = re.sub(r'https?://(www\.)?', '', url)
    filename = re.sub(r'[<>:"/\\|?*#]', '_', filename)
    filename = filename[:100] + '.html'
    filepath = os.path.join(output_folder, filename)

    if os.path.exists(filepath):
        return filepath

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        with open(filepath, 'w', encoding='utf-8', errors='replace') as f:
            f.write(resp.text)
        return filepath
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 'unknown'
        if status == 403:
            print(f"    ⚠ Blocked by {url.split('/')[2]} (403 Forbidden)")
        else:
            print(f"    ✗ HTTP {status}: {url.split('/')[2]}")
        return None
    except Exception as e:
        print(f"    ✗ Failed to fetch article: {e}")
        return None


def process_quotes(quotes, output_folder="assets", people=None):
    """Search for articles containing quotes, download them, create index."""
    articles_folder = os.path.join(output_folder, "articles")
    results = []

    for i, quote in enumerate(quotes):
        print(f"  📰 Quote {i+1}/{len(quotes)}: \"{quote['text'][:60]}...\"")
        search_results = search_for_article(quote['text'], quote['source'], people)

        if not search_results:
            print(f"    ⚠ No articles found")
            results.append({'quote': quote['text'], 'source': quote['source'], 'articles': []})
            continue

        fetched_articles = []
        for result in search_results[:2]:
            url = result.get('href') or result.get('link', '')
            title = result.get('title', 'Unknown')
            snippet = result.get('body', '')
            if not url:
                continue
            print(f"    → {title[:70]}")
            filepath = fetch_article(url, articles_folder)
            fetched_articles.append({
                'title': title, 'url': url,
                'snippet': snippet, 'local_file': filepath,
            })

        results.append({
            'quote': quote['text'], 'source': quote['source'],
            'articles': fetched_articles,
        })
        time.sleep(1)

    index_path = os.path.join(output_folder, "quotes.md")
    write_quote_index(results, index_path)
    return results


def write_quote_index(results, filepath):
    """Write markdown file mapping quotes to source articles."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("# Quote Sources\n\n")
        f.write("Quotes extracted from the script mapped to their source articles.\n\n---\n\n")
        for i, item in enumerate(results, 1):
            f.write(f"## Quote {i}\n\n> {item['quote']}\n\n")
            f.write(f"**Attributed to:** {item['source']}\n\n")
            if item['articles']:
                f.write("**Sources found:**\n\n")
                for article in item['articles']:
                    f.write(f"- [{article['title']}]({article['url']})\n")
                    if article.get('local_file'):
                        f.write(f"  - Local: `{article['local_file']}`\n")
                    if article.get('snippet'):
                        f.write(f"  - Preview: {article['snippet'][:150]}...\n")
                f.write("\n")
            else:
                f.write("**No source articles found.**\n\n")
            f.write("---\n\n")
    print(f"    📝 Quote index saved: {filepath}")


# ═══════════════════════════════════════════════════════════════════
#  PEOPLE EXTRACTION
# ═══════════════════════════════════════════════════════════════════

NOISE_WORDS = {
    'The', 'This', 'That', 'These', 'Those', 'What', 'When', 'Where',
    'Who', 'Why', 'How', 'And', 'But', 'Or', 'Not', 'If', 'In', 'On',
    'At', 'To', 'For', 'Of', 'With', 'From', 'By', 'As', 'Is', 'It',
    'Are', 'Was', 'Were', 'Be', 'Been', 'Being', 'Have', 'Has', 'Had',
    'Do', 'Does', 'Did', 'Will', 'Would', 'Could', 'Should', 'May',
    'Might', 'Must', 'Shall', 'Can', 'Need', 'So', 'No', 'Yes',
    'All', 'Each', 'Every', 'Both', 'Few', 'More', 'Most', 'Other',
    'Some', 'Such', 'Only', 'Own', 'Same', 'Than', 'Too', 'Very',
    'Just', 'Because', 'Before', 'After', 'While', 'During', 'About',
    'Between', 'Through', 'Above', 'Below', 'Again', 'Then', 'Once',
    'Here', 'There', 'Also', 'Now', 'They', 'Their', 'Them', 'He',
    'She', 'His', 'Her', 'Him', 'You', 'Your', 'We', 'Our', 'My',
    'Me', 'I', 'Think', 'Look', 'Want', 'Give', 'Take', 'Make',
    'Know', 'Even', 'Still', 'Already', 'Never', 'Always', 'Sometimes',
    'Imagine', 'Remember', 'Consider', 'Notice', 'Watch', 'Yet',
    'Meanwhile', 'However', 'Instead', 'Rather', 'One', 'Two', 'Three',
    'Four', 'Five', 'First', 'Second', 'Try', 'Every', 'Another',
    'Nothing', 'Something', 'Everything', 'Anyone', 'Someone',
    'Which', 'Whose', 'Where', 'Zero', 'Over', 'Under', 'Into',
    'Show', 'Answer', 'Said', 'Asked', 'Told',
}

NOISE_PHRASES = {
    'power plays', 'law', 'defense', 'debate', 'cold open', 'hook',
    'pause', 'next week', 'much depends', 'guard it', 'say less',
    'am athlete', 'beast mode', 'funding secured', 'investor support',
    'say more', 'every episode', 'on one side', 'on the other',
    'picture this', 'from prison', 'best friend', 'dangerous person',
    'wrong person', 'type one', 'type two', 'type three',
    'camp cupcake', 'for janet', 'remember janet', 'rock your',
    'tape that', 'fox didn', 'simple life', 'stars are', 'gonna have',
    'sold over', 'nine sixteenths', 'keep it simple',
}

NAME_PATTERN = re.compile(
    r'\b([A-Z][a-z]{2,15})\s+((?:van |de |von |de la )?[A-Z][a-z]{2,20})\b'
)

FALSE_FIRST_NAMES = {
    'But', 'So', 'The', 'And', 'Or', 'Yet', 'Now', 'Then', 'Just',
    'Every', 'After', 'Before', 'When', 'Where', 'While', 'Since',
    'Once', 'Still', 'Also', 'Here', 'There', 'Most', 'Some',
    'That', 'This', 'These', 'Those', 'Each', 'Such',
    'Super', 'Public', 'New', 'San', 'Los', 'Las', 'United',
    'National', 'American', 'General', 'Federal', 'Royal',
    'Best', 'Keep', 'Get', 'Win', 'Use', 'Learn', 'Never', 'Too',
    'Type', 'Wrong', 'Faster', 'Less', 'Four', 'Crush', 'Destroy',
    'Ruin', 'Conceal', 'Your', 'From', 'Sent', 'Living', 'Sports',
    'Comedy', 'Postal', 'Sequential', 'Sunday', 'Tour', 'Camp',
    'Puppy', 'Golden', 'Western',
    'Fox', 'Grammy', 'Television', 'Radio', 'Rock', 'Simple',
    'Tape', 'For', 'Remember', 'Wall', 'Street', 'Rolling',
    'Stone', 'Daily', 'Weekly', 'Monthly', 'Annual', 'World',
    'International', 'Global', 'Central', 'Social', 'Digital',
    'Modern', 'Classic', 'Grand', 'Major', 'Minor', 'Real',
    'Big', 'Top', 'Hot', 'Old', 'Young', 'High', 'Low',
    'Last', 'Next', 'Half', 'Full', 'Free', 'Open', 'Closed',
    'Long', 'Short', 'Hard', 'Sold', 'Gonna', 'Stars',
    'Bad', 'Good', 'True', 'False', 'Right', 'Left', 'Same',
    'Other', 'Both', 'Only', 'First', 'Second', 'Third',
    'Nine', 'Ten', 'Hundred', 'Thousand', 'Million', 'Billion',
    # Final audit additions
    'Murder', 'Talk', 'Ice', 'Cheese', 'Orange', 'Net', 'Wire',
    'Adult', 'Black', 'White', 'Clone', 'Warrior', 'Grand',
    'Red', 'Blue', 'Green', 'Dead', 'Dark', 'Bright', 'Clear',
}

KNOWN_NON_PEOPLE = {
    'Super Bowl', 'Saudi Arabia', 'San Francisco', 'New England',
    'United States', 'New York', 'Los Angeles', 'Golden State',
    'Camp Cupcake', 'Power Plays', 'Beast Mode', 'Public Investment',
    'Comedy Central', 'Sports Illustrated', 'Sunday Times',
    'Postal Service', 'Sequential Brands', 'Living Omnimedia',
    'Gallo Winery', 'Alameda Research', 'Tour de France',
    'Puppy Bowl', 'Golden State Warriors', 'Western Conference',
    'Western Conference Finals', 'Saint Pablo',
    'Grammy Awards', 'Television Council', 'Simple Life',
    'Fox News', 'Wall Street', 'Rolling Stone',
    'Bad Boy', 'Bad Boy Records', 'Murder Inc',
    'From Prison', 'Sent Twitter', 'Potluck Dinner',
    'Best Friend', 'Billion Friendship', 'Wrong Person',
    'Dangerous Person', 'For Janet', 'Remember Janet',
    'Rock Your', 'Tape That', 'Fox Didn', 'Stars Are',
    'Sold Over', 'Gonna Have',
    'Adult Survivors', 'Global Icon',
    # Final audit additions
    'Murder Inc', 'Hot Ones', 'Grand Slam', 'World Cup',
    'Wire Fraud', 'Net Worth', 'Black Card', 'Orange Tiles',
    'Clone Conspiracy', 'Warrior Monk', 'Cheese Sandwich',
    'Ice Cream', 'Talk Show',
}


def is_noise(phrase):
    lower = phrase.lower().strip()
    if lower in NOISE_PHRASES:
        return True
    words = phrase.split()
    if all(w in NOISE_WORDS for w in words):
        return True
    if len(words) == 1 and len(words[0]) < 4:
        return True
    return False


def extract_people(text):
    """Extract people using regex + known names registry + teleprompter detection."""
    people = set()

    # 1. Known single-word names
    for name in KNOWN_SINGLE_NAMES:
        if re.search(rf'\b{re.escape(name)}\b', text):
            people.add(name)

    # 2. Known stage names (multi-word, hyphenated, number-prefixed)
    for variant, canonical in KNOWN_STAGE_NAMES.items():
        if variant in text:
            people.add(canonical)

    # 3. Standard two-word name pattern
    candidates = {}
    for match in NAME_PATTERN.finditer(text):
        full = match.group(0)
        first_word = full.split()[0]
        if is_noise(full) or first_word in FALSE_FIRST_NAMES or full in KNOWN_NON_PEOPLE:
            continue
        candidates[full] = candidates.get(full, 0) + 1

    person_verbs = [
        'said', 'asked', 'told', 'tweeted', 'testified', 'explained',
        'posted', 'announced', 'filed', 'settled', 'responded', 'replied',
        'published', 'wrote', 'claimed', 'argued', 'stated', 'denied',
        'sat', 'walked', 'hated', 'made', 'earned', 'spent',
        'chose', 'sent', 'met', 'discussed', 'played', 'kept',
        'showed', 'hit', 'fined', 'acknowledged', 'admitted', 'recalled',
        'confessed', 'conceded', 'insisted', 'maintained', 'described',
    ]

    for name, count in candidates.items():
        if count >= 2:
            people.add(name)
            continue
        for verb in person_verbs:
            pattern = rf'{re.escape(name)}\s+{verb}\b|\b{verb}\s+.*?{re.escape(name)}'
            if re.search(pattern, text, re.IGNORECASE):
                people.add(name)
                break

    # Teleprompter style: full name once, then last name only
    for name, count in candidates.items():
        if name in people:
            continue
        last_name = name.split()[-1]
        last_name_count = len(re.findall(rf"\b{re.escape(last_name)}(?:'s)?\b", text))
        if last_name_count >= 2:
            people.add(name)

    return sorted(people)


# ═══════════════════════════════════════════════════════════════════
#  ORGANIZATION EXTRACTION
# ═══════════════════════════════════════════════════════════════════

def extract_organizations(text, people):
    org_patterns = [
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:were|was|had|is|are)\b',
        r'\bthe\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b',
    ]
    candidates = {}
    for pattern in org_patterns:
        for match in re.finditer(pattern, text):
            full = match.group(1)
            if is_noise(full) or full in people:
                continue
            words = full.split()
            if len(words) < 2 or all(w in NOISE_WORDS for w in words):
                continue
            if full in KNOWN_NON_PEOPLE:
                pass
            if (len(words) == 2 and all(w.isalpha() and len(w) <= 10 for w in words)
                    and full not in KNOWN_NON_PEOPLE
                    and not any(ind in full.lower() for ind in ['patriots', 'seahawks', 'fund', 'office', 'records', 'warriors'])):
                continue
            candidates[full] = candidates.get(full, 0) + 1

    org_indicators = [
        'team', 'league', 'brand', 'company', 'fund', 'office',
        'commission', 'stock', 'partnership', 'playing', 'patriots',
        'seahawks', 'nfl', 'sec', 'tesla', 'nasdaq', 'records',
        'warriors', 'label', 'network', 'studio',
    ]
    orgs = set()
    for name, count in candidates.items():
        if count >= 2:
            orgs.add(name)
            continue
        for indicator in org_indicators:
            if indicator.lower() in text.lower():
                window = text[max(0, text.find(name)-200):text.find(name)+200]
                if indicator.lower() in window.lower():
                    orgs.add(name)
                    break
    return sorted(orgs)


# ═══════════════════════════════════════════════════════════════════
#  SCENE / LOCATION / OBJECT EXTRACTION
# ═══════════════════════════════════════════════════════════════════

def extract_scenes(text, people, broll_queries, onscreen_texts=None):
    """
    Build scene queries from:
    1. B-ROLL SUGGESTION content (extracted during preprocessing)
    2. ON SCREEN TEXT items (for visual context)
    3. Dynamic document/legal/brand patterns tied to nearest person
    4. Dynamic visual moment patterns tied to nearest person
    5. Money/headline events tied to nearest person
    6. Dynamic theme patterns
    """
    scene_queries = []

    def nearest_person(position):
        best = None
        best_dist = 999999
        for person in people:
            last_name = person.split()[-1] if ' ' in person else person
            for name_form in [person, last_name]:
                for m in re.finditer(re.escape(name_form), text, re.IGNORECASE):
                    dist = abs(m.start() - position)
                    if dist < best_dist:
                        best_dist = dist
                        best = person
        return best if best_dist < 500 else None

    # 1. B-ROLL SUGGESTIONS (highest quality — written by Michael)
    scene_queries.extend(broll_queries)

    # 2. ON SCREEN TEXT items — search for the visual context behind them
    if onscreen_texts:
        for ost in onscreen_texts:
            # Find what person/topic this on-screen text relates to
            idx = text.find(ost) if ost in text else -1
            if idx == -1:
                # Try a partial match (text was cleaned, might not match exactly)
                for word in ost.split()[:3]:
                    found = text.find(word)
                    if found >= 0:
                        idx = found
                        break
            person = nearest_person(idx) if idx >= 0 else None
            if person:
                scene_queries.append(f"{person} {ost}")

    # 2. Documents, filings, legal materials — dynamic
    doc_patterns = [
        (r'\bSEC\b.*(?:complaint|filing|lawsuit|charged)', 'SEC complaint filing'),
        (r'fraud settlement', 'fraud settlement'),
        (r'trademark.*(?:filed|approved|office)', 'trademark filing'),
        (r'(?:fined|fine)\b.*(?:violation|policy|\$)', 'fine'),
        (r'lawsuit|sued|suing', 'lawsuit'),
        (r'subpoena|deposition', 'deposition'),
        (r'indicted|indictment', 'indictment'),
        (r'convicted|verdict|sentenced', 'conviction verdict'),
        (r'arrested|arrest', 'arrest'),
        (r'settlement.*\$|settled.*\$', 'settlement'),
    ]
    for pattern, label in doc_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            person = nearest_person(match.start())
            scene_queries.append(f"{person} {label}" if person else label)

    # 3. Brands / merchandise — dynamic
    brand_patterns = [
        (r'(?:clothing|fashion|merchandise)\s*(?:brand|line|empire)', 'brand merchandise'),
        (r'pop-up shop', 'pop-up shop'),
        (r'Fanatics.*partnership|Fanatics.*deal', 'Fanatics partnership'),
    ]
    for pattern, label in brand_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            person = nearest_person(match.start())
            scene_queries.append(f"{person} {label}" if person else label)

    # 4. Visual moments — dynamic (no more hardcoded Law 4 queries)
    visual_patterns = [
        (r'stock.*(?:jumped|halted|crashed|surged|plummeted)', 'stock chart'),
        (r'tweet.*screenshot|screenshot.*tweet', 'tweet screenshot'),
        (r'blog post', 'blog post'),
        (r'dashcam|bodycam|surveillance.*footage|hotel.*footage', 'surveillance footage'),
        (r'mugshot', 'mugshot'),
        (r'magazine.*cover|cover.*magazine', 'magazine cover'),
    ]
    for pattern, label in visual_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            person = nearest_person(match.start())
            # Find a year nearby
            nearby_text = text[max(0, match.start()-100):match.end()+100]
            years = re.findall(r'\b(20[0-2]\d)\b', nearby_text)
            year_str = f" {years[0]}" if years else ""
            scene_queries.append(f"{person} {label}{year_str}" if person else f"{label}{year_str}")

    # 5. Money / headline events
    money_events = re.findall(
        r'(?:fined|settled|cost|earned|generated|moved|worth|paid|lost)\s+(?:.*?)(\$[\d,.]+\s*(?:million|billion|thousand)?)',
        text, re.IGNORECASE
    )
    seen_amounts = set()
    for amount in money_events[:5]:
        if amount in seen_amounts:
            continue
        seen_amounts.add(amount)
        idx = text.lower().find(amount.lower())
        if idx > 0:
            person = nearest_person(idx)
            if person:
                scene_queries.append(f"{person} {amount} news")

    # 6. Theme images — dynamic
    theme_patterns = [
        (r'courtroom|under oath|testified|trial', 'courtroom testimony'),
        (r'(?:press conference|podium).*(?:media|NFL|NBA)', 'press conference podium'),
        (r'prison|incarcerat|jail', 'prison'),
        (r'red carpet', 'red carpet'),
        (r'paparazzi', 'paparazzi'),
        (r'Super Bowl.*(?:halftime|media day)', 'Super Bowl'),
    ]
    for pattern, label in theme_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            person = nearest_person(match.start())
            scene_queries.append(f"{person} {label}" if person else label)

    return list(dict.fromkeys(scene_queries))


# ═══════════════════════════════════════════════════════════════════
#  QUERY BUILDERS
# ═══════════════════════════════════════════════════════════════════

def build_image_queries(text, people, orgs, scenes):
    """Build typed image queries from people + orgs + scenes."""
    queries = []

    event_keywords = {
        'tweet': ('tweet', 'document'), 'tweeted': ('tweet', 'document'),
        'courtroom': ('court testimony', 'person'),
        'court': ('court', 'person'),
        'testified': ('testimony', 'person'),
        'deposition': ('deposition', 'person'),
        'oath': ('testimony', 'person'),
        'podium': ('press conference', 'person'),
        'press conference': ('press conference', 'person'),
        'media day': ('media day', 'person'),
        'super bowl': ('Super Bowl', 'person'),
        'interview': ('interview', 'person'),
        'podcast': ('podcast', 'person'),
        'settlement': ('settlement', 'document'),
        'fined': ('fine', 'document'),
        'trademark': ('trademark', 'document'),
        'merchandise': ('merchandise', 'general'),
        'brand': ('brand', 'general'),
        'halftime': ('halftime show', 'person'),
        'prison': ('prison', 'person'),
        'arrested': ('arrest', 'person'),
    }

    for person in people:
        queries.append((person, 'person'))
        # Search with full name AND last name (teleprompter style)
        last_name = person.split()[-1] if ' ' in person else person
        name_patterns = [re.escape(person)]
        if last_name != person:
            name_patterns.append(re.escape(last_name))
        
        all_sentences = []
        for np in name_patterns:
            all_sentences.extend(
                re.findall(rf'[^.!?\n]*{np}[^.!?\n]*[.!?]', text, re.IGNORECASE)
            )
        
        added_contexts = set()
        for sentence in set(all_sentences):
            for keyword, (context, qtype) in event_keywords.items():
                if keyword.lower() in sentence.lower() and context not in added_contexts:
                    queries.append((f"{person} {context}", qtype))
                    added_contexts.add(context)
            years = re.findall(r'\b(20[0-2]\d)\b', sentence)
            for year in years:
                year_query = f"{person} {year}"
                if year_query not in [q[0] for q in queries]:
                    queries.append((year_query, 'person'))

    for org in orgs:
        queries.append((org, 'general'))

    # Classify scene queries
    location_kw = ['factory', 'center', 'stadium', 'arena', 'podium',
                    'locker room', 'courtroom', 'prison', 'jail', 'red carpet']
    document_kw = ['SEC', 'complaint', 'filing', 'settlement', 'trademark',
                    'fine', 'chart', 'tweet', 'screenshot', 'blog post',
                    'stock', 'email', 'indictment', 'verdict', 'mugshot']

    for scene in scenes:
        scene_lower = scene.lower()
        has_person = any(
            p.lower() in scene_lower or (p.split()[-1].lower() if ' ' in p else p.lower()) in scene_lower
            for p in people
        )
        if has_person and any(kw in scene_lower for kw in
                              ['testimony', 'courtroom', 'trial', 'press conference',
                               'media day', 'interview', 'podcast', 'halftime',
                               'prison', 'arrest', 'red carpet', 'paparazzi']):
            queries.append((scene, 'person'))
        elif any(kw in scene_lower for kw in document_kw):
            queries.append((scene, 'document'))
        elif any(kw in scene_lower for kw in location_kw):
            queries.append((scene, 'location'))
        else:
            queries.append((scene, 'general'))

    seen = set()
    deduped = []
    for query, qtype in queries:
        if query not in seen:
            seen.add(query)
            deduped.append((query, qtype))
    return deduped


def build_video_queries(text, people):
    """Build video queries from person+event patterns with topic context."""
    queries = []

    # Patterns that are specific enough on their own — no extra context needed
    specific_patterns = [
        (r'press conference', '{person} press conference'),
        (r'media day', '{person} media day'),
        (r'podcast', '{person} podcast'),
        (r'Oprah.*interview|interview.*Oprah|told Oprah|Oprah.*confession', '{person} Oprah interview'),
        (r'roast|Comedy Central', '{person} roast'),
        (r'halftime|half-time', '{person} halftime show'),
        (r'sex tape|leaked.*tape', '{person} sex tape scandal'),
        (r'\bdoping\b|\bPED\b|\bsteroids\b', '{person} doping scandal'),
        (r'deposition.*video|video.*deposition', '{person} deposition video'),
        (r'Super Bowl', '{person} Super Bowl'),
    ]

    # Patterns that are too generic alone — need topic context from the sentence
    # "Elon Musk confession" → "Elon Musk Tesla funding secured confession"
    generic_patterns = [
        (r'testified|testimony|courtroom|deposition|under oath', 'testimony'),
        (r'keynote|presentation|stage', 'keynote'),
        (r'postgame|post-game|after the game', 'postgame'),
        (r'rant', 'rant'),
        (r'confession|confessed|admitted|admit', 'confession'),
        (r'apolog|sorry', 'apology'),
        (r'interview', 'interview'),
        (r'trial|convicted|verdict|sentenced', 'trial'),
        (r'comeback|returned|return', 'comeback'),
        (r'scandal|controversy|accused', 'scandal'),
        (r'(?:concert|live show|on stage|played a set|music festival)', 'concert performance'),
        (r'award|Grammy|Oscar|Emmy', 'award speech'),
        (r'fired|resign|stepped down', 'resignation'),
        (r'arrest|charged|indicted', 'arrest'),
        (r'debut|launch|unveil', 'launch'),
        (r'prison|jail|incarcerat|released from', 'prison release'),
        (r'walkoff|walked off|walks off|storms off', 'walks off'),
        (r'meme|went viral|viral.*moment', 'viral moment'),
    ]

    # Topic words to extract from sentences for context
    # These are nouns/proper nouns that make a query specific
    TOPIC_STOPWORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
        'for', 'of', 'with', 'by', 'from', 'is', 'was', 'are', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
        'not', 'no', 'so', 'if', 'when', 'where', 'how', 'what', 'who',
        'which', 'that', 'this', 'these', 'those', 'it', 'its', 'he',
        'she', 'him', 'her', 'his', 'they', 'them', 'their', 'we', 'our',
        'you', 'your', 'my', 'me', 'i', 'about', 'after', 'before',
        'because', 'just', 'also', 'even', 'still', 'than', 'then',
        'said', 'told', 'asked', 'made', 'went', 'got', 'had', 'been',
        'every', 'never', 'always', 'here', 'there', 'more', 'most',
        'time', 'didn', 'doesn', 'wasn', 'wouldn', 'couldn',
        'same', 'something', 'nothing', 'everything', 'anyone',
        'into', 'over', 'under', 'between', 'through', 'during',
        'first', 'second', 'third', 'last', 'next', 'other', 'another',
        'much', 'many', 'some', 'any', 'all', 'both', 'each', 'every',
        'only', 'own', 'very', 'already', 'too', 'now', 'again',
        # Verbs that add no search value
        'saying', 'telling', 'going', 'coming', 'making', 'taking',
        'getting', 'doing', 'being', 'having', 'trying', 'keeping',
        'using', 'finding', 'giving', 'knowing', 'thinking', 'looking',
        'wanting', 'seeing', 'showing', 'leaving', 'calling', 'running',
        'talking', 'asking', 'working', 'playing', 'moving', 'living',
        'starting', 'turning', 'explaining', 'described', 'became',
        'happened', 'became', 'against', 'quoted', 'directly',
        'behind', 'while', 'until', 'back', 'down', 'away',
        'years', 'year', 'months', 'days', 'hours', 'minutes',
        'later', 'earlier', 'ever', 'since', 'long', 'enough',
    }

    def extract_topic(sentence, person):
        """Pull 1-2 distinctive proper nouns or entities from a sentence."""
        cleaned = sentence
        last_name = person.split()[-1] if ' ' in person else person
        cleaned = re.sub(re.escape(person), '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(re.escape(last_name), '', cleaned, flags=re.IGNORECASE)

        words = re.findall(r'[A-Za-z]{3,}', cleaned)
        # Only keep proper nouns (capitalized mid-sentence) and known entities
        topics = []
        for w in words:
            if w.lower() in TOPIC_STOPWORDS:
                continue
            if w[0].isupper() and w not in FALSE_FIRST_NAMES:
                topics.append(w)

        # Take at most 2 topic words
        return ' '.join(topics[:2]) if topics else ''

    for person in people:
        last_name = person.split()[-1] if ' ' in person else person
        name_patterns = [re.escape(person)]
        if last_name != person:
            name_patterns.append(re.escape(last_name))

        all_sentences = []
        for np in name_patterns:
            all_sentences.extend(
                re.findall(rf'[^.!?\n]*{np}[^.!?\n]*[.!?]', text, re.IGNORECASE)
            )
        unique_sentences = list(set(all_sentences))
        person_text = ' '.join(unique_sentences)

        added = set()

        # Specific patterns — check at sentence level, not joined text
        for pattern, query_template in specific_patterns:
            sentence_match = False
            for s in unique_sentences:
                if not re.search(pattern, s, re.IGNORECASE):
                    continue
                # Verify person is in THIS sentence
                for np in name_patterns:
                    if re.search(np, s, re.IGNORECASE):
                        sentence_match = True
                        break
                if sentence_match:
                    break
            if sentence_match:
                query = query_template.format(person=person)
                if query not in added:
                    queries.append(query)
                    added.add(query)

        # Generic patterns — add topic context, skip if no relevant context found
        for pattern, label in generic_patterns:
            # Only match sentences where BOTH the person's name AND the pattern appear
            matching_sentences = []
            for s in unique_sentences:
                if not re.search(pattern, s, re.IGNORECASE):
                    continue
                # Verify the person is actually mentioned in this specific sentence
                person_in_sentence = False
                for np in name_patterns:
                    if re.search(np, s, re.IGNORECASE):
                        person_in_sentence = True
                        break
                if person_in_sentence:
                    matching_sentences.append(s)
            if matching_sentences:
                # Get topic from the first matching sentence
                topic = extract_topic(matching_sentences[0], person)
                if topic:
                    query = f"{person} {topic} {label}"
                else:
                    # No proper nouns in context — only include if the pattern
                    # keyword appears within 50 chars of the person's name in that sentence
                    sentence = matching_sentences[0]
                    last = person.split()[-1] if ' ' in person else person
                    name_pos = sentence.lower().find(last.lower())
                    pattern_match = re.search(pattern, sentence, re.IGNORECASE)
                    if pattern_match and name_pos >= 0:
                        distance = abs(pattern_match.start() - name_pos)
                        if distance < 80:
                            query = f"{person} {label}"
                        else:
                            continue  # Too far apart — probably about someone else
                    else:
                        query = f"{person} {label}"
                if query not in added:
                    queries.append(query)
                    added.add(query)

    return list(dict.fromkeys(queries))


# ═══════════════════════════════════════════════════════════════════
#  MASTER PARSER
# ═══════════════════════════════════════════════════════════════════

def parse_script(script_path):
    raw_text = read_script_file(script_path)
    text, broll_queries, onscreen_texts = preprocess_script(raw_text)

    print(f"\n📄 Parsing script: {os.path.basename(script_path)}")
    print(f"   {len(text)} characters, ~{len(text.split())} words")
    if broll_queries:
        print(f"   📋 {len(broll_queries)} B-ROLL suggestions extracted")
    if onscreen_texts:
        print(f"   📺 {len(onscreen_texts)} ON SCREEN TEXT items extracted")
    print()

    people = extract_people(text)
    orgs = extract_organizations(text, people)
    scenes = extract_scenes(text, people, broll_queries, onscreen_texts)
    quotes = extract_quotes(text)
    image_queries = build_image_queries(text, people, orgs, scenes)
    video_queries = build_video_queries(text, people)

    return {
        'people': people,
        'organizations': orgs,
        'scenes': scenes,
        'quotes': quotes,
        'image_queries': image_queries,
        'video_queries': video_queries,
    }


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def detect_law_number(script_path):
    """Auto-detect law number from filename for per-episode folders."""
    match = re.search(r'law[_\s-]*(\d+)', os.path.basename(script_path), re.IGNORECASE)
    return match.group(1) if match else None


def run_manual():
    print("\n── Manual Mode ──\n")
    download_images("Mark Zuckerberg Senate Hearing 2024", max_results=2)
    download_youtube_clip("Tim Cook CNBC interview snippet", max_results=1)


def run_script_mode(script_path, images_per=2, videos_per=1, output="assets", dry_run=False):
    parsed = parse_script(script_path)

    # Auto per-episode folder
    law_num = detect_law_number(script_path)
    if law_num:
        output = os.path.join(output, f"law-{law_num}")
        print(f"   📁 Output folder: {output}/")

    print(f"── Extracted from script ──")
    print(f"   People:         {', '.join(parsed['people']) or 'none found'}")
    print(f"   Organizations:  {', '.join(parsed['organizations']) or 'none found'}")
    print(f"   Scene queries:  {len(parsed['scenes'])}")
    print(f"   Quotes found:   {len(parsed['quotes'])}")
    print(f"   Image queries:  {len(parsed['image_queries'])}")
    print(f"   Video queries:  {len(parsed['video_queries'])}")

    if dry_run:
        print(f"\n── Dry Run — would fetch: ──\n")
        print("  Images:")
        for q, qtype in parsed['image_queries']:
            print(f"    • {q}  ({images_per} images, {qtype})")
        print("\n  Videos:")
        for q in parsed['video_queries']:
            print(f"    • {q}  ({videos_per} clips)")
        print(f"\n  Quotes ({len(parsed['quotes'])} found):")
        for q in parsed['quotes']:
            print(f"    • \"{q['text'][:70]}...\"  (source: {q['source']})")
        return

    img_folder = os.path.join(output, "images")
    vid_folder = os.path.join(output, "videos")

    print(f"\n── Fetching Images ──\n")
    for i, (query, qtype) in enumerate(parsed['image_queries']):
        download_images(query, max_results=images_per,
                        output_folder=img_folder, query_type=qtype)
        if i < len(parsed['image_queries']) - 1:
            time.sleep(2)

    print(f"\n── Fetching Videos ──\n")
    for query in parsed['video_queries']:
        download_youtube_clip(query, max_results=videos_per, output_folder=vid_folder)

    if parsed['quotes']:
        print(f"\n── Finding Quote Sources ──\n")
        process_quotes(parsed['quotes'], output, parsed['people'])

    img_count = len(os.listdir(img_folder)) if os.path.exists(img_folder) else 0
    vid_count = len(os.listdir(vid_folder)) if os.path.exists(vid_folder) else 0
    art_count = len(os.listdir(os.path.join(output, "articles"))) if os.path.exists(os.path.join(output, "articles")) else 0

    # Generate asset manifest
    manifest = {
        'script': os.path.basename(script_path),
        'law': law_num,
        'people': parsed['people'],
        'organizations': parsed['organizations'],
        'image_queries': [
            {'query': q, 'type': t, 'files': [
                f for f in os.listdir(img_folder)
                if f.startswith(q.replace(' ', '_').lower()[:40])
            ] if os.path.exists(img_folder) else []}
            for q, t in parsed['image_queries']
        ],
        'video_queries': [
            {'query': q}
            for q in parsed['video_queries']
        ],
        'quotes': [
            {'text': q['text'][:100], 'source': q['source']}
            for q in parsed['quotes']
        ],
        'scenes': parsed['scenes'],
        'totals': {
            'images': img_count,
            'videos': vid_count,
            'articles': art_count,
        }
    }
    manifest_path = os.path.join(output, "manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n── Done ──")
    print(f"   📷 {img_count} images in {img_folder}/")
    print(f"   🎬 {vid_count} videos in {vid_folder}/")
    print(f"   📰 {art_count} articles in {output}/articles/")
    print(f"   📝 Quote index: {output}/quotes.md")
    print(f"   📋 Manifest: {manifest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Power Plays Asset Fetcher v5"
    )
    parser.add_argument('--script', type=str, default=None,
                        help='Path to a Power Plays script file (.md, .txt, .docx)')
    parser.add_argument('--images-per', type=int, default=2,
                        help='Number of images per query (default: 2)')
    parser.add_argument('--videos-per', type=int, default=1,
                        help='Number of videos per query (default: 1)')
    parser.add_argument('--output', type=str, default='assets',
                        help='Output folder (default: ./assets)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be fetched without downloading')

    args = parser.parse_args()

    if args.script:
        if not os.path.exists(args.script):
            print(f"Error: Script file not found: {args.script}")
            sys.exit(1)
        run_script_mode(
            args.script,
            images_per=args.images_per,
            videos_per=args.videos_per,
            output=args.output,
            dry_run=args.dry_run,
        )
    else:
        run_manual()
