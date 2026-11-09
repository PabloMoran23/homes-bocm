"""Oroso's municipal planning documents; a complete snapshot of a limited inventory."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.oroso.gal/show_content.php?section=5&subsection=27'
LEGACY = 'https://www.concellooroso.com/pxom/'
LIMITATIONS = [
    'Partial municipal coverage: published PXOM original, San Martiño II partial plan and Sector 10 reparcelación only; not the complete planning history or amendments in SIOTUGA.',
    'Document links retain municipal labels; attachments are not all downloaded or legally validated. Source labels may contain errors.',
    'Only PXOM approval date is stated by the municipal page. Publication and other agreement/approval dates are unknown.',
    'No verified project geometry; PDF plans are retained as documents, without invented coordinates.',
    'No granted licence register extracted; licences disabled. News and procurement notices excluded.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    for link in soup.select('a[href], link[href]'):
        label = link.get_text(' ', strip=True).casefold()
        rel = link.get('rel', [])
        if 'next' in rel or label in {'seguinte', 'siguiente', 'next', 'seguinte »', 'siguiente »'} or link.has_attr('data-page'):
            raise ValueError('Unexpected pagination: review inventory traversal before accepting snapshot')
    return soup


def _documents(links, source_url):
    """One attachment per URL; preserve alternative labels and listing provenance."""
    docs = {}
    for title, url in links:
        doc = docs.setdefault(url, {'titulo': title, 'url': url, 'titulos_fuente': [], 'source_urls': []})
        if title and title not in doc['titulos_fuente']:
            doc['titulos_fuente'].append(title)
        if source_url not in doc['source_urls']:
            doc['source_urls'].append(source_url)
    return list(docs.values())


def parse_inventory(html):
    soup = _soup(html)
    heading = soup.find('h2', string=re.compile('Oficina Municipal de Urbanismo'))
    if not heading:
        raise ValueError('Missing municipal urban planning inventory')
    # The approval statement is in the entry content, not a date in the footer.
    content = heading.find_parent(class_='entry') or heading.parent.parent
    text = content.get_text(' ', strip=True)
    approval = re.search(r'PXOM\), aprobado definitivamente na orde (\d{2}/\d{2}/\d{2})', text)
    if not approval:
        raise ValueError('Missing explicit original PXOM approval statement')
    pxom_links = [urljoin(SOURCE, a['href']) for a in soup.select('a[href]')
                  if urljoin(SOURCE, a['href']) == LEGACY + 'index.htm']
    if not pxom_links:
        raise ValueError('Missing original PXOM document inventory link')
    modal_heading = soup.find('h4', string=re.compile('Polígono Industrial San Martiño II'))
    modal = modal_heading.find_parent(class_='modal-content') if modal_heading else None
    if not modal or 'Plan Parcial do Área de Reparto Número 10' not in modal.get_text(' ', strip=True):
        raise ValueError('Missing identified San Martiño partial plan')
    if not modal.find('h4', string=re.compile('Proxecto de reparcelación do Sector 10')):
        raise ValueError('Missing identified Sector 10 reparcelación')
    groups = {'plan-parcial-san-martino-ii': [], 'reparcelacion-sector-10': []}
    for a in modal.select('a[href]'):
        url = urldefrag(urljoin(SOURCE, a['href']))[0]
        parsed = urlparse(url)
        if parsed.hostname != 'www.concellooroso.com' or not parsed.path.startswith('/polsmar/'):
            continue
        if not parsed.path.lower().endswith(('.pdf', '.zip')):
            raise ValueError('Unexpected partial-plan document type: ' + url)
        key = 'reparcelacion-sector-10' if '/reparcelacion/' in parsed.path else 'plan-parcial-san-martino-ii'
        groups[key].append((a.get_text(' ', strip=True), url))
    rows = []
    for key, title, kind in [
        ('pxom', 'Plan Xeral de Ordenación Municipal de Oroso', 'plan_xeral'),
        ('plan-parcial-san-martino-ii', 'Plan Parcial do Área de Reparto Número 10, Polígono Empresarial San Martiño II', 'plan_parcial'),
        ('reparcelacion-sector-10', 'Proxecto de reparcelación do Sector 10', 'reparcelacion'),
    ]:
        docs = _documents(groups.get(key, []), SOURCE)
        if key != 'pxom' and not docs:
            raise ValueError('Instrument without source documents: ' + key)
        row = {'id': 'oroso-proy-' + key, 'municipio': 'Oroso', 'codigo_ine': '15060',
               'provincia': 'A Coruña', 'titulo': title, 'tipo': kind,
               'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
               'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
               'documentos': docs, 'lat': None, 'lon': None, 'geometry': None,
               'geometry_status': 'unavailable', 'publication_ready': False,
               'coverage': 'partial', 'limitations': LIMITATIONS}
        if key == 'pxom':
            row.update(fecha_aprob=datetime.strptime(approval[1], '%d/%m/%y').date().isoformat(),
                       fase='aprobación definitiva', url_inventario_documentos=pxom_links[0],
                       fecha_aprob_source_url=SOURCE, fecha_aprob_texto=approval[0])
        else:
            row['descripcion'] = modal.find('p').get_text(' ', strip=True) if key.startswith('plan-parcial') else title
        rows.append(row)
    return rows


def parse_pxom_page(html, source_url):
    """Read frames, ordinary links, image maps and literal legacy JS submenu HTML.

    No external JavaScript is executed. All linked HTML within /pxom/ is traversed.
    """
    soup = _soup(html)
    fragments = [soup]
    for script in soup.find_all('script'):
        text = script.get_text()
        assignments = re.findall(r'submenu\[\d+\]\s*=', text)
        matches = list(re.finditer(r"submenu\[\d+\]\s*=\s*'([^'\n]*)'", text))
        if len(matches) != len(assignments):
            raise ValueError('Changed PXOM JavaScript submenu syntax; review before accepting snapshot')
        for match in matches:
            fragments.append(_soup(match[1]))
    pages, docs = set(), []
    for fragment in fragments:
        for node in fragment.select('a[href], area[href], frame[src], iframe[src]'):
            href = node.get('href', node.get('src', ''))
            url = urldefrag(urljoin(source_url, href))[0]
            if not url.startswith(LEGACY):
                continue
            path = urlparse(url).path.lower()
            if path.endswith(('.htm', '.html')):
                pages.add(url)
            elif path.endswith(('.pdf', '.zip')):
                docs.append((node.get_text(' ', strip=True) or node.get('alt') or path.rsplit('/', 1)[-1], url))
            else:
                raise ValueError('Unreviewed PXOM link type: ' + url)
    return pages, _documents(docs, source_url)


class OrosoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=35)
        response.raise_for_status()
        if response.url != url:
            raise ValueError('Unexpected source redirect: ' + response.url)
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML inventory: ' + url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (directory / name).write_bytes(response.content)
            self.captures.append({'url': url, 'file': name, 'status_code': response.status_code,
                                  'sha256': hashlib.sha256(response.content).hexdigest()})
        # Legacy pages contain Windows-1252, including when headers omit charset.
        encoding = response.encoding if 'charset=' in response.headers.get('Content-Type', '').lower() else 'windows-1252' if url.startswith(LEGACY) else 'utf-8'
        return response.content.decode(encoding or 'utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.captures = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-oroso/1.0 (public planning inventory)'
            rows = parse_inventory(self._fetch(session, SOURCE))
            pending, seen, docs = {rows[0]['url_inventario_documentos']}, set(), {}
            while pending:
                if len(seen) >= 100:
                    raise ValueError('PXOM traversal exceeds safety bound; no partial output written')
                url = min(pending)
                pending.remove(url)
                time.sleep(0.15)
                pages, attachments = parse_pxom_page(self._fetch(session, url), url)
                seen.add(url)
                pending.update(pages - seen)
                for doc in attachments:
                    if doc['url'] not in docs:
                        docs[doc['url']] = doc
                    else:
                        for field in ('titulos_fuente', 'source_urls'):
                            docs[doc['url']][field] = sorted(set(docs[doc['url']][field] + doc[field]))
            if not docs:
                raise ValueError('PXOM inventory yielded no documents')
            rows[0]['documentos'] = sorted(docs.values(), key=lambda d: d['url'])
        self._write(out_jsonl, rows)
        if self.config.get('capture_dir'):
            (Path(self.config['capture_dir']) / 'index.json').write_text(json.dumps(self.captures, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + sorted(seen),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
