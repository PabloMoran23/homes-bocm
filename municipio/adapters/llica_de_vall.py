"""Municipal Urbanisme inventory, fully paginated, with grouped source documents."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.llissadevall.cat/ajuntament-seu/informacio-oficial/urbanisme'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
# Same water-network project: initial and definitive document versions, not two works.
WATER_INITIAL = SOURCE + '/projecte-sectoritzacio-xarxa-aigua-potable.html'
WATER_FINAL = SOURCE + '/projecte-executiu-per-la-sectoritzacio-i-loptimitzacio-de-pressions-a-la-xarxa-dabastament-daigua-potable-de-llica-de-vall.html'


def supported(title):
    return bool(re.match(r"^(?:Projecte\b|Memòria [Vv]alorada\b|Modificació [Pp]untual\b|Pla Especial\b|Aprovació (?:del .*?[Pp]rojecte|definitiva del Projecte|d'un conjunt de modificacions)|Tercer carril\b)", title))


def page_url(url):
    parts = urlsplit(url)
    if parts.hostname != 'www.llissadevall.cat' or parts.path.rstrip('/') != urlsplit(SOURCE).path:
        raise ValueError('Unexpected inventory pagination URL: ' + url)
    params = parse_qs(parts.query)
    if set(params) - {'pag'} or len(params.get('pag', ['1'])) != 1:
        raise ValueError('Unknown pagination scheme')
    number = params.get('pag', ['1'])[0]
    if not number.isdigit() or int(number) < 1:
        raise ValueError('Invalid inventory page number')
    return SOURCE if int(number) == 1 else SOURCE + '?pag=' + str(int(number))


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if not main or not main.select_one('h1') or main.h1.get_text(strip=True) != 'Urbanisme':
        raise ValueError('Urbanisme inventory missing or changed')
    entries = {}
    for block in main.select('.tplDefault'):
        a = block.select_one('a[href]')
        if not a:
            raise ValueError('Inventory item without detail link')
        target = urljoin(url, a['href'])
        if not target.startswith(SOURCE + '/') or not target.endswith('.html'):
            raise ValueError('Unexpected inventory detail link')
        entries[target] = a.get_text(' ', strip=True)
    if not entries:
        raise ValueError('Empty inventory page')
    pages = set()
    for a in main.select('a[href]'):
        target = urljoin(url, a['href'])
        if 'pag=' in target or a.get('rel') == ['next'] or a.get_text(strip=True).lower() in {'següent', 'next'}:
            pages.add(page_url(target))
    return entries, pages


def exact_date(text):
    """Only a date at the end of a short explicit event, never a certificate date."""
    text = ' '.join(text.lower().replace('’', "'").split()).rstrip('.')
    if any(word in text for word in ('certific', 'al·legacion', 'publicació', 'supeditad')):
        return None
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})$', text)
    if match:
        day, month, year = map(int, match.groups())
    else:
        match = re.search(r"(\d{1,2})\s*(?:de\s+|d')([a-zç]+)\s+(?:de|del)\s+(\d{4})$", text)
        if not match or match[2] not in MONTHS:
            return None
        day, month, year = int(match[1]), MONTHS[match[2]], int(match[3])
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_detail(html, url, expected_title):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('main .containerArticle')
    if not article or not article.h1 or article.h1.get_text(' ', strip=True) != expected_title:
        raise ValueError('Project detail missing or title changed: ' + url)
    description = '\n'.join(x.get_text('\n', strip=True) for x in article.select('.ddbbtext'))
    # Preserve original event narratives, including automatic approvals and
    # certificates. Only simple, unambiguous approval dates become typed fields.
    events = []
    pattern = r"(Aprovació[^:\n]*|Exposició pública|Al·legacions|Publicació[^:\n]*):"
    matches = list(re.finditer(pattern, description, re.I))
    for i, match in enumerate(matches):
        value = ' '.join(description[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(description)].split())
        events.append({'etiqueta': match[1], 'texto': value, 'fecha': exact_date(value), 'source_url': url})
    docs = {}
    for a in soup.select('main #page-documents a[href]'):
        target = urljoin(url, a['href'])
        if urlsplit(target).hostname != 'www.llissadevall.cat' or not urlsplit(target).path.startswith('/media/repository/'):
            raise ValueError('Unexpected document host/path')
        docs[target] = {'titulo': a.get_text(' ', strip=True), 'url': target, 'source_url': url}
    if not docs:
        raise ValueError('Project has no source documents: ' + url)
    definitive = [e for e in events if e['etiqueta'].lower().startswith('aprovació definitiva') and e['texto'] not in {'', '-'}]
    provisional = [e for e in events if e['etiqueta'].lower().startswith('aprovació provisional') and e['texto'] not in {'', '-'}]
    initial = [e for e in events if e['etiqueta'].lower().startswith('aprovació inicial') and e['texto'] not in {'', '-'}]
    phase = 'aprobación definitiva' if definitive else 'aprobación provisional' if provisional else 'aprobación inicial' if initial else None
    if not phase and expected_title.startswith('Aprovació definitiva del Projecte'):
        phase = 'aprobación definitiva'
    updated = article.select_one('.updated')
    return {
        'id': 'llica-de-vall-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Lliçà de Vall', 'provincia': 'Barcelona', 'codigo_ine': '08108',
        'titulo': expected_title, 'tipo': 'planeamiento_urbanistico' if re.search(r'Pla (?:General|Especial)', expected_title, re.I) else 'proyecto_obra_publica',
        'fase': phase, 'fecha': None, 'fecha_publicacion': None,
        'fecha_aprob': definitive[0]['fecha'] if len(definitive) == 1 else None,
        'descripcion': description, 'eventos_fuente': events,
        'url': url, 'source_urls': [url], 'url_documento': next(iter(docs)),
        'documentos': list(docs.values()), 'source': 'ayuntamiento',
        # Source identity is a project-document collection, not a verified
        # administrative expediente or an activity eligible for publication.
        'source_entity_type': 'documento',
        'origen': 'inventario_municipal_urbanisme',
        'actualizacion_pagina_texto': updated.get_text(' ', strip=True) if updated else None,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No se ha extraído geometría de proyecto; documentos enlazados sin geocodificación',
    }


def group_projects(rows):
    groups = {}
    for row in rows:
        key = WATER_FINAL if row['url'] in {WATER_INITIAL, WATER_FINAL} else row['url']
        groups.setdefault(key, []).append(row)
    output = []
    for key, members in sorted(groups.items()):
        preferred = next((r for r in members if r['url'] == key), members[0])
        row = dict(preferred)
        row['id'] = 'llica-de-vall-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16]
        row['source_urls'] = sorted({u for r in members for u in r['source_urls']})
        row['documentos'] = list({d['url']: d for r in members for d in r['documentos']}.values())
        row['fuentes'] = [{'url': r['url'], 'titulo': r['titulo'], 'descripcion': r['descripcion'],
                          'actualizacion_pagina_texto': r['actualizacion_pagina_texto']} for r in members]
        row['eventos_fuente'] = [e for r in members for e in r['eventos_fuente']]
        output.append(row)
    return output


class LlicaDeVallAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.llissadevall.cat')

    def _fetch(self, url):
        with requests.get(url, timeout=35, stream=True, headers={'User-Agent': self.config.get('user_agent', 'municipio-llica-de-vall/1.0')}) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'www.llissadevall.cat':
                raise ValueError('Unexpected redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('HTML source exceeds 4 MB; extraction aborted')
                chunks.append(chunk)
            raw = b''.join(chunks)
            if self.config.get('capture_dir'):
                folder = Path(self.config['capture_dir'])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (hashlib.sha256(url.encode()).hexdigest() + '.html')).write_bytes(raw)
            return raw.decode('utf-8-sig')

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.jsonl.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, seen, inventory, signatures = {SOURCE}, set(), {}, set()
        while pending:
            url = sorted(pending)[0]
            pending.remove(url)
            if len(seen) >= 100:
                raise ValueError('Pagination exceeds safety bound; no partial output written')
            entries, pages = parse_inventory(self._fetch(url), url)
            signature = tuple(sorted(entries))
            if signature in signatures:
                raise ValueError('Repeated inventory page; pagination may be ignored')
            signatures.add(signature)
            seen.add(url)
            for target, title in entries.items():
                if target in inventory and inventory[target] != title:
                    raise ValueError('Conflicting project title across pages')
                inventory[target] = title
            pending.update(pages - seen)
        numbers = {int(parse_qs(urlsplit(u).query).get('pag', ['1'])[0]) for u in seen}
        if numbers != set(range(1, max(numbers) + 1)):
            raise ValueError('Missing inventory page')
        rows = [parse_detail(self._fetch(u), u, title) for u, title in sorted(inventory.items()) if supported(title)]
        if not rows:
            raise ValueError('No supported projects; no output written')
        rows = group_projects(rows)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_pages': len(seen),
                'source_urls': sorted(seen | {u for r in rows for u in r['source_urls']}),
                'excluded_entries': [{'url': u, 'titulo': t} for u, t in sorted(inventory.items()) if not supported(t)],
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current public inventory snapshot; no date cutoff or stale cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
