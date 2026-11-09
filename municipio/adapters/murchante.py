"""Current Murchante PGM re-exposure notices, verified against attached edicts.

Requires the existing system executable pdftotext; no OCR or inferred geometry.
The deliberately narrow coverage is not the municipality's complete plan register.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://murchante.sedipualba.es/tablondeanuncios/'
HOST = 'murchante.sedipualba.es'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
LIMITATIONS = [
    'Sólo nuevas exposiciones públicas de modificaciones estructurantes del PGM en el tablón vigente; no histórico completo.',
    'No se extrae el inventario interactivo de transparencia ANIMSA ni se acredita la fecha de publicación en BON.',
    'Los PDF son edictos: no se ha recuperado el documento técnico completo ni geometría del instrumento.',
    'Sin licencias concedidas verificadas, coordenadas ni geometría; publication_ready=false.',
]


def clean(text):
    return ' '.join(text.split())


def official_url(base, href, endpoint):
    url = urljoin(base, href)
    parsed = urlparse(url)
    identifier = parse_qs(parsed.query).get('id', [''])[0]
    if (parsed.scheme != 'https' or parsed.hostname != HOST
            or parsed.path != '/tablondeanuncios/' + endpoint or not identifier.isdigit()):
        raise ValueError('Unexpected official source URL: ' + url)
    return url


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.select_one('#contenido .gridview') or 'AYUNTAMIENTO DE MURCHANTE' not in soup.get_text():
        raise ValueError('Missing municipal notice inventory')
    # The reviewed Repeater renders all 25 current notices, with no pager.
    # Fail closed if any paging controls appear; never silently read page one.
    for el in soup.select('#contenido a, #contenido input, #contenido button, #contenido [class], #contenido [id]'):
        attrs = ' '.join(str(el.get(k, '')) for k in ('href', 'id', 'class', 'rel', 'title', 'value', 'onclick'))
        label = clean(el.get_text(' ', strip=True)) if el.name in ('a', 'button') else ''
        if (re.search(r'page\$|[?&](?:page|pagina|p)=|pager|pagin|nextpage', attrs, re.I)
                or label.lower() in {'siguiente', 'anterior', 'next', 'previous', '>', '»', '‹', '›'}):
            raise ValueError('Unreviewed pagination in municipal inventory')
    notices = {}
    for tr in soup.select('#contenido .gridview tr'):
        a = tr.select_one('a[href*="anuncio.aspx?id="]')
        if not a:
            continue
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 3:
            raise ValueError('Changed notice row structure')
        title = clean(cells[2].get_text(' ', strip=True))
        if not re.search(r'nueva exposición al público modificación estructurante del Plan General Municipal', title, re.I):
            continue
        dates = re.fullmatch(r'(\d{2}/\d{2}/\d{4}) - (\d{2}/\d{2}/\d{4})', clean(cells[1].get_text()))
        if not dates:
            raise ValueError('Missing publication interval')
        url = official_url(SOURCE, a['href'], 'anuncio.aspx')
        notices[url] = {'titulo': title, 'url': url,
                        'fecha_publicacion': datetime.strptime(dates[1], '%d/%m/%Y').date().isoformat(),
                        'fecha_fin_exposicion_tablon': datetime.strptime(dates[2], '%d/%m/%Y').date().isoformat()}
    if not notices:
        raise ValueError('No supported planning notices; review current inventory')
    return list(notices.values())


def parse_documents(html, notice):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('#leer h2')
    if not heading or clean(heading.get_text()) != notice['titulo']:
        raise ValueError('Notice detail does not match inventory')
    exposure = soup.select_one('.fechas-exposicion')
    if not exposure or datetime.strptime(notice['fecha_publicacion'], '%Y-%m-%d').strftime('%d/%m/%Y') not in exposure.get_text():
        raise ValueError('Publication date differs between inventory and detail')
    docs = {}
    for block in soup.select('#leer .adjunto'):
        a = block.select_one('a[href]')
        title = block.select_one('.adjunto-titulo')
        if not a or not title:
            raise ValueError('Changed document structure')
        url = official_url(notice['url'], a['href'], 'documento.aspx')
        doc_id = parse_qs(urlparse(url).query)['id'][0]
        docs[doc_id] = {'titulo': clean(title.get_text()), 'url': url,
                        'source_url': notice['url'], 'id_documento': doc_id}
    if not docs:
        raise ValueError('Planning notice has no official attachments')
    return list(docs.values())


def parse_edict(text):
    # PDF side-column stamp can interrupt the body between two lines.
    # Remove only its standalone label; retain the original text as description.
    text = clean(re.sub(r'^\s*SELLO\s*$', '', text, flags=re.M))
    refs = set(re.findall(r'Expediente\s+(\d+[A-Z])\b', text))
    agreement = re.search(r'El Pleno del Ayuntamiento de Murchante, en sesión celebrada el día (\d{1,2}) de (\w+) de (\d{4}) aprobó realizar nueva información pública', text)
    scope = re.search(r'modificación estructurante del Plan General Municipal de Murchante en (.+?)\.\s*(?:SELLO|\d{2}/\d{2}/\d{4}|Publicado|Se somete)', text, re.I)
    if len(refs) != 1 or not agreement or not scope or agreement[2] not in MONTHS:
        raise ValueError('Edict does not establish an identifiable PGM instrument and agreement')
    return {'expediente': next(iter(refs)),
            'titulo': 'Modificación estructurante del Plan General Municipal de Murchante en ' + scope[1],
            'fecha_acuerdo': date(int(agreement[3]), MONTHS.index(agreement[2]) + 1, int(agreement[1])).isoformat(),
            'fase': 'nueva información pública'}


def group_records(records):
    grouped = {}
    for row in records:
        key = row['expediente']
        if key not in grouped:
            grouped[key] = row
            continue
        old = grouped[key]
        if old['titulo'] != row['titulo']:
            raise ValueError('Conflicting instruments with same expediente')
        old['documentos'] = list({d['url']: d for d in old['documentos'] + row['documentos']}.values())
        old['avisos'] = list({a['url']: a for a in old['avisos'] + row['avisos']}.values())
        if row['fecha_publicacion'] > old['fecha_publicacion']:
            for field in ('url', 'fecha_publicacion', 'fecha_acuerdo', 'fase', 'descripcion'):
                old[field] = row[field]
    return sorted(grouped.values(), key=lambda r: r['id'])


class MurchanteAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, name):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Official source redirected outside municipal board')
        data = response.content
        if self.config.get('capture_dir'):
            target = Path(self.config['capture_dir'])
            target.mkdir(parents=True, exist_ok=True)
            (target / name).write_bytes(data)
        return data

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        records = []
        sources = [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-murchante/1.0'
            notices = parse_inventory(self._fetch(session, SOURCE, 'inventory.html'))
            for notice in notices:
                nid = parse_qs(urlparse(notice['url']).query)['id'][0]
                sources.append(notice['url'])
                docs = parse_documents(self._fetch(session, notice['url'], f'detail-{nid}.html'), notice)
                edicts = []
                for doc in docs:
                    sources.append(doc['url'])
                    data = self._fetch(session, doc['url'], f"document-{doc['id_documento']}.pdf")
                    if not data.startswith(b'%PDF-'):
                        raise ValueError('Expected a source PDF')
                    with tempfile.TemporaryDirectory() as directory:
                        pdf = Path(directory) / 'source.pdf'
                        pdf.write_bytes(data)
                        result = subprocess.run(['pdftotext', '-layout', str(pdf), '-'],
                                                capture_output=True, check=True, timeout=30)
                    text = result.stdout.decode('utf-8')
                    if self.config.get('capture_dir'):
                        (Path(self.config['capture_dir']) / f"document-{doc['id_documento']}.txt").write_text(text, encoding='utf-8')
                    if 'Edicto' in doc['titulo']:
                        edicts.append((parse_edict(text), clean(text)))
                if len(edicts) != 1:
                    raise ValueError('Expected one unambiguous edict per notice')
                fields, description = edicts[0]
                records.append({**fields, 'id': 'murchante-pgm-' + fields['expediente'].lower(),
                    'municipio': 'Murchante', 'codigo_ine': '31176', 'provincia': 'Navarra',
                    'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
                    'origen': 'tablon_vigente_sedipualba', 'url': notice['url'],
                    'fecha_publicacion': notice['fecha_publicacion'], 'fecha_aprob': None,
                    'descripcion': description, 'documentos': docs,
                    'avisos': [{**notice, 'fecha_acuerdo': fields['fecha_acuerdo'], 'fase': fields['fase']}],
                    'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                    'geometry_status': 'unavailable', 'limitaciones': LIMITATIONS})
        rows = group_records(records)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(dict.fromkeys(sources)),
                'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot; no incremental history or deletion inference.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
