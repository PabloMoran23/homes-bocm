"""Official municipal works announcements, with explicit publication semantics."""
from __future__ import annotations

from datetime import datetime
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.santabrigida.es'
API = BASE + '/wp-json/wp/v2/posts'


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag in ('p', 'br', 'div', 'li'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        if tag in ('p', 'div', 'li'):
            self.parts.append(' ')

    def handle_data(self, value):
        if not self.skip:
            self.parts.append(value)


def plain(value):
    parser = _Text()
    parser.feed(str(value))
    return re.sub(r'\s+', ' ', unescape(''.join(parser.parts))).strip()


def normalized(value):
    return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()


# Both an actual intervention and a concrete asset are required in the headline.
INTERVENTION = re.compile(r'\b(obras?|asfaltado|reconstruccion|restitucion|restauracion|reforma|rehabilitacion|renovacion|renovad[ao]s?|mejora[sn]?|modernizacion|construccion|remodelacion|pavimentacion|transformar)\b')
ASSET = re.compile(r'\b(calle|calles|avenida|biblioteca|polideportivo|pabellon|colegio|escuela|plaza|carretera|saneamiento|alcantarillado|amas de casa|instalaciones deportivas|pisos de repesa|parque infantil|gamonal|silos|almacen municipal|centro ocupacional|complejo deportivo|castillo|casa-museo)\b')
NOISE = re.compile(r'\b(exige[n]?|piden|pide|reclama[n]?|solicita[n]?|exposicion|teatro|pintura|certamen|acoge|prioriza|cortes|cortara|cerrada|desvia|vehiculo|rallye|ayudas|subvenciones|convoca|comision de seguimiento)\b')


def record(post):
    title = plain(post.get('title', {}).get('rendered', ''))
    text = normalized(title)
    if not INTERVENTION.search(text) or not ASSET.search(text) or NOISE.search(text):
        return None
    link = post.get('link', '')
    parsed = urlparse(link)
    if parsed.scheme != 'https' or parsed.hostname != 'www.santabrigida.es' or parsed.path.strip('/') == '':
        return None
    description = plain(post.get('content', {}).get('rendered', ''))
    if not description or not post.get('id'):
        return None
    result = {
        'id': f'santa-brigida-noticia-{int(post["id"])}',
        'municipio': 'Santa Brígida', 'codigo_ine': '35021',
        'titulo': title, 'descripcion': description,
        'tipo': 'actuación de obra pública', 'source': 'ayuntamiento',
        'origen': 'comunicado_municipal', 'url': link,
        'source_api_url': API + '/' + str(int(post['id'])),
        'publication_ready': False,
        'geometry_status': 'unavailable',
    }
    date = post.get('date', '')
    try:
        result['fecha_publicacion'] = datetime.fromisoformat(date).date().isoformat()
    except (TypeError, ValueError):
        pass
    return result


class SantaBrigidaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, page):
        params = urlencode({'search': 'obras', 'per_page': 100, 'page': page, 'orderby': 'date', 'order': 'desc'})
        req = Request(API + '?' + params, headers={'User-Agent': 'Mozilla/5.0 (compatible; municipio-santa-brigida/1.0)', 'Accept': 'application/json'})
        with urlopen(req, timeout=25) as response:
            if urlparse(response.url).hostname != 'www.santabrigida.es':
                raise ValueError('Unexpected API redirect')
            payload = json.load(response)
            if not isinstance(payload, list):
                raise ValueError('Unexpected WordPress response')
            return payload, int(response.headers.get('X-WP-TotalPages', '1'))

    def _collect(self):
        max_pages = int(self.config.get('max_pages', 5))
        if not 1 <= max_pages <= 20:
            raise ValueError('max_pages must be between 1 and 20')
        result, scanned, total_pages = {}, 0, 1
        for page in range(1, max_pages + 1):
            if page > 1:
                time.sleep(0.5)
            posts, total_pages = self._fetch(page)
            scanned += 1
            for post in posts:
                item = record(post)
                if item:
                    result[item['id']] = item
            if page >= total_pages:
                break
        if total_pages > scanned:
            raise RuntimeError(f'Pagination cap reached: {scanned}/{total_pages}; increase max_pages after review')
        if not result:
            raise RuntimeError('No concrete works announcements extracted; source review required')
        return list(result.values()), {'pages_scanned': scanned, 'total_pages': total_pages, 'truncated': total_pages > scanned}

    def backfill_proyectos(self, out_jsonl: Path):
        rows, stats = self._collect()
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'publication_ready': False, **stats}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Snapshot refresh is idempotent by official post ID; no invented cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'count': 0, 'written': 0, 'disabled': True, 'reason': 'No verified public register of actual licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
