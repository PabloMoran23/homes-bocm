"""Municipal POUM snapshot, grouping the technical documents and notices."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.svmontalt.cat'
SOURCE = BASE + '/ambit.php?id=71'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial coverage: only the new POUM initial-approval dossier, not the full RPUC or historical planning inventory.',
    'The new POUM is not definitively approved; the municipal page states the 1986 subsidiary rules remain in force.',
    'PDF links are retained as provenance; PDF contents and vector geometry are not extracted.',
    'No verified project coordinates or granted-licence register; publication_ready is false.',
    'Updates refresh this complete dossier snapshot; they do not preserve a historical event log.',
]


def _date(text):
    match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', text)
    if not match or match[2] not in MONTHS:
        raise ValueError('Expected an explicit Catalan calendar date')
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def _content(html, selector):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one(selector)
    if content is None:
        raise ValueError('Municipal source content missing: ' + selector)
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
                re.fullmatch(r'(següent|següents|siguiente|next|»|›)', a.get_text(' ', strip=True), re.I)):
            if a['href'] not in ('', '#'):
                raise ValueError('Pagination appeared; refusing an incomplete snapshot')
    return content


def _municipal_link(content, label):
    links = {urljoin(SOURCE, a['href']) for a in content.select('a[href]')
             if a.get_text(' ', strip=True).casefold() == label}
    if len(links) != 1:
        raise ValueError('Missing or ambiguous dossier index: ' + label)
    link = links.pop()
    if urlparse(link).netloc != 'www.svmontalt.cat' or urlparse(link).path != '/pagina.php':
        raise ValueError('Dossier index moved outside the reviewed municipal source')
    return link


def _documents(html, source_url, kind):
    content = _content(html, '#cos')
    docs = {}
    for a in content.select('a[href]'):
        url = urljoin(source_url, a['href'])
        parsed = urlparse(url)
        if parsed.path.lower().endswith('.pdf'):
            if parsed.netloc != 'www.svmontalt.cat' or not parsed.path.startswith('/ARXIUS/'):
                raise ValueError('Document provenance changed: ' + url)
            title = a.get_text(' ', strip=True)
            docs.setdefault(url, {'url': url, 'titulo': title or parsed.path.rsplit('/', 1)[-1],
                                  'tipo': kind, 'source_url': source_url})
            if title:
                docs[url]['titulo'] = title
    if not docs:
        raise ValueError('POUM index has no source PDF documents')
    return list(docs.values())


class SantVicencDeMontaltAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def discover(html):
        content = _content(html, '#PRESENTACIO .presentacio')
        return (_municipal_link(content, 'consulta la documentació'),
                _municipal_link(content, 'consulta els anuncis'))

    @classmethod
    def parse_projects(cls, overview, documents_html, notices_html):
        document_url, notice_url = cls.discover(overview)
        content = _content(overview, '#PRESENTACIO .presentacio')
        paragraphs = [p.get_text(' ', strip=True) for p in content.select('p')]
        approvals = [p for p in paragraphs if 'el Ple en sessió' in p and
                     "va aprovar inicialment el Pla d'Ordenació Urbanística Municipal (POUM)" in p]
        if len(approvals) != 1 or 'FASE APROVACIÓ INICIAL POUM' not in content.get_text(' ', strip=True):
            raise ValueError('Reviewed POUM initial-approval narrative missing or ambiguous')
        agreement = _date(approvals[0])
        notices = _content(notices_html, '#DOCUMENT .dinssinopsi')
        publications = []
        for li in notices.select('li'):
            text = li.get_text(' ', strip=True)
            if re.match(r'^(Seu Electrònica|BOPB|DOGC|Diari El Punt Avui|Diari La Vanguardia):', text):
                publications.append({'medio': text.split(':', 1)[0], 'fecha_publicacion': _date(text),
                                     'source_url': notice_url})
        bop_dates = {p['fecha_publicacion'] for p in publications if p['medio'] == 'BOPB'}
        if len(bop_dates) != 1:
            raise ValueError('Missing or conflicting explicit BOPB publication date')
        docs = _documents(documents_html, document_url, 'documentacion_tecnica')
        docs += _documents(notices_html, notice_url, 'anuncio')
        return [{
            'id': 'sant-vicenc-de-montalt-poum-ambit-71',
            'municipio': 'Sant Vicenç de Montalt', 'codigo_ine': '08264', 'provincia': 'Barcelona',
            'titulo': "Pla d'Ordenació Urbanística Municipal de Sant Vicenç de Montalt (POUM)",
            'tipo': 'POUM', 'fase': 'aprobación inicial',
            'fecha': None, 'fecha_acuerdo': agreement, 'fecha_aprob': agreement,
            'fecha_publicacion': next(iter(bop_dates)), 'medio_publicacion': 'BOPB',
            'publicaciones': publications,
            'descripcion': approvals[0], 'url': SOURCE, 'url_documento': document_url,
            'source': 'ayuntamiento', 'origen': 'planejament_municipal',
            'source_urls': [SOURCE, document_url, notice_url], 'documentos': docs,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'limitations': LIMITATIONS,
        }]

    def _fetch(self, url, capture_name):
        with requests.get(url, timeout=30, stream=True,
                          headers={'User-Agent': 'municipio-sant-vicenc-de-montalt/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).netloc != 'www.svmontalt.cat':
                raise ValueError('Unexpected redirect outside the municipality')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 3_000_000:
                    raise ValueError('Municipal HTML exceeds response size limit')
            # This portal declares ISO-8859-1; let its HTML meta declaration
            # drive BeautifulSoup decoding instead of forcing UTF-8.
            payload = bytes(data)
            if self.config.get('evidence_dir'):
                directory = Path(self.config['evidence_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                (directory / capture_name).write_bytes(payload)
            return payload

    def backfill_proyectos(self, out_jsonl):
        overview = self._fetch(SOURCE, 'poum.html')
        document_url, notice_url = self.discover(overview)
        documents = self._fetch(document_url, 'documents.html')
        notices = self._fetch(notice_url, 'notices.html')
        rows = self.parse_projects(overview, documents, notices)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': rows[0]['source_urls'],
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
