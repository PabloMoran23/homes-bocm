"""Current Castejón notices of public consultation on project-affected property.

This is a partial snapshot, not a historical works or granted-licence register.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://sedeelectronica.castejon.com'
SOURCE = BASE + '/tablondeanuncios/default.aspx'


def norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper()


def resource_id(url, resource):
    parsed = urlparse(urljoin(SOURCE, url))
    values = parse_qs(parsed.query).get('id', [])
    if (parsed.scheme != 'https' or parsed.netloc != urlparse(BASE).netloc
            or parsed.path != '/tablondeanuncios/' + resource + '.aspx'
            or len(values) != 1 or not values[0].isdigit()):
        raise ValueError('Unexpected municipal resource URL: ' + url)
    return values[0]


def date_value(text):
    return datetime.strptime(text, '%d/%m/%Y').date().isoformat()


class CastejonAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = SOURCE

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        # The reviewed unfiltered board has no paging. Fail closed on newly
        # introduced paging (including WebForms postbacks), never take page 1.
        for control in soup.select('a, button, input, select'):
            marker = ' '.join(str(control.get(k, '')) for k in
                              ('href', 'id', 'name', 'class', 'rel', 'title', 'value', 'aria-label'))
            text = norm(control.get_text(' ', strip=True))
            if (re.search(r'pager|pagination|paginacion|Page\$|[?&](?:page|pagina)=', marker, re.I)
                    or text in {'SIGUIENTE', 'NEXT', 'ULTIMA', 'ULTIMO', '>', '>>', '»', '›'}):
                raise ValueError('Inventory pagination requires review; snapshot not written')
        area = soup.select_one('select[id$="ddlArea"]')
        if area:
            selected = area.select_one('option[selected]') or area.select_one('option')
            if not selected or norm(selected.get_text(' ', strip=True)) != 'TODAS LAS AREAS':
                raise ValueError('Expected the unfiltered current board')
        table = soup.select_one('table.gridview')
        if not table:
            raise ValueError('Municipal inventory table missing')
        notices = {}
        total = 0
        for tr in table.select('tr'):
            if tr.select('th'):
                continue
            cells = tr.find_all('td', recursive=False)
            link = tr.select_one('a[href*="anuncio.aspx?"]')
            if not link or len(cells) != 3:
                raise ValueError('Unrecognised inventory row or pagination')
            total += 1
            ident = resource_id(link['href'], 'anuncio')
            dates = re.fullmatch(r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})', cells[1].get_text(' ', strip=True))
            if not dates:
                raise ValueError('Unrecognised exposure date range')
            title = cells[2].get_text(' ', strip=True)
            key = norm(title)
            # A concrete public-consultation notice about affected property is
            # evidence of a project; forms, procurement and budget acts are not.
            if not all(term in key for term in ('INFORMACION PUBLICA', 'BIENES Y DERECHOS AFECTADOS', 'PROYECTO')):
                continue
            item = {'notice_id': ident, 'titulo': title,
                    'url': BASE + '/tablondeanuncios/anuncio.aspx?id=' + ident,
                    'fecha_publicacion': date_value(dates[1]),
                    'fecha_fin_exposicion': date_value(dates[2])}
            if ident in notices and notices[ident] != item:
                raise ValueError('Conflicting duplicate notice')
            notices[ident] = item
        if not notices:
            raise ValueError('No supported current project notices; review source coverage')
        return list(notices.values()), total

    @staticmethod
    def parse_detail(html, notice):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#leer')
        heading = content.select_one('h2') if content else None
        if not heading or heading.get_text(' ', strip=True) != notice['titulo']:
            raise ValueError('Notice detail title mismatch')
        text = content.get_text(' ', strip=True)
        if not re.search(r'Código de anuncio:\s*' + re.escape(notice['notice_id']) + r'\b', text):
            raise ValueError('Notice detail identity mismatch')
        exposure = content.select_one('.fechas-exposicion')
        match = re.search(r'desde el día\s+(\d{2}/\d{2}/\d{4})', exposure.get_text(' ', strip=True) if exposure else '')
        if not match or date_value(match[1]) != notice['fecha_publicacion']:
            raise ValueError('Publication date mismatch')
        docs = {}
        for block in content.select('.adjunto'):
            link = block.select_one('a[href*="documento.aspx?"]')
            title = block.select_one('.adjunto-titulo')
            if not link or not title:
                raise ValueError('Unrecognised attachment markup')
            ident = resource_id(link['href'], 'documento')
            docs[ident] = {'id': ident, 'titulo': title.get_text(' ', strip=True),
                           'url': BASE + '/tablondeanuncios/documento.aspx?id=' + ident + '&modo=guardar'}
        if not docs:
            raise ValueError('Project notice lacks municipal documents')
        return list(docs.values())

    def _fetch(self, url, filename, limit=25_000_000):
        with requests.get(url, timeout=(10, 60), stream=True,
                          headers={'User-Agent': 'municipio-castejon/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).netloc != urlparse(BASE).netloc:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds response size limit')
                chunks.append(chunk)
            body = b''.join(chunks)
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture) / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        return body

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        html = self._fetch(SOURCE, 'inventory.html', 3_000_000).decode('utf-8-sig')
        notices, count = self.parse_inventory(html)
        rows, downloaded = [], {}
        for notice in notices:
            detail = self._fetch(notice['url'], 'notice-' + notice['notice_id'] + '.html', 3_000_000)
            docs = self.parse_detail(detail.decode('utf-8-sig'), notice)
            for doc in docs:
                if doc['id'] not in downloaded:
                    body = self._fetch(doc['url'], 'document-' + doc['id'] + '.pdf')
                    if not body.startswith(b'%PDF-'):
                        raise ValueError('Attachment is not the expected PDF')
                    downloaded[doc['id']] = hashlib.sha256(body).hexdigest()
                doc['sha256'] = downloaded[doc['id']]
            # Identity is the municipal notice. All attached documents belong to
            # one project record; they never become individual projects.
            rows.append({'id': 'castejon-proy-' + notice['notice_id'],
                         'municipio': 'Castejón', 'codigo_ine': '31070', 'provincia': 'Navarra',
                         'titulo': notice['titulo'], 'tipo': 'proyecto_infraestructura',
                         'fase': 'información pública de bienes y derechos afectados',
                         'fecha_publicacion': notice['fecha_publicacion'],
                         'fecha_fin_exposicion': notice['fecha_fin_exposicion'],
                         'fecha_acuerdo': None, 'fecha_aprob': None,
                         'url': notice['url'], 'source_url': SOURCE,
                         'source': 'ayuntamiento', 'origen': 'tablon_anuncios_vigentes',
                         'id_anuncio': notice['notice_id'], 'documentos': docs,
                         'lat': None, 'lon': None, 'geometry': None,
                         'geometry_status': 'unavailable', 'publication_ready': False,
                         'cobertura': 'Parcial: anuncios vigentes de información pública de bienes afectados por proyectos; sin histórico ni licencias.'})
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_notices': count, 'source': SOURCE,
                'coverage': 'partial_current_public_consultation', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh the entire current inventory; state is not a historical cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
