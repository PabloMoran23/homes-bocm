"""Villamayor (37354): official JCyL planning archive linked by the Diputación."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://servicios.jcyl.es/PlanPublica/'
SOURCE = BASE + 'searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=354'
SUPPORTED = {'PU': {'PGOU', 'NUM', 'NS', 'DSU', 'ED', 'PP', 'PPI', 'PE', 'PERI', 'PEP', 'PECH'},
             'GU': {'PEX', 'PAU', 'PN'}}


def canonical(href: str, base: str = BASE) -> str:
    url = re.sub(r';jsessionid=[^?/#]*', '', urljoin(base, href))
    if urlsplit(url).netloc != 'servicios.jcyl.es' or not urlsplit(url).path.startswith('/PlanPublica/'):
        raise ValueError('Unexpected planning archive URL')
    return url


def page_url(offset: int) -> str:
    # The unparameterised landing page is NOT sorted like its AJAX pagination.
    return BASE + 'searchVPubDocMuniPlau.do?' + urlencode({
        'pager.size': 15, 'pager.reload': 'no', 'municipio': '354', 'provincia': '37',
        'bInfoPublica': 'N', 'urlResults': 'searchVPubDocMuniPlau.do',
        'pager.offset': offset, 'pager.sortindex': '-3', 'pager.sortname': 'fPublicacion',
    })


def source_date(text: str) -> str | None:
    return datetime.strptime(text, '%d/%m/%Y').date().isoformat() if text else None


def parse_inventory(html: str, url: str) -> tuple[list[dict], tuple[int, int, int]]:
    soup = BeautifulSoup(html, 'html.parser')
    summary = re.search(r'Mostrando resultados\s+(\d+)\s*-\s*(\d+)\s+de\s+(\d+)',
                        soup.get_text(' ', strip=True))
    if not summary:
        raise ValueError('Missing archive pagination totals')
    bounds = tuple(map(int, summary.groups()))
    rows = []
    for tr in soup.select('table.cuadroAplicacion tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 6:
            raise ValueError('Changed archive row schema')
        book, instrument, publication, agreement, title = [c.get_text(' ', strip=True) for c in cells[:5]]
        ids = set(re.findall(r'cDocId=(\d+)', str(tr)))
        ids.update(re.findall(r"doGoBoletin\('(\d+)'", str(tr)))
        if len(ids) != 1 or not title:
            raise ValueError('Missing or ambiguous archive identifier/title')
        doc_id = ids.pop()
        # Parse every row before filtering, so unsupported rows cannot mask loss.
        row = {'id': 'villamayor-plau-' + doc_id, 'archivo_id': doc_id,
               'municipio': 'Villamayor', 'codigo_ine': '37354', 'provincia': 'Salamanca',
               'titulo': title, 'tipo': instrument, 'libro': book,
               'fecha_publicacion': source_date(publication), 'fecha_acuerdo': source_date(agreement),
               'source': 'jcyl', 'origen': 'archivo_planeamiento_urbanistico',
               'inventory_url': url, 'source_inventory_url': SOURCE,
               'documentos': [], 'geometry': None, 'lat': None, 'lon': None,
               'geometry_status': 'unavailable', 'publication_ready': False}
        for a in cells[5].select('a[href]'):
            target = canonical(a['href'])
            if 'ldoc_files.do?' in target:
                row['files_url'] = target
            elif 'openDocuIndice.do?' in target:
                row['url'] = target
        if cells[2].select_one('[onclick]'):
            row['boletin_url'] = BASE + 'openBoletinDoc.do?cDocId=' + doc_id
            row['documentos'].append({'titulo': 'Boletín enlazado por el archivo',
                                      'url': row['boletin_url'], 'procedencia': url})
        row.setdefault('url', row.get('boletin_url', url))
        row['documentacion_status'] = 'ficheros_enlazados' if 'files_url' in row else 'sin_ficheros_en_archivo'
        rows.append(row)
    start, end, total = bounds
    if not (1 <= start <= end <= total) or len(rows) != end - start + 1:
        raise ValueError('Archive row count disagrees with pagination')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate archive identifiers within page')
    return rows, bounds


def parse_files(html: str, url: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    headings = ' '.join(h.get_text(' ', strip=True) for h in soup.select('h1'))
    if not re.search(r'Villamayor\s*\(Salamanca\s*\)', headings, re.I):
        raise ValueError('File listing is not for Villamayor (Salamanca)')
    docs = {}
    for tr in soup.select('table.cuadroAplicacion tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        a = tr.select_one('a[href*="openFichero.do"]')
        if not a or len(cells) != 2:
            raise ValueError('Changed archive file listing')
        target = canonical(a['href'])
        if not re.fullmatch(r'\d+', parse_qs(urlsplit(target).query).get('cFicheroId', [''])[0]):
            raise ValueError('Missing file identifier')
        docs[target] = {'titulo': cells[0].get_text(' ', strip=True), 'url': target, 'procedencia': url}
    if not docs:
        raise ValueError('Advertised file listing contains no files')
    if soup.find(string=re.compile(r'Mostrando resultados|Siguiente')):
        raise ValueError('File listing has pagination; review before accepting partial documents')
    return list(docs.values())


def write_jsonl(path: Path, rows: list[dict]) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    temp.replace(path)
    return {'status': 'ok', 'rows': len(rows)}


class VillamayorAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        source_urls = []
        captures = self.config.get('evidence_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-villamayor/1.0 (public planning inventory)'

            def fetch(url):
                url = canonical(url)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                canonical(response.url)
                response.encoding = 'utf-8'
                source_urls.append(url)
                if captures:
                    dest = Path(captures)
                    dest.mkdir(parents=True, exist_ok=True)
                    (dest / f'source-{len(source_urls):03d}.html').write_text(response.text, encoding='utf-8')
                time.sleep(0.15)
                return response.text

            landing = BeautifulSoup(fetch(SOURCE), 'html.parser').get_text(' ', strip=True)
            if not re.search(r'VILLAMAYOR\s+Código INE:\s*37354\b', landing):
                raise ValueError('Archive municipality identity changed')
            all_rows = {}
            offset, total = 0, None
            while total is None or offset < total:
                url = page_url(offset)
                rows, (start, end, reported_total) = parse_inventory(fetch(url), url)
                if start != offset + 1 or (total is not None and total != reported_total):
                    raise ValueError('Inconsistent archive pagination snapshot')
                total = reported_total
                for row in rows:
                    if row['id'] in all_rows:
                        raise ValueError('Repeated archive page/identifier; refusing truncated snapshot')
                    all_rows[row['id']] = row
                offset = end
            if len(all_rows) != total:
                raise ValueError('Incomplete planning inventory')
            selected = [r for r in all_rows.values() if r['tipo'] in SUPPORTED.get(r['libro'], set())]
            if not selected:
                raise ValueError('No usable planning instruments or projects')
            for row in selected:
                if 'files_url' in row:
                    row['documentos'].extend(parse_files(fetch(row['files_url']), row['files_url']))
            result = write_jsonl(out_jsonl, selected)
            return {**result, 'inventory_rows': total, 'excluded_rows': total - len(selected),
                    'source_urls': source_urls, 'coverage': 'current PLAU inventory; historical checkbox off',
                    'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh; a failed fetch never replaces the previous snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**write_jsonl(out_jsonl, []), 'status': 'disabled',
                'reason': 'No verified register of granted licences; application forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
