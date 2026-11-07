"""Offline parser and pagination regression tests; fixtures are synthetic."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from municipio.adapters.pizarra import (
    PizarraAyuntamientoAdapter, SOURCE, group_instruments, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(page=1, total=1, number=1, municipality='PIZARRA'):
    return f'''<table><thead><tr><th>Número de Expediente</th></tr></thead>
    <tr><td>Órgano</td><td>Modificación del PGOU de prueba</td><td>MÁLAGA</td>
    <td></td><td>{municipality}</td><td></td><td>Documento de Alcance</td>
    <td>17/04/2023</td><td>EA/MA/{number}/22</td><td>
    <a href="/medioambiente/daepu/resolucions/{number};jsessionid=TOKEN">Ver</a></td></tr>
    <tr class="footer"><td colspan="10">Página {page} de {total}</td></tr></table>'''


def detail(number=1):
    fields = {'Municipio': 'PIZARRA', 'Provincia': 'MÁLAGA',
              'Número de Expediente': f'EA/MA/{number}/22',
              'Actuación': 'Modificación del PGOU de prueba',
              'Órgano Tramitador': 'Junta de Andalucía', 'Fecha de Resolución': '17/04/2023'}
    return ''.join(f'<label>{k}:</label><div class="box">{v}</div>' for k, v in fields.items()) + '''
    <table><tr><th>Tipo</th></tr>
    <tr><td>Documento de Alcance del Estudio Ambiental Estratégico (DA)</td>
    <td>17/04/2023</td><td><a href="downloadFile/abc">Documento</a></td></tr>
    <tr><td>Publicación en BOJA (PB)</td><td>25/04/2023</td>
    <td><a href="downloadFile/def">Documento</a></td></tr></table>'''


class PizarraTests(unittest.TestCase):
    def entry(self):
        return parse_inventory(inventory())[0][0]

    def test_exact_identity_manifest(self):
        path = Path('data/municipios/pizarra/manifest.yaml')
        raw = load_yaml(path)
        self.assertEqual((raw['codigo_ine'], raw['nombre'], raw['provincia']), ('29080', 'Pizarra', 'Málaga'))
        for field in ('schedule', 'licencias'):
            self.assertIs(raw[field]['enabled'], False)
        self.assertIs(raw['geocode']['jitter_missing'], False)
        self.assertEqual(load_manifest(path).portal.adapter, 'municipio.adapters.pizarra:PizarraAyuntamientoAdapter')

    def test_inventory_session_free_and_filtered_pagination(self):
        rows, current, total, next_url = parse_inventory(inventory(total=2))
        self.assertNotIn('jsessionid', rows[0]['url'])
        self.assertEqual((current, total), (1, 2))
        query = parse_qs(urlsplit(next_url).query)
        self.assertEqual(query['page'], ['2'])
        self.assertEqual(query['filter5'], ['PIZARRA'])

    def test_bad_inventory_fails_closed(self):
        for html in ('<h1>Licencia de obra: solicitud</h1>', inventory().replace('Página 1 de 1', ''),
                     inventory(municipality='ÁLORA'), inventory().replace('resolucions/1;', 'resolucions/other;')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_grouped_documents_and_date_semantics(self):
        parsed = parse_detail(detail(), self.entry())
        row = group_instruments([parsed, parsed])[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['fichas_fuente']), 1)
        docs = row['documentos']
        self.assertEqual(docs[0]['fecha_resolucion'], '2023-04-17')
        self.assertEqual(docs[1]['fecha_publicacion'], '2023-04-25')
        self.assertEqual(docs[0]['url'], 'https://www.juntadeandalucia.es/medioambiente/daepu/resolucions/downloadFile/abc')
        for field in ('fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertNotIn('fase', row)
        self.assertIs(row['publication_ready'], False)

    def test_distinct_documents_same_instrument_are_retained(self):
        first = parse_detail(detail(), self.entry())
        second = parse_detail(detail().replace('downloadFile/abc', 'downloadFile/xyz'), self.entry())
        rows = group_instruments([first, second])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)

    def test_detail_rejects_wrong_identity_or_missing_documents(self):
        for html in (detail().replace('PIZARRA', 'ÁLORA'), detail().replace('EA/MA/1/22', 'EA/MA/2/22'),
                     detail().split('<table>')[0], detail().replace('17/04/2023', '31/02/2023')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_detail(html, self.entry())

    def test_full_two_page_snapshot(self):
        adapter = PizarraAyuntamientoAdapter()
        def fetch(session, url):
            if '/find?' in url:
                page = int(parse_qs(urlsplit(url).query).get('page', ['1'])[0])
                return inventory(page=page, total=2, number=page)
            return detail(int(url.rsplit('/', 1)[-1]))
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=fetch):
            out = Path(folder) / 'projects.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(result['count'], 2)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_repeated_page_aborts_without_overwriting_snapshot(self):
        adapter = PizarraAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'projects.jsonl'
            out.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[inventory(total=2), detail(), inventory(total=2)]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_disabled_licences(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'licencias.jsonl'
            self.assertTrue(PizarraAyuntamientoAdapter().backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
