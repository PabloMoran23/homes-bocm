"""Bounded DOE planning inventory for Navalvillar de Pela (not a licence register)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://doe.juntaex.es'
SEARCH = BASE + '/busquedas/disposiciones.php'
START = '2024-01-01'
MONTHS = dict(zip(('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split(), range(1, 13)))
DATE_RE = r'(\d{1,2}) de (\w+) de (\d{4})'
LIMITATIONS = [
    'Cobertura parcial desde 2024-01-01: UE3 y modificación 20-1/2019; no histórico completo ni todos los proyectos del término.',
    'Dos búsquedas DOE: organismo municipal y título con Navalvillar de Pela; no búsqueda exhaustiva por contenido.',
    'HTML DOE informativo; se conservan enlaces al PDF auténtico y XML. No se extraen geometrías ni se descargan proyectos técnicos de la sede.',
    'La fecha del anuncio no se interpreta como fecha del acuerdo. Fase es la última documentada en este inventario, no prueba de ejecución física.',
    'Web municipal HTTP 403 en la investigación; sin registro verificado de licencias concedidas.',
]


def spanish_date(text):
    m = re.search(DATE_RE, text.lower())
    if not m or m[2] not in MONTHS:
        raise ValueError('Unrecognized Spanish date: ' + text)
    return date(int(m[3]), MONTHS[m[2]], int(m[1])).isoformat()


def official_url(href, base=SEARCH):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'doe.juntaex.es':
        raise ValueError('Unexpected source URL: ' + url)
    return url


def parse_inventory(html):
    """Require every advertised result; fail on pagination/truncation rather than cut off."""
    soup = BeautifulSoup(html, 'html.parser')
    total = re.search(r'Resultado de la búsqueda:\s*(\d+) disposiciones', soup.get_text(' ', strip=True))
    if not total:
        raise ValueError('DOE result count missing')
    entries = []
    for td in soup.select('td.justificado'):
        title = td.select_one('.DOE4')
        if title is None:
            continue
        link = title.select_one('a[href*="otrosFormatos/html.php"]')
        if link is None:
            raise ValueError('Result lacks HTML detail')
        url = official_url(link['href'])
        query = parse_qs(urlparse(url).query)
        if not all(len(query.get(k, [])) == 1 for k in ('xml', 'anio', 'doe')):
            raise ValueError('Malformed detail URL')
        canonical = BASE + '/otrosFormatos/html.php?' + urlencode({k: query[k][0] for k in ('xml', 'anio', 'doe')})
        entries.append({'titulo': title.get_text(' ', strip=True), 'url': canonical})
    if len(entries) != int(total[1]):
        raise ValueError('DOE pagination/truncation: advertised results differ from parsed rows')
    for a in soup.select('a[href]'):
        if re.search(r'^(siguiente|next|última|ultima)\b', a.get_text(' ', strip=True), re.I) or 'next' in a.get('rel', []):
            raise ValueError('DOE pagination requires review')
    return entries


def candidate(title):
    t = title.lower()
    if any(word in t for word in ('licitación', 'contratación', 'solicitud de licencia', 'formulario')):
        return False
    ue3 = re.search(r'\bue\s*3\b', t) and any(
        phrase in t for phrase in ('programa de ejecución', 'viabilidad de la transformación urbanizadora'))
    return bool(ue3 or ('modificación puntual' in t and 'normas subsidiarias' in t))


def parse_detail(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.Contenido_principal')
    heading = soup.select_one('.tablabordecolor')
    if content is None or heading is None:
        raise ValueError('DOE detail structure missing')
    title = heading.get_text(' ', strip=True)
    if not candidate(title):
        return None
    text = content.get_text(' ', strip=True)
    if 'navalvillar de pela' not in text.lower():
        raise ValueError('Municipality absent in source')
    if 'TEXTO ORIGINAL' not in text:
        raise ValueError('Original text missing')
    body = text.split('TEXTO ORIGINAL', 1)[1]
    t = title.lower()
    if re.search(r'\bue\s*3\b', t):
        key = 'ue3'
    elif ('modificación puntual' in t and ('1/2019' in t or '20-1/2019' in t)):
        key = 'mp20-1-2019'
    elif ('informe ambiental estratégico' in t and 'IA24/0077' in title
          and all(street in body.lower() for street in ('cantarranas', 'luis chamizo', 'velázquez', 'adolfo suárez'))):
        # The definitive 1/2019 agreement explicitly cites this 09/05/2024 report
        # and the identical block bounded by these four streets.
        key = 'mp20-1-2019'
    else:
        return None
    pub = re.search(r'Fecha Publicación:\s*.*?(' + DATE_RE + ')', text, re.I)
    if not pub:
        raise ValueError('Publication date missing')
    doc = {'titulo': title, 'url': url, 'fecha_publicacion': spanish_date(pub[1]),
           'fecha_documento': spanish_date(title), 'organismo': None,
           'procedencia': 'Diario Oficial de Extremadura; HTML informativo'}
    org = re.search(r'Organismo:\s*(.*?)\s*Rango:', text)
    if not org:
        raise ValueError('Issuing body missing')
    doc['organismo'] = org[1]
    formats = {}
    for a in content.select('a[href]'):
        href = a['href']
        if '/pdfs/doe/' in href and href.lower().endswith('.pdf'):
            formats['pdf'] = official_url(href, url)
        elif '.xml' in href.lower():
            formats['xml'] = official_url(href, url)
    if 'pdf' not in formats:
        raise ValueError('Authentic PDF link missing')
    doc.update(formats)
    phase = None
    agreement = None
    if 'aprobación definitiva' in t:
        phase = 'aprobacion_definitiva'
    elif 'aprobación inicial' in t:
        phase = 'aprobacion_inicial'
    elif 'informe ambiental estratégico' in t:
        phase = 'informe_ambiental_estrategico'
    elif 'viabilidad de la transformación urbanizadora' in t:
        phase = 'consulta_viabilidad'
    else:
        return None
    if key == 'ue3' and phase.startswith('aprobacion_'):
        m = re.search(r'Pleno ordinario de fecha\s*' + DATE_RE + r'\s*se aprobó (?:definitivamente|inicialmente)', body, re.I)
        if not m:
            raise ValueError('UE3 agreement date missing')
        agreement = spanish_date(m[0])
    elif key == 'mp20-1-2019' and phase == 'aprobacion_definitiva':
        if not title.upper().startswith('ACUERDO '):
            raise ValueError('Expected definitive agreement')
        agreement = spanish_date(title)
    elif key == 'mp20-1-2019' and phase == 'aprobacion_inicial':
        m = re.search(r'sesión ordinaria celebrada el día\s*' + DATE_RE, body, re.I)
        if not m:
            raise ValueError('Initial agreement date missing')
        agreement = spanish_date(m[0])
    doc['fase'] = phase
    if agreement:
        doc['fecha_acuerdo'] = agreement
    return key, doc


def group_documents(items):
    groups = {}
    titles = {'ue3': 'Programa de Ejecución de la UE3, zona 3: urbanización y reparcelación',
              'mp20-1-2019': 'Modificación puntual 1/2019 (n.º 20) de las NNSS: Cooperativa San Isidro Labrador'}
    for key, doc in items:
        groups.setdefault(key, {})[doc['url']] = doc
    rows = []
    for key, documents in sorted(groups.items()):
        docs = sorted(documents.values(), key=lambda d: (d['fecha_publicacion'], d['url']))
        latest = docs[-1]
        row = {'id': 'navalvillar-de-pela-' + key, 'municipio': 'Navalvillar de Pela',
               'codigo_ine': '06091', 'provincia': 'Badajoz', 'titulo': titles[key],
               'tipo': 'gestion_urbanistica' if key == 'ue3' else 'planeamiento_urbanistico',
               'source': 'ayuntamiento', 'origen': 'doe_inventario_planeamiento',
               'url': latest['url'], 'inventory_url': SEARCH, 'fase': latest['fase'],
               'fecha_publicacion': latest['fecha_publicacion'], 'documentos': docs,
               'geometry_status': 'unavailable', 'publication_ready': False,
               'cobertura': 'Parcial: publicaciones DOE desde 2024 sobre UE3 y modificación 20-1/2019.'}
        if latest.get('fecha_acuerdo'):
            row['fecha_acuerdo'] = latest['fecha_acuerdo']
        rows.append(row)
    if not rows:
        raise ValueError('No supported planning instruments discovered')
    return rows


class NavalvillarDePelaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        end = self.config.get('end_date') or date.today().isoformat()
        if date.fromisoformat(end) < date.fromisoformat(START):
            raise ValueError('Invalid coverage interval')
        evidence = self.config.get('capture_dir')
        captures = Path(evidence) if evidence else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        source_urls = []
        searches = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-inventory/1.0'

            def fetch(url, data=None):
                response = session.post(url, data=data, timeout=40) if data is not None else session.get(url, timeout=40)
                response.raise_for_status()
                official_url(response.url)
                source_urls.append(response.url)
                if captures:
                    digest = hashlib.sha256((url + json.dumps(data, sort_keys=True)).encode()).hexdigest()[:16]
                    (captures / (digest + '.html')).write_text(response.text, encoding='utf-8')
                return response.text

            entries = {}
            for filter_ in ({'orgabus': 'NAVALVILLAR DE PELA'}, {'textobus': 'Navalvillar de Pela'}):
                data = {'fecha1': START, 'fecha2': end, 'tipo': ' ', 'rango': '00',
                        'descriptor': '00', 'yuo': '0', 'buscardesc': 'nodesc', **filter_}
                found = parse_inventory(fetch(SEARCH, data))
                searches.append({'url': SEARCH, 'method': 'POST', 'parameters': data, 'results': len(found)})
                for entry in found:
                    entries[entry['url']] = entry
            items = []
            for entry in entries.values():
                if candidate(entry['titulo']):
                    item = parse_detail(fetch(entry['url']), entry['url'])
                    if item:
                        items.append(item)
        rows = group_documents(items)
        result = self._write(out_jsonl, rows)
        return {**result, 'live_records': len(rows), 'source_urls': sorted(set(source_urls)),
                'searches': searches, 'coverage_start': START, 'coverage_end': end,
                'limitations': LIMITATIONS}

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Re-read the complete bounded inventory: the server has no reliable delta.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
