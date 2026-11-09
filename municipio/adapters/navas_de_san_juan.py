"""Navas de San Juan: municipal planning register and preparation inventory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://navasdesanjuan.es'
URBANISMO = BASE + '/el-ayuntamiento/areas-municipales/urbanismo/'
REGISTER = URBANISMO + 'registro-municipal-de-instrumentos-de-planeamiento-navas-de-san-juan-jaen/'
PREPARATION = URBANISMO + 'planeamiento-en-elaboracion/'
MONTHS = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1, 13)))
MONTHS.update({'dic': 12})


def text(node):
    return node.get_text(' ', strip=True)


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('.et_pb_post_content')
    if main is None:
        raise ValueError('Missing municipal inventory content')
    # These are static inventories. Fail if the site introduces pagination.
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
                re.match(r'^(siguiente|next|»)', text(a), re.I) or
                re.search(r'[?&](?:paged|page)=|/page/\d', a['href'])):
            raise ValueError('Pagination requires review; refusing a partial inventory')
    return main


def explicit_date(raw):
    """Only complete unambiguous dates, never years or bulletin identifiers."""
    clean = re.sub(r'\bde\b', ' ', raw.lower())
    found = []
    for d, m, y in re.findall(r'\b(\d{1,2})\s+([a-z]+)\s+(\d{4})\b', clean):
        if m in MONTHS:
            found.append(date(int(y), MONTHS[m], int(d)).isoformat())
    for d, m, y in re.findall(r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', clean):
        found.append(date(int(y), int(m), int(d)).isoformat())
    return found[0] if len(found) == 1 else None


def links(node, source):
    docs = {}
    for a in node.select('a[href]'):
        url = urljoin(source, a['href'])
        if urlparse(url).scheme not in {'https', 'http'}:
            raise ValueError('Unexpected document scheme')
        docs.setdefault(url, {'titulo': text(a), 'url': url, 'source_url': source})
    return list(docs.values())


def record(key, title, url, source):
    return {'id': 'navas-de-san-juan-plan-' + key, 'municipio': 'Navas de San Juan',
            'codigo_ine': '23063', 'provincia': 'Jaén', 'titulo': title,
            'tipo': 'planeamiento_urbanistico', 'url': url, 'inventory_url': source,
            'source': 'ayuntamiento', 'fecha': None, 'fecha_aprob': None,
            'fecha_publicacion': None, 'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False}


def parse_register(html):
    main = content(html)
    table = main.select_one('table')
    if table is None or 'APROBACIÓN DEFINITIVA' not in text(table):
        raise ValueError('Missing planning register columns')
    rows = []
    seen = set()
    for tr in table.select('tr')[1:]:
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 6 or not text(cells[0]).isdigit():
            raise ValueError('Unexpected register row')
        number = text(cells[0])
        if number in seen:
            raise ValueError('Duplicate register number')
        seen.add(number)
        title = text(cells[1])
        # The official table also contains fiscal/building ordinances.
        if not re.match(r'^(Normas Subsidiarias|Modificación (?:Puntual|de (?:las )?NN\.SS\.)|Estudio de Detalle|PGOU:|Innovación PGOU:)', title, re.I):
            if 'ordenanza' in title.lower():
                continue
            raise ValueError('Unreviewed register instrument: ' + title)
        docs = links(cells[1], REGISTER)
        row = record('registro-' + number, title, REGISTER, REGISTER)
        row.update(registro_numero=number, origen='registro_municipal_planeamiento',
                   fase='aprobación definitiva', fecha_aprob=explicit_date(text(cells[2])),
                   fecha_publicacion=explicit_date(text(cells[3])),
                   aprobacion_texto=text(cells[2]), publicacion_texto=text(cells[3]),
                   organo_aprobacion=text(cells[4]), registro_autonomico=text(cells[5]),
                   documentos=docs)
        rows.append(row)
    if not rows:
        raise ValueError('Empty planning register')
    return rows


def parse_preparation(html):
    main = content(html)
    groups = {}
    section = None
    for p in main.find_all('p', recursive=False):
        heading = p.find('strong', recursive=False)
        if heading:
            section = text(heading)
            if not re.match(r'^[1-5]\.', section):
                raise ValueError('Unreviewed preparation section: ' + section)
        docs = links(p, PREPARATION)
        if docs:
            if section is None:
                raise ValueError('Documents without preparation section')
            key = 'cruz-15' if section.startswith('4.') else 'pbom'
            groups.setdefault(key, []).extend(dict(d, seccion=section) for d in docs)
    if set(groups) != {'pbom', 'cruz-15'}:
        raise ValueError('Preparation instruments changed; review required')
    rows = []
    for key, docs in groups.items():
        title = ('Plan Básico de Ordenación Municipal (PBOM) de Navas de San Juan'
                 if key == 'pbom' else 'Estudio de Ordenación (Calle Cruz, 15)')
        row = record(key, title, PREPARATION, PREPARATION)
        row.update(origen='planeamiento_en_elaboracion', documentos=list({d['url']: d for d in docs}.values()),
                   fase='en elaboración', descripcion='Documentos agrupados por instrumento; las fechas de ficheros no se interpretan como acuerdos.')
        # Approval phase is taken from the section/link label, without a date.
        if any('aprobación inicial' in (d['seccion'] + ' ' + d['titulo']).lower() for d in docs):
            row['fase'] = 'aprobación inicial'
        rows.append(row)
    return rows


class NavasDeSanJuanAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        if urlparse(url).hostname not in {'navasdesanjuan.es', 'www.navasdesanjuan.es'}:
            raise ValueError('Unexpected municipal detail host')
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-navas-de-san-juan/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'navasdesanjuan.es', 'www.navasdesanjuan.es'}:
            raise ValueError('Unexpected redirect')
        response.encoding = 'utf-8'
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(url.encode()).hexdigest()[:16]
            (path / (key + '.html')).write_text(response.text, encoding='utf-8')
            (path / (key + '.url')).write_text(url, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = parse_register(self._fetch(REGISTER))
        for row in rows:
            documents = {}
            for link in row['documentos']:
                url = link['url']
                if urlparse(url).path.lower().endswith(('.pdf', '.zip')):
                    documents[url] = link
                else:
                    detail = content(self._fetch(url))
                    attached = links(detail, url)
                    if not attached:
                        raise ValueError('Instrument detail has no documents: ' + url)
                    documents[url] = dict(link, tipo='pagina_instrumento')
                    for doc in attached:
                        documents[doc['url']] = doc
            row['documentos'] = list(documents.values())
        rows.extend(parse_preparation(self._fetch(PREPARATION)))
        return {**self._write(out_jsonl, rows), 'source_urls': [REGISTER, PREPARATION],
                'coverage': 'municipal planning inventories; not all public works or licences'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled',
                'reason': 'No verified granted-licence inventory; application forms excluded'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
