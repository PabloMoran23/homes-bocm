"""Complete snapshot of Santpedor's municipal Projectes urbanístics inventory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.santpedor.cat'
SOURCE = BASE + '/regidories-i-serveis/urbanisme/projectes-urbanistics'
DOCUMENT_HOSTS = {'www.santpedor.cat', 'santpedor.cat', 'santpedor.webmunicipal.diba.cat'}


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('main #readspeakerPage')
    if content is None or content.select_one('h1') is None:
        raise ValueError('Missing municipal article; possible login or changed markup')
    return soup, content


def _check_pagination(soup):
    # Reviewed source is unpaginated. Fail explicitly if this changes, including
    # numbered controls, rather than silently returning only its first page.
    if soup.select('.pagination, .pager, [rel~=next]'):
        raise ValueError('Pagination detected; crawler must be extended before extraction')
    for a in soup.select('main a[href]'):
        if (a.get_text(' ', strip=True).lower() in {'següent', 'següents', 'siguiente', 'next', '›', '»'}
                or re.search(r'[?&](?:page|pagina|p|offset|start)=', a['href'], re.I)):
            raise ValueError('Pagination detected; refusing a partial inventory')


def _kind(title):
    if title.startswith('Projecte ') or title.startswith("Memòria elaborada per l'arranjament"):
        return 'obra_publica'
    if title.startswith('Pla de delimitació'):
        return 'plan_prevencion_incendios'
    raise ValueError('Unreviewed inventory entry: ' + title)


class SantpedorAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html):
        soup, content = _content(html)
        _check_pagination(soup)
        if content.h1.get_text(' ', strip=True) != 'Projectes urbanístics':
            raise ValueError('Unexpected municipal inventory heading')
        links = {}
        for a in content.select('.widgetMenu a[href]'):
            url = urljoin(SOURCE, a['href'])
            path = urlsplit(url)
            if (path.scheme != 'https' or path.netloc != 'www.santpedor.cat'
                    or not url.startswith(SOURCE + '/') or path.query or path.fragment):
                raise ValueError('Unexpected inventory destination: ' + url)
            title = a.get_text(' ', strip=True)
            _kind(title)
            if url in links and links[url] != title:
                raise ValueError('Conflicting titles for the same project')
            links[url] = title
        if not links:
            raise ValueError('Empty or changed project inventory')
        return list(links.items())

    @staticmethod
    def parse_project(html, url, expected_title):
        soup, content = _content(html)
        _check_pagination(soup)
        title = content.h1.get_text(' ', strip=True)
        if title != expected_title:
            raise ValueError('Project detail does not match inventory title')
        body = content.select_one('.ddbbtext')
        if body is None:
            raise ValueError('Project lacks technical content')
        documents = {}
        for a in body.select('a[href]'):
            href = urljoin(url, a['href'])
            parsed = urlsplit(href)
            if parsed.scheme != 'https':
                raise ValueError('Unexpected document protocol')
            label = a.get_text(' ', strip=True)
            pdf = parsed.hostname in DOCUMENT_HOSTS and parsed.path.lower().endswith('.pdf')
            notice = parsed.hostname == 'tauler.seu-e.cat' and parsed.path == '/detall'
            if not pdf and not notice:
                raise ValueError('Unreviewed project attachment: ' + href)
            role = 'anuncio' if notice or label.lower() == 'anunci' else 'documento_tecnico'
            documents.setdefault(href, {
                'titulo': label, 'url': href, 'tipo': role, 'source_url': url,
            })
        technical = [d for d in documents.values() if d['tipo'] == 'documento_tecnico']
        if not technical:
            raise ValueError('Notice alone is not a verified technical project')
        updated = content.select_one('.updated')
        match = re.search(r'(\d{2}\.\d{2}\.\d{4})', updated.get_text() if updated else '')
        page_updated = datetime.strptime(match[1], '%d.%m.%Y').date().isoformat() if match else None
        return {
            'id': 'santpedor-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Santpedor', 'provincia': 'Barcelona', 'codigo_ine': '08192',
            'titulo': title, 'tipo': _kind(title), 'fase': None,
            'descripcion': body.get_text(' ', strip=True),
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fecha_actualizacion_pagina': page_updated,
            'url': url, 'url_documento': technical[0]['url'],
            'documentos': list(documents.values()), 'source_url': url,
            'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'projectes_urbanistics_municipals',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified machine-readable project geometry extracted',
        }

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 40), stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-santpedor/1.0'),
        }) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'www.santpedor.cat':
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Municipal HTML exceeds size limit')
                chunks.append(chunk)
            raw = b''.join(chunks)
            capture_dir = self.config.get('capture_dir')
            if capture_dir:
                path = Path(capture_dir)
                path.mkdir(parents=True, exist_ok=True)
                (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(raw)
            return raw.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        inventory = self.parse_inventory(self._fetch(SOURCE))
        rows = [self.parse_project(self._fetch(url), url, title) for url, title in inventory]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [r['url'] for r in rows],
                'publication_ready': False, 'coverage': 'Complete current Projectes urbanístics page; partial municipal coverage'}

    def update_proyectos(self, out_jsonl, state_path):
        # Re-read the full inventory, including every detail, on each refresh.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
