"""Municipal planning catalogue: one instrument per document entry, not per PDF."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.motilla.com/documento-categoria/urbanismo-planeamiento/'
HOST = 'www.motilla.com'


def _official(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname == HOST and not parsed.username


def _norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper()


def parse_inventory(html, page_url=SOURCE):
    """Return grouped records, all pagination links and explicitly excluded entries."""
    soup = BeautifulSoup(html, 'html.parser')
    articles = soup.select('article.lsvr_document')
    if not articles:
        raise ValueError('Missing municipal planning catalogue articles')
    rows, excluded = {}, []
    for article in articles:
        anchor = article.select_one('.post__title-link[href]')
        if anchor is None:
            raise ValueError('Catalogue entry without title link')
        title = anchor.get_text(' ', strip=True)
        norm = _norm(title)
        url = urljoin(page_url, anchor['href']).split('#')[0]
        if not _official(url) or not urlparse(url).path.startswith('/documentos/'):
            raise ValueError('Unexpected instrument provenance')
        if re.search(r'\b(SOLICITUD|FORMULARIO|LICITACION|CONTRATACION)\b', norm):
            excluded.append({'titulo': title, 'url': url, 'reason': 'procedure_or_procurement'})
            continue
        docs = {}
        for link in article.select('.post__attachment-link[href]'):
            doc_url = urljoin(page_url, link['href']).split('#')[0]
            if not _official(doc_url) or not urlparse(doc_url).path.lower().endswith('.pdf'):
                raise ValueError('Unexpected planning attachment URL')
            docs[doc_url] = {'titulo': link.get_text(' ', strip=True), 'url': doc_url,
                             'source_url': url, 'inventory_url': page_url}
        if not docs:
            raise ValueError('Instrument without source documents')
        if 'MOD' in norm and re.search(r'MOD(?:IFICACION|PUNT|\s*PUNT|\d)', norm):
            kind = 'modificacion_planeamiento'
        elif 'NORMAS SUBSIDIARIAS' in norm:
            kind = 'normas_subsidiarias'
        elif re.search(r'\bPAU\b', norm):
            kind = 'programa_actuacion_urbanizadora'
        elif re.search(r'\bED\b|ESTUDIO DE DETALLE', norm):
            kind = 'estudio_detalle'
        elif re.search(r'\bPP\b|PLAN PARCIAL', norm):
            kind = 'plan_parcial'
        elif any('PERI' in _norm(d['titulo']) for d in docs.values()):
            kind = 'plan_especial_reforma_interior'
        else:
            raise ValueError(f'Unreviewed planning catalogue entry: {title}')
        ids = [c[5:] for c in article.get('class', []) if re.fullmatch(r'post-\d+', c)]
        if len(ids) != 1:
            raise ValueError('Missing stable municipal catalogue ID')
        row = {
            'id': 'motilla-del-palancar-proy-' + ids[0], 'id_origen': ids[0],
            'municipio': 'Motilla del Palancar', 'codigo_ine': '16134', 'provincia': 'Cuenca',
            'titulo': title, 'tipo': kind, 'source': 'ayuntamiento',
            'origen': 'inventario_municipal_planeamiento', 'url': url,
            'source_urls': [page_url, url], 'documentos': list(docs.values()),
            # Catalogue title dates have no explicit event semantics. Preserve
            # the complete title instead of interpreting them as approvals.
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None, 'fecha_texto_origen': title,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }
        if row['id'] in rows and rows[row['id']] != row:
            raise ValueError('Conflicting duplicate catalogue identity')
        rows[row['id']] = row

    pages = set()
    prefix = urlparse(SOURCE).path
    for link in soup.select('a[href], link[rel=next][href]'):
        target = urljoin(page_url, link['href']).split('#')[0]
        label = _norm(link.get_text(' ', strip=True))
        rel = link.get('rel', [])
        pagination = (bool(re.search(r'/page/\d+/?$', urlparse(target).path))
                      or 'paged=' in target or 'next' in rel
                      or label in {'SIGUIENTE', 'NEXT', '»', '›'})
        if not pagination:
            continue
        if not _official(target) or not urlparse(target).path.startswith(prefix):
            raise ValueError('Unreviewed pagination destination')
        pages.add(target)
    return list(rows.values()), sorted(pages), excluded


class MotillaDelPalancarAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-motilla-planning/1.0'}, stream=True)
        with response:
            response.raise_for_status()
            if not _official(response.url):
                raise ValueError('Source redirected outside official municipal host')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected municipal HTML inventory')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 8_000_000:
                    raise ValueError('Inventory exceeds size guard; no partial output')
                chunks.append(chunk)
            body = b''.join(chunks)
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / f'inventory-{len(self.source_urls)}.html').write_bytes(body)
        return body.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, seen, rows, excluded = [SOURCE], set(), {}, []
        self.source_urls = []
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            if len(seen) >= 100:
                raise ValueError('Pagination guard exceeded; no partial output')
            seen.add(url)
            self.source_urls.append(url)
            parsed, pages, skipped = parse_inventory(self._fetch(url), url)
            excluded.extend(skipped)
            for row in parsed:
                old = rows.get(row['id'])
                if old:
                    # Repeated entries across pages must have identical content.
                    comparable = {k: v for k, v in old.items() if k not in {'source_urls', 'documentos'}}
                    if comparable != {k: v for k, v in row.items() if k not in {'source_urls', 'documentos'}}:
                        raise ValueError('Conflicting paginated instrument')
                    old_docs = {d['url']: d for d in old['documentos']}
                    for doc in row['documentos']:
                        old_docs.setdefault(doc['url'], doc)
                    old['documentos'] = list(old_docs.values())
                    old['source_urls'] = sorted(set(old['source_urls'] + row['source_urls']))
                else:
                    rows[row['id']] = row
            pending.extend(p for p in pages if p not in seen and p not in pending)
        if not rows:
            raise ValueError('No usable planning instruments; manual source review required')
        self._write(out_jsonl, list(rows.values()))
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'excluded': excluded, 'coverage': 'current municipal planning catalogue only'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
