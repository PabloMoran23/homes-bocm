"""Complete snapshot of the municipal POUM page, not all municipal dossiers."""
from __future__ import annotations

import hashlib
import json
import re
import ssl
from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.palauplegamans.cat/ca/poum'
DERIVED_SOURCE = 'https://www.palauplegamans.cat/ca/planejament-derivat-gestio-urbanistica-i-projectes-d-urbanitzacio'
INTERMEDIATE = 'http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt'
INTERMEDIATE_SHA256 = '6542d176bed50f193c0ce297ae44ecd8a0a86bec2ede682769344059b4e78530'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def catalan_date(value):
    m = re.search(r"(\d{1,2}) d[e']\s*(\w+) del (\d{4})", value)
    return date(int(m[3]), MONTHS[m[2]], int(m[1])).isoformat() if m else None


def documents(node, source_url=SOURCE):
    """Deduplicate URL, retaining every label (including municipal mislabelling)."""
    found = {}
    for a in node.select('a[href]'):
        url = urljoin(source_url, a['href'])
        if urlsplit(url).scheme not in ('http', 'https'):
            continue
        label = text(a)
        entry = found.setdefault(url, {'url': url, 'titulos': [], 'source_url': source_url})
        if label and label not in entry['titulos']:
            entry['titulos'].append(label)
    return list(found.values())


def record(title, docs, kind, description, identity=None, source_url=SOURCE):
    if not docs:
        raise ValueError('Instrument without source documents: ' + title)
    return {
        'id': 'palau-solita-i-plegamans-proy-' + hashlib.sha256((identity or title.casefold()).encode()).hexdigest()[:16],
        'municipio': 'Palau-solità i Plegamans', 'provincia': 'Barcelona', 'codigo_ine': '08156',
        'titulo': title, 'tipo': kind, 'descripcion': description,
        'fase': None, 'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'url': source_url, 'url_documento': docs[0]['url'],
        'documentos': docs, 'source': 'ayuntamiento', 'origen': 'planejament_municipal',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified instrument geometry extracted',
    }


class PalauSolitaIPlegamansAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.palauplegamans.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        h1 = soup.find('h1')
        if not h1 or text(h1) != 'POUM, aprovat de forma definitiva':
            raise ValueError('Missing municipal POUM heading')
        # This inventory is unpaginated. Fail if the site introduces pagination.
        if soup.select('[rel="next"], .pagination, .paginacio, .paginador'):
            raise ValueError('Pagination introduced; full inventory must be reviewed')
        narrative = next((e for e in soup.select('div.element') if 'ha entrat en vigor' in text(e)), None)
        heading = next((h for h in soup.find_all('h2') if text(h) == 'Modificacions del POUM'), None)
        if narrative is None or heading is None:
            raise ValueError('Missing plan narrative or modifications inventory')
        rpuc = narrative.select('a[href*="/consulta/detallExpedient/"]')
        if len(rpuc) != 1:
            raise ValueError('Missing or ambiguous RPUC plan identity')
        plan_url = rpuc[0]['href']
        docs = documents(narrative)
        # Retain the other base-plan collections and attached documents as links,
        # without turning individual plans or chapters into separate instruments.
        for e in soup.select('div.element'):
            h = e.find('h2')
            if h and text(h).startswith("POUM, versió d'abril del 2015"):
                docs.extend(documents(e))
        unique = {d['url']: d for d in docs}
        base = record("Pla d'Ordenació Urbanística Municipal de Palau-solità i Plegamans (POUM)", list(unique.values()), 'POUM', text(narrative), plan_url)
        base['url_documento'] = plan_url
        base['rpuc_id'] = plan_url.rsplit('/', 1)[-1]
        for p in narrative.find_all('p'):
            value = text(p)
            if 'ha entrat en vigor' in value:
                base['fecha_publicacion'] = catalan_date(value)
            if "aprovat de forma definitiva el" in value:
                match = re.search(r"aprovat de forma definitiva el (\d{1,2} d[e']\s*\w+ del \d{4})", value)
                base['fecha_aprob'] = catalan_date(match[1]) if match else None
        base['fase'] = 'aprobación definitiva'
        rows = [base]
        inventory = heading.parent.find('ul', recursive=False)
        if inventory is None:
            raise ValueError('Missing modifications list')
        for li in inventory.find_all('li', recursive=False):
            span = li.find('span', recursive=False)
            nested = li.find('ul', recursive=False)
            if span is not None and nested is not None:
                title = text(span)
                docs = documents(nested)
                # A licence suspension alone is not a project. This group also
                # contains the technical modification and its supporting annex.
                if title.startswith('SUSPENSIÓ'):
                    technical = [d for d in docs if any('Modificació puntual' in t for t in d['titulos'])]
                    if not technical:
                        raise ValueError('Suspension group no longer contains a planning instrument')
                    title = technical[0]['titulos'][0].removesuffix(' (PDF)')
            else:
                a = li.find('a', recursive=False)
                if a is None or not re.search(r'/consulta/fitxaExpedient/\d+$', a.get('href', '')):
                    raise ValueError('Unknown inventory group; refusing to skip it')
                title, docs = text(a), documents(li)
            row = record(title, docs, 'Modificación del POUM', text(li))
            # Only explicit document labels supply modification dates; filenames
            # and the page update date are never treated as agreement dates.
            for d in docs:
                for label in d['titulos']:
                    m = re.search(r'Anunci.*?DOGC\s+(\d{2})\.(\d{2})\.(\d{4})', label)
                    compact = re.search(r'Anunci AD DOGC (\d{2})(\d{2})(\d{4})', label)
                    if m or compact:
                        m = m or compact
                        row['fecha_publicacion'] = date(int(m[3]), int(m[2]), int(m[1])).isoformat()
                    m = re.search(r'Acord CTUARC (\d{4}-\d{2}-\d{2}) Aprov\.def', label)
                    if m:
                        row['fecha_acuerdo'] = row['fecha_aprob'] = date.fromisoformat(m[1]).isoformat()
                        row['fase'] = 'aprobación definitiva'
            rows.append(row)
        if len(rows) == 1 or len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Empty or duplicate modifications inventory')
        return rows

    @staticmethod
    def parse_derived(html):
        soup = BeautifulSoup(html, 'html.parser')
        if soup.select('[rel="next"], .pagination, .paginacio, .paginador'):
            raise ValueError('Pagination introduced in derived inventory')
        elements = soup.select('div.element')
        expected = ['PLANS DERIVATS', "PROJECTES D'URBANITZACIÓ", 'PROJECTES DE REPARCEL·LACIÓ']
        if len(elements) != 3 or any(not text(e).startswith(prefix) for e, prefix in zip(elements, expected)):
            raise ValueError('Missing derived inventory sections')
        rows = []
        for element, kind in zip(elements, ['Planeamiento derivado', 'Proyecto de urbanización', 'Proyecto de reparcelación']):
            current = None
            for p in element.find_all('p', recursive=False):
                value = text(p)
                if not value:
                    continue
                links = documents(p, DERIVED_SOURCE)
                if not links and re.match(r"^(Pla especial |SUD \d|PMU |PU |PR |PBàsic )", value) and not re.search(r" - (MEM|PLÀ|PLAN)", value):
                    if current is not None:
                        rows.append(current)
                    current = {'title': value, 'docs': [], 'parts': [value], 'approval': None, 'kind': kind}
                elif links:
                    if current is None:
                        raise ValueError('Orphan documents in derived inventory')
                    current['docs'].extend(links)
                    current['parts'].append(value)
                elif value.startswith('Aprov.def'):
                    if current is None:
                        raise ValueError('Orphan approval date')
                    match = re.search(r'Aprov\.def Plè Municipal (\d{2})/(\d{2})/(\d{4})', value)
                    if not match:
                        raise ValueError('Unknown approval date format')
                    current['approval'] = date(int(match[3]), int(match[2]), int(match[1])).isoformat()
                    current['parts'].append(value)
                elif current is not None:
                    current['parts'].append(value)
            if current is not None:
                rows.append(current)
        result = []
        for group in rows:
            # Public consultation notice alone is not a technical plan/project.
            if group['docs'] and all('Consulta prèvia' in ' '.join(d['titulos']) for d in group['docs']):
                continue
            unique = {}
            for d in group['docs']:
                entry = unique.setdefault(d['url'], {**d, 'titulos': []})
                entry['titulos'].extend(t for t in d['titulos'] if t not in entry['titulos'])
            row = record(group['title'], list(unique.values()), group['kind'], '\n'.join(group['parts']), source_url=DERIVED_SOURCE)
            if group['approval']:
                row['fecha_aprob'] = row['fecha_acuerdo'] = group['approval']
                row['fase'] = 'aprobación definitiva'
            result.append(row)
        if not result or len({r['id'] for r in result}) != len(result):
            raise ValueError('Empty or duplicate derived inventory')
        return result

    def _fetch(self, source_url):
        request = Request(source_url, headers={'User-Agent': self.config.get('user_agent', 'municipio-palau-solita-i-plegamans/1.0')})
        context = ssl.create_default_context()
        try:
            response = urlopen(request, timeout=40, context=context)
        except URLError as exc:
            if not isinstance(exc.reason, ssl.SSLCertVerificationError):
                raise
            # Server omits its intermediate. Pin the public intermediate bytes;
            # retain hostname verification and validation to system trust roots.
            with urlopen(INTERMEDIATE, timeout=30) as cert_response:
                der = cert_response.read(65537)
            if hashlib.sha256(der).hexdigest() != INTERMEDIATE_SHA256:
                raise ValueError('Unexpected public TLS intermediate certificate') from exc
            context.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(der))
            response = urlopen(request, timeout=40, context=context)
        with response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('POUM response exceeds 2 MB')
            if urlsplit(response.url).hostname != 'www.palauplegamans.cat':
                raise ValueError('Unexpected source redirect')
            return raw.decode(response.headers.get_content_charset() or 'utf-8')

    def backfill_proyectos(self, out_jsonl: Path):
        html = self._fetch(SOURCE)
        derived_html = self._fetch(DERIVED_SOURCE)
        rows = self.parse_projects(html) + self.parse_derived(derived_html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'poum-live.html').write_text(html, encoding='utf-8')
            (capture / 'derivats-live.html').write_text(derived_html, encoding='utf-8')
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, DERIVED_SOURCE], 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
