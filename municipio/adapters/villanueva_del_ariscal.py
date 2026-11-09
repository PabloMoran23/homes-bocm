"""Current municipal works document inventory; no inferred execution status."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'https://transparencia.villanuevadelariscal.es'
SOURCE = HOST + '/es/transparencia/indicadores-de-transparencia/indicador/Obras-mas-importantes-de-infraestructura-que-estan-en-curso-00023/'
PAGE_KEY = 'pagegalleryfiles-1-1'

# Reviewed document identities, not preloaded records. Emit only links actually
# present in the live gallery. Unknown additions require review, never omission.
GROUPS = {
    'supera-v-parques': ('Reparación y conservación de parques y jardines (Plan Supera V)', [
        'PLAN-SUPERA-V-Proyecto-parques-y-jardines.pdf']),
    'supera-v-ascensor': ('Adecuación a normativa de edificios e instalaciones públicas: ascensor (Plan Supera V)', [
        'PLAN-SUPERA-V-Proyecto-ascensor.pdf']),
    'supera-v-viarios': ('Reparación y conservación de viales y espacios públicos (Plan Supera V)', [
        'PLAN-SUPERA-V-Proyecto-Mejora-de-Viarios.pdf']),
    'supera-v-colegio': ('Reparación y conservación del CEIP Manuel Castro Orellana (Plan Supera V)', [
        'PLAN-SUPERA-V-Proyecto-Colegio-Manuel-Castro-Orellana.pdf']),
    'supera-iii-viarios': ('Mejora de viarios públicos (Plan Supera III)', [
        'ProyectoCompletoViariosSubsanadoFirmado.pdf']),
    'supera-iv-piscina': ('Reparación y conservación de instalaciones deportivas municipales en avenida de los Niños (Plan Supera IV)', [
        'PROYECTO-PISCINA-COMPLETO-FIRMADO.pdf', 'PROYECTO_MODIFICADO_BajaPiscina-FIRMADO.pdf']),
    'supera-iv-viarios-baja': ('Mejora de viarios públicos: reinversión de baja (Plan Supera IV)', [
        'Proyecto-BajaMejoradeViarios-firmado.pdf']),
    'ludoteca': ('Rehabilitación de edificio anexo a recinto deportivo en avenida de los Niños para centro de ocio juvenil (Ludoteca)', [
        'PROYECTO-LUDOTECA_FIRMADO.pdf']),
    'supera-iv-accesos-ceip': ('Conservación y reparación de accesos del CEIP Manuel Castro Orellana (Plan Supera IV)', [
        'PROYECTO-Baja_Accesos-CEIPMCastro-OrellanaFIRMADO.pdf',
        '01_Proyecto-Conservacion-y-Reparacion-Accesos-CEIP_FIRMADO-DEFINITIVO.pdf']),
    'supera-iv-alumbrado': ('Mejora de alumbrado público (Plan Supera IV)', [
        'PROYECTO-BAJA_ALUMBRADO_FIRMADO.pdf', '03_ALUMBRADO-LED-REFORMULADO_FIRMADO.pdf']),
    'pfoea-2015-rafael-alberti': ('Reforma de viarios en plaza Rafael Alberti (PFOEA 2015)', [
        'E.4.61-PFOEA-15-Proyecto-de-Reforma-de-viario-en-Plaza-Rafael-Alberti.pdf']),
}
DOCUMENTS = {filename: (key, title) for key, (title, files) in GROUPS.items() for filename in files}
ARCHIVE = 'E.4.61-Plan-Supera-III.rar'
LIMITATIONS = [
    'Cobertura parcial: solo proyectos PDF del indicador municipal 61; no es un registro completo de obras ni de licencias.',
    'El archivo colectivo Plan Supera III se conserva como enlace excluido: no se descompone en proyectos sin identificar su contenido.',
    'Agrupación por intervención y programa; incluye reinversiones de bajas con sus títulos originales, sin afirmar un único expediente administrativo.',
    'La etiqueta del portal obras en curso no acredita ejecución actual; documentos históricos revisados de 2015-2017.',
    'Sin fechas de acuerdo, aprobación o publicación verificadas, ni geometría; las firmas técnicas no son aprobaciones.',
]


def canonical_page(url: str) -> str:
    parsed = urlparse(urldefrag(url)[0])
    if (parsed.scheme != 'https' or parsed.netloc != urlparse(HOST).netloc
            or parsed.path.rstrip('/') != urlparse(SOURCE).path.rstrip('/')):
        raise ValueError('Unexpected gallery pagination URL: ' + url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if query and (set(query) != {PAGE_KEY} or len(query[PAGE_KEY]) != 1
                  or not query[PAGE_KEY][0].isdigit() or int(query[PAGE_KEY][0]) < 1):
        raise ValueError('Unexpected gallery pagination query')
    page = int(query.get(PAGE_KEY, ['1'])[0])
    return SOURCE if page == 1 else SOURCE + '?' + PAGE_KEY + '=' + str(page)


def parse_inventory_page(html: str, url: str):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find(['h1', 'h2'], string=lambda s: s and 'Obras más importantes de infraestructura' in s)
    if not heading:
        raise ValueError('Municipal works inventory heading missing')
    docs, excluded = [], []
    for anchor in soup.select('table.table tbody a[href]'):
        target = urljoin(url, anchor['href'])
        parsed = urlparse(target)
        if parsed.netloc != urlparse(HOST).netloc or '/.galleries/IND-61-/' not in parsed.path:
            raise ValueError('Unexpected document provenance')
        title = anchor.get_text(' ', strip=True)
        filename = parsed.path.rsplit('/', 1)[-1]
        if not title:
            raise ValueError('Document without title')
        doc = {'titulo': title, 'url': target, 'inventory_url': url}
        if filename == ARCHIVE:
            excluded.append({**doc, 'reason': 'Collective archive; individual projects not identified'})
        elif filename in DOCUMENTS:
            key, _ = DOCUMENTS[filename]
            docs.append((key, doc))
        else:
            raise ValueError('Unreviewed inventory document: ' + filename)
    if not docs:
        raise ValueError('No reviewed physical works projects in gallery')
    pages = {canonical_page(urljoin(url, a['href'])) for a in soup.select('a[numpag][href], a[rel="next"][href]')}
    expected = int(parse_qs(urlparse(url).query).get(PAGE_KEY, ['1'])[0])
    current = soup.select_one('a.currentpagelink[numpag]')
    if (current and int(current['numpag']) != expected) or (expected > 1 and not current):
        raise ValueError('Server did not return requested gallery page')
    return docs, excluded, pages


def group_projects(documents):
    grouped = {}
    for key, doc in documents:
        if key not in grouped:
            grouped[key] = {
                'id': 'villanueva-del-ariscal-proy-' + key,
                'municipio': 'Villanueva del Ariscal', 'codigo_ine': '41098', 'provincia': 'Sevilla',
                'titulo': GROUPS[key][0], 'tipo': 'proyecto de obra pública',
                'source': 'ayuntamiento', 'origen': 'inventario_documental_obras',
                'url': doc['url'], 'inventory_url': SOURCE, 'documentos': [],
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'coverage': 'partial_current_document_inventory', 'limitations': LIMITATIONS,
            }
        if doc['url'] not in {d['url'] for d in grouped[key]['documentos']}:
            grouped[key]['documentos'].append(doc)
    if not grouped:
        raise ValueError('No public works projects extracted')
    for record in grouped.values():
        record['documentos'].sort(key=lambda d: d['url'])
        record['url'] = record['documentos'][0]['url']
    return [grouped[key] for key in sorted(grouped)]


class VillanuevaDelAriscalAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        pending, visited, signatures = {SOURCE}, set(), set()
        documents, excluded, captures = [], [], []
        session = requests.Session()
        session.headers['User-Agent'] = 'municipio-villanueva-del-ariscal/1.0'
        try:
            while pending:
                url = sorted(pending)[0]
                pending.remove(url)
                if url in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('Unexpected gallery size; extraction aborted without truncation')
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if canonical_page(response.url) != url:
                    raise ValueError('Unexpected gallery redirect')
                docs, omissions, pages = parse_inventory_page(response.text, url)
                signature = tuple(sorted(doc['url'] for _, doc in docs))
                if signature in signatures:
                    raise ValueError('Repeated gallery page; pagination may be ignored')
                signatures.add(signature)
                documents.extend(docs)
                excluded.extend(omissions)
                visited.add(url)
                pending.update(pages - visited)
                if self.config.get('capture_dir'):
                    directory = Path(self.config['capture_dir'])
                    directory.mkdir(parents=True, exist_ok=True)
                    name = 'inventory-' + hashlib.sha256(url.encode()).hexdigest()[:12] + '.html'
                    (directory / name).write_text(response.text, encoding='utf-8')
                    captures.append({'url': url, 'status': response.status_code, 'file': name})
        finally:
            session.close()
        records = group_projects(documents)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        return {'count': len(records), 'written': len(records), 'document_count': sum(len(r['documentos']) for r in records),
                'pages': sorted(visited), 'excluded_documents': excluded, 'captures': captures,
                'source_urls': sorted(visited | {d['url'] for _, d in documents} | {d['url'] for d in excluded}),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
