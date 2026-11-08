"""Individual instruments linked by Abanto-Zierbena's planning inventory."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.abanto-zierbena.eus'
SOURCE = BASE + '/es-ES/soy-abanto-zierbena/Urbanismo-vivienda/Paginas/Planificacionurbanistica.aspx'
MONTHS = ('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split()
DATE = re.compile(r'(\d{1,2}) de (' + '|'.join(MONTHS) + r') de (\d{4})', re.I)
# These two entries contain several instruments/parts and need a separate parser.
AGGREGATES = {'PlanEspecialdeReformaInteriorPERIS.aspx', 'PGOU.aspx'}
LIMITATIONS = [
    'Partial coverage: individual instruments in Planificación urbanística only; Gestión urbanística is outside scope.',
    'PGOU and multi-instrument PERIS catalogue excluded explicitly, as is the advisory council regulation.',
    'Municipal inventory mixes historical and recent instruments; listing does not prove current legal force.',
    'Document links retained as published; PDF contents and agreement conditions are not interpreted.',
    'Publication dates remain null; dates in filenames are not evidence of publication or agreement.',
    'San Miguel detail announces an approved instrument but exposes no document links.',
    'No verified geometry, coordinates or granted-licence inventory.',
]


def clean(text):
    return ' '.join(text.replace('\u200b', '').replace('\ufeff', '').split())


def canonical(base, href):
    parts = urlsplit(urljoin(base, href))
    if parts.scheme != 'https' or parts.hostname != 'www.abanto-zierbena.eus':
        raise ValueError('Unexpected non-municipal link: ' + href)
    return urlunsplit((parts.scheme, parts.netloc, quote(unquote(parts.path), safe='/'), parts.query, parts.fragment))


def assert_unpaginated(soup):
    for a in soup.select('a[href]'):
        label = clean(a.get_text(' ', strip=True)).lower()
        marker = ' '.join([a.get('title', ''), a.get('aria-label', ''), label]).lower()
        href = a['href']
        if (a.get('rel') == ['next'] or any(x in marker for x in ('siguiente', 'next page', 'hurrengo'))
                or re.search(r'(?:[?&](?:page|pagenum|paged|pageno|startrow|pagedprev)=|Page\$Next)', href, re.I)):
            if href not in ('', '#'):
                raise ValueError('Pagination detected; refusing an incomplete inventory')


class AbantoZierbenaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        assert_unpaginated(soup)
        links = soup.select('.slm-layout-main .link-item a[href]')
        if not links:
            raise ValueError('Planning inventory missing or changed')
        entries, excluded = {}, []
        for a in links:
            title = clean(a.get_text(' ', strip=True))
            url = canonical(SOURCE, a['href'])
            basename = unquote(urlsplit(url).path).rsplit('/', 1)[-1]
            if basename in AGGREGATES or title.lower().startswith('reglamento municipal'):
                excluded.append({'titulo': title, 'url': url, 'reason': 'aggregate catalogue' if basename in AGGREGATES else 'regulation, not an instrument'})
                continue
            if not re.search(r'plan |estudio.*detalle|programa.*actuaci|proyecto.*reparcelaci', title, re.I):
                raise ValueError('Unclassified inventory entry: ' + title)
            if not urlsplit(url).path.lower().endswith('.aspx'):
                raise ValueError('Expected an individual instrument detail: ' + url)
            entries[url] = {'titulo': title, 'url': url}
        if not entries:
            raise ValueError('No individual planning instruments')
        return list(entries.values()), excluded

    @staticmethod
    def parse_detail(html, entry):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#ProcedureContent, #MainContent')
        if content is None:
            raise ValueError('Instrument content missing: ' + entry['url'])
        for node in content.select('script, style, nav'):
            node.decompose()
        text = clean(content.get_text(' ', strip=True))
        documents = {}
        for a in content.select('a[href]'):
            if urlsplit(a['href']).path.lower().endswith(('.pdf', '.zip')):
                url = canonical(entry['url'], a['href'])
                documents.setdefault(url, {'titulo': clean(a.get_text(' ', strip=True)), 'url': url, 'source_url': entry['url']})
        if not documents and not re.search(r'acuerdo de aprobaci[oó]n definitiva', text, re.I):
            raise ValueError('Neither documents nor explicit instrument agreement: ' + entry['url'])
        # Extract only single-date approval paragraphs. Multiple-date narratives
        # remain verbatim rather than guessing which agreement a date belongs to.
        events = []
        section_phase = None
        phases_seen = set()
        for p in content.select('p, h3, h4, strong'):
            narrative = clean(p.get_text(' ', strip=True))
            if narrative.lower() in {'aprobación inicial', 'aprobación definitiva'}:
                section_phase = narrative.lower()
                phases_seen.add(section_phase)
            if p.name != 'p':
                continue
            matches = list(DATE.finditer(narrative))
            if len(matches) != 1:
                continue
            phase = None
            if re.search(r'(?:aprob[oó]|aprobad[oa]).*definitivamente|aprobaci[oó]n definitiva', narrative, re.I):
                phase = 'aprobación definitiva'
            elif re.search(r'aprob[oó] inicialmente|aprobaci[oó]n inicial', narrative, re.I):
                phase = 'aprobación inicial'
            elif section_phase and re.search(r'aprob[oó]|aprobad[oa]', narrative, re.I):
                phase = section_phase
            if phase:
                phases_seen.add(phase)
            if phase and re.search(r'acuerdo|sesi[oó]n', narrative, re.I):
                m = matches[0]
                day = date(int(m[3]), MONTHS.index(m[2].lower()) + 1, int(m[1])).isoformat()
                event = {'fase': phase, 'fecha_acuerdo': day, 'texto_fuente': narrative, 'source_url': entry['url']}
                if event not in events:
                    events.append(event)
        final = [e for e in events if e['fase'] == 'aprobación definitiva']
        initial = [e for e in events if e['fase'] == 'aprobación inicial']
        if 'aprobación definitiva' in phases_seen or 'aprobación definitiva' in entry['titulo'].lower():
            phase, selected = 'aprobación definitiva', final
        elif 'aprobación inicial' in phases_seen or 'aprobación inicial' in entry['titulo'].lower():
            phase, selected = 'aprobación inicial', initial
        else:
            phase, selected = None, []
        agreement_dates = {e['fecha_acuerdo'] for e in selected}
        agreement = next(iter(agreement_dates)) if len(agreement_dates) == 1 else None
        title = entry['titulo']
        return {
            'id': '48002-plan-' + hashlib.sha256(entry['url'].encode()).hexdigest()[:16],
            'municipio': 'Abanto y Ciérvana-Abanto Zierbena', 'codigo_ine': '48002', 'provincia': 'Bizkaia',
            'titulo': title, 'tipo': 'reparcelacion' if 'reparcelaci' in title.lower() else 'planeamiento_urbanistico',
            'fase': phase, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': agreement, 'fecha_aprob': agreement,
            'url': entry['url'], 'source': 'ayuntamiento', 'source_url': SOURCE,
            'origen': 'inventario_planificacion_urbanistica', 'descripcion': text,
            'documentos': list(documents.values()), 'acuerdos': events,
            'documentos_status': 'linked_not_downloaded' if documents else 'not_exposed',
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False,
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        capture = Path(self.config['evidence_dir']) if self.config.get('evidence_dir') else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)
        sources = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-abanto-zierbena/1.0'

            def fetch(url):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                canonical(url, response.url)
                if 'text/html' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Expected HTML: ' + url)
                sources.append(url)
                if capture:
                    name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
                    (capture / name).write_bytes(response.content)
                return response.content

            entries, excluded = self.parse_inventory(fetch(SOURCE))
            rows = []
            for entry in entries:
                time.sleep(.2)
                rows.append(self.parse_detail(fetch(entry['url']), entry))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'excluded_inventory_entries': excluded, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh the complete scoped snapshot; no date watermark drops old plans.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
