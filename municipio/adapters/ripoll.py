"""Ripoll's current municipal works-project inventory (not a licence register)."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://ripoll.cat/projectes-obres/'
HEADERS = ['Concepte', 'Aprovació inicial', 'Informació pública', 'Aprovació definitiva']


def _date(value):
    if value in {'', '-', '–', '—'}:
        return None
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


class RipollAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='ripoll', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://ripoll.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        # This source is a complete static table, not a search-results page.
        if soup.select('a[rel~=next], .pagination a, .page-numbers, .page-links a'):
            raise ValueError('Pagination detected; inventory coverage must be reviewed')
        tables = [t for t in soup.select('table')
                  if [c.get_text(' ', strip=True) for c in t.select('thead th')] == HEADERS]
        if len(tables) != 1:
            raise ValueError('Expected one municipal works-project table')
        rows, seen = [], set()
        for tr in tables[0].select('tbody > tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 4:
                raise ValueError('Unexpected project table row')
            anchors = cells[0].select('a[href]')
            if not anchors:
                raise ValueError('Project lacks source documents')
            title = re.sub(r'^\d+\s*[-–]\s*', '', anchors[0].get_text(' ', strip=True))
            if not title.startswith('Projecte '):
                raise ValueError('Non-project entry in works inventory')
            docs = {}
            for a in anchors:
                url = quote(urljoin(SOURCE, a['href']), safe=':/%?=&+#')
                parsed = urlsplit(url)
                if parsed.scheme != 'https' or parsed.hostname not in {'ripoll.cat', 'www.ripoll.cat'} or not parsed.path.lower().endswith('.pdf'):
                    raise ValueError('Unexpected municipal project document URL')
                docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                                      'source_url': SOURCE})
            initial, public, definitive = [_date(c.get_text(' ', strip=True)) for c in cells[1:]]
            key = hashlib.sha256(title.casefold().encode()).hexdigest()[:20]
            if key in seen:
                raise ValueError('Duplicate project identity')
            seen.add(key)
            rows.append({
                'id': 'ripoll-proy-' + key,
                'municipio': 'Ripoll', 'provincia': 'Girona', 'codigo_ine': '17147',
                'titulo': title, 'tipo': 'proyecto_obra_publica',
                'fase': ('aprobación definitiva' if definitive else
                         'información pública' if public else
                         'aprobación inicial' if initial else None),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': definitive or initial,
                'fecha_aprob_inicial': initial, 'fecha_aprob_definitiva': definitive,
                'fecha_informacion_publica': public,
                'url': SOURCE, 'url_documento': next(iter(docs)),
                'documentos': list(docs.values()), 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_projectes_obres',
                'date_provenance': dict(zip(HEADERS[1:], [c.get_text(' ', strip=True) for c in cells[1:]])),
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            })
        if not rows:
            raise ValueError('Empty municipal project inventory')
        return rows

    def fetch_inventory(self):
        """Fetch with verified TLS, optionally via an explicitly configured edge IP.

        SNI, certificate validation and HTTP Host always remain ripoll.cat.
        The fallback is useful where the DNS-selected Cloudflare edge times out.
        No local capture is substituted for a live response.
        """
        addresses = [None]
        if self.config.get('fallback_ipv4'):
            addresses.append(str(ipaddress.IPv4Address(self.config['fallback_ipv4'])))
        errors = []
        for address in addresses:
            conn = http.client.HTTPSConnection('ripoll.cat', timeout=8, context=ssl.create_default_context())
            try:
                if address:
                    sock = socket.create_connection((address, 443), timeout=8)
                    conn.sock = ssl.create_default_context().wrap_socket(sock, server_hostname='ripoll.cat')
                conn.request('GET', '/projectes-obres/', headers={
                    'User-Agent': self.config.get('user_agent', 'municipio-ripoll/1.0'),
                    'Accept': 'text/html',
                })
                response = conn.getresponse()
                if response.status != 200:
                    raise ValueError(f'Inventory HTTP {response.status}')
                if 'text/html' not in response.getheader('Content-Type', ''):
                    raise ValueError('Inventory is not HTML')
                body = response.read(3_000_001)
                if len(body) > 3_000_000:
                    raise ValueError('Inventory response exceeds size bound')
                return body.decode('utf-8'), {'source_url': SOURCE, 'http_status': response.status,
                                              'connect_ipv4': address, 'prior_errors': errors}
            except (OSError, http.client.HTTPException, ValueError) as exc:
                errors.append(f'{type(exc).__name__}: {exc}')
            finally:
                conn.close()
        raise RuntimeError('Unable to fetch Ripoll inventory: ' + '; '.join(errors))

    def backfill_proyectos(self, out_jsonl: Path):
        html, transport = self.fetch_inventory()
        rows = self.parse_projects(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'projectes-obres.html').write_text(html, encoding='utf-8')
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'transport': transport, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full refresh: all rows of the current inventory; no historical deletion claim.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
