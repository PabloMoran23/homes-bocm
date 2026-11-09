"""Sant Lluís municipal planning catalogue (partial, document-level provenance)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, quote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.ajsantlluis.org'
SOURCE = BASE + '/Contingut.aspx?IdPub=37089'


def canonical(url):
    parts = urlsplit(url)
    if parts.hostname != 'www.ajsantlluis.org' or parts.scheme != 'https':
        raise ValueError('Unexpected non-municipal catalogue URL: ' + url)
    query = {k.lower(): v for k, v in parse_qs(parts.query).items()}
    if parts.path.lower() == '/contingut.aspx' and 'idpub' in query:
        return BASE + '/Contingut.aspx?IdPub=' + str(int(query['idpub'][0]))
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe='/%'), parts.query, ''))


class SantLluisAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_page(html, url):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.PLA_texte')
        heading = soup.select_one('h1')
        if not content or not heading or 'NORMATIVA URBANÍSTICA DE SANT LLUÍS' != heading.get_text(' ', strip=True):
            raise ValueError('Planning catalogue missing or changed')
        # These are static tabbed inventories. Refuse newly introduced paging
        # rather than outputting an unannounced first page.
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            href = a['href']
            if (a.get('rel') == ['next'] or label in {'següent', 'siguiente', 'next', 'més', 'més resultats'}
                    or re.search(r'(?:[?&](?:page|pagina|offset)=|Page\$)', href, re.I)):
                raise ValueError('Unreviewed catalogue pagination')
        active = content.select_one('a.boton2')
        if not active:
            raise ValueError('Missing active catalogue tab')
        label = active.get_text(' ', strip=True)
        nnss = label.startswith('Normes Subsidiàries')
        if not nnss and label != 'Altres normatives urbanístiques':
            raise ValueError('Unknown catalogue tab: ' + label)
        links = []
        for a in content.select('a.boton[href], a.boton2[href]'):
            if not a['href'].startswith('#'):
                linked = canonical(urljoin(url, a['href']))
                if '/Contingut.aspx?IdPub=' not in linked:
                    raise ValueError('Unknown catalogue navigation')
                if linked not in links:
                    links.append(linked)
        groups = {}
        section = None
        for node in content.find_all(['strong', 'a']):
            if node.name == 'strong':
                section = node.get_text(' ', strip=True)
            elif node.has_attr('href') and urlsplit(node['href']).path.lower().endswith('.pdf'):
                title = node.get_text(' ', strip=True)
                if not title:
                    raise ValueError('Untitled catalogue document')
                group = 'Normes Subsidiàries de Sant Lluís' if nnss else section
                if not group:
                    raise ValueError('Ungrouped planning document')
                doc = {'titulo': title, 'url': canonical(urljoin(url, node['href'])),
                       'source_url': url, 'seccion': label if nnss else section}
                groups.setdefault(group, {})[doc['url']] = doc
        if not groups:
            raise ValueError('Catalogue contains no documents')
        if nnss and not any('normativ' in d['url'].lower() for docs in groups.values() for d in docs.values()):
            raise ValueError('NNSS normative document missing')
        return links, {name: list(docs.values()) for name, docs in groups.items()}

    def backfill_proyectos(self, out_jsonl):
        pending, seen, grouped = [SOURCE], set(), {}
        capture_dir = self.config.get('capture_dir')
        session = requests.Session()
        session.headers['User-Agent'] = 'municipio-sant-lluis/1.0'
        try:
            while pending:
                url = pending.pop(0)
                if url in seen:
                    continue
                if len(seen) >= 20:
                    raise ValueError('Catalogue grew beyond reviewed scope; no output written')
                response = session.get(url, timeout=35)
                response.raise_for_status()
                if canonical(response.url) != url:
                    raise ValueError('Unexpected catalogue redirect')
                if capture_dir:
                    directory = Path(capture_dir)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / ('catalogue-' + url.rsplit('=', 1)[-1] + '.html')).write_bytes(response.content)
                links, groups = self.parse_page(response.content, url)
                seen.add(url)
                pending.extend(link for link in links if link not in seen)
                for title, docs in groups.items():
                    # Camp Sarc is a standalone ordinance resource, not a
                    # verified project/plan; catalogue traversal still covers it.
                    if title != 'Normes Subsidiàries de Sant Lluís' and not title.startswith('Pla Especial de '):
                        if title != 'Nucli Rural Camp Sarc':
                            raise ValueError('Unreviewed catalogue group: ' + title)
                        continue
                    group = grouped.setdefault(title, {'docs': {}, 'sources': set()})
                    group['sources'].add(url)
                    group['docs'].update({doc['url']: doc for doc in docs})
        finally:
            session.close()
        if len(seen) < 3 or not grouped:
            raise ValueError('Incomplete catalogue tabs')
        rows = []
        for title, group in sorted(grouped.items()):
            sources = sorted(group['sources'])
            rows.append({
                'id': 'sant-lluis-proy-' + hashlib.sha256(title.encode()).hexdigest()[:16],
                'municipio': 'Sant Lluís', 'codigo_ine': '07052', 'provincia': 'Illes Balears',
                'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'url': SOURCE if title.startswith('Normes') else sources[0],
                'source': 'ayuntamiento', 'origen': 'catalogo_planeamiento_municipal',
                'source_urls': sources, 'documentos': list(group['docs'].values()),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False,
                'coverage': 'Catálogo municipal parcial; fechas no extraídas de los PDF; sin geometría vectorial verificada.',
            })
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(seen)}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
