"""Offline contract tests; synthetic fixtures reproduce the reviewed SIGIF tables."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.vilamarxant import (
    DETAIL, INVENTORY, VilamarxantAyuntamientoAdapter, parse_inventory,
)

PLAN = '/Documents/planes_PLPIF/46/PLPIF462567.zip'
RES = 'https://dogv.gva.es/datos/2020/12/09/pdf/2020_10407.pdf'
DETAIL_HTML = f'''
<table id="tablaMunicipio"><tbody><tr><td>Vilamarxant</td><td>46256</td><td>Valencia</td></tr></tbody></table>
<table id="tablaPLPIF"><thead><tr><th>PLPIF</th><th>Fecha Resolución</th><th>Resolución</th><th>Expediente</th><th>Informes Anuales</th></tr></thead>
<tbody><tr><td><a href="{PLAN}">Vilamarxant</a></td><td>24 noviembre 2020</td><td><a href="{RES}">2020/10407</a></td><td></td><td><a href="/Documents/planes_PLPIF/46/annual.zip">2023</a><a href="/Documents/planes_PLPIF/46/annual-2024.zip">2024</a></td></tr></tbody></table>
<table id="tablaDEM"><tbody><tr><td><a href="/Documents/regional.zip">Llíria</a></td></tr></tbody></table>
<a href="/licencia.pdf">Solicitud de licencia</a>'''
LIST_HTML = f'''
<table id="tablaValencia"><thead><tr><th>Municipio</th><th>Estado</th><th>Resolución</th><th>Fecha  Resolución</th><th>DOGV</th><th>Fecha DOGV</th><th>Vigencia</th></tr></thead><tbody>
<tr><td>Otro municipio</td><td>Aprobado</td></tr>
<tr><td><a href="{PLAN}">Vilamarxant</a></td><td>Aprobado</td><td><a href="{RES}">2020/10407</a></td><td>24/11/2020</td><td>8971</td><td>09/12/2020</td><td>15 años con revisión parcial cada 5 años</td></tr>
</tbody></table><script>$('#tablaValencia').DataTable({{pageLength: 5}});</script>'''


class VilamarxantTests(unittest.TestCase):
    def test_one_instrument_groups_all_documents_and_preserves_dates(self):
        rows = parse_inventory(DETAIL_HTML, LIST_HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '46256')
        self.assertEqual(row['fecha_aprob'], '2020-11-24')
        self.assertEqual(row['fecha_publicacion'], '2020-12-09')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(sum(d['rol'] == 'informe_anual' for d in row['documentos']), 2)
        self.assertFalse(any('regional' in d['url'] or 'licencia' in d['url'] for d in row['documentos']))
        self.assertEqual(row['id'], parse_inventory(DETAIL_HTML + '<p>Updated CMS</p>', LIST_HTML)[0]['id'])

    def test_fail_closed_on_missing_identity_documents_or_ambiguous_plan(self):
        for detail in [DETAIL_HTML.replace('46256</td>', '46255</td>'),
                       DETAIL_HTML.replace('Valencia</td>', 'Alicante</td>'),
                       DETAIL_HTML.replace('id="tablaPLPIF"', 'id="other"'),
                       DETAIL_HTML.replace(f'href="{PLAN}"', 'title="missing"'),
                       DETAIL_HTML.replace('2020/10407</a>', '2020/99999</a>'),
                       DETAIL_HTML.replace(RES, 'https://example.org/foreign.pdf')]:
            with self.subTest(detail=detail), self.assertRaises(ValueError):
                parse_inventory(detail, LIST_HTML)
        with self.assertRaises(ValueError):
            parse_inventory(DETAIL_HTML, LIST_HTML.replace('Aprobado', 'En Tramitación'))
        with self.assertRaises(ValueError):
            parse_inventory('<p>Solicitud de licencia</p>', '<p>Noticias</p>')

    def test_no_silent_server_pagination(self):
        for more in ['<a rel="next" href="?page=2">Next</a>',
                     '<script>var options={serverSide: true};</script>']:
            with self.subTest(more=more), self.assertRaises(ValueError):
                parse_inventory(DETAIL_HTML, LIST_HTML + more)

    def test_adapter_writes_snapshot_and_captures_and_disables_licences(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = VilamarxantAyuntamientoAdapter('vilamarxant', {'evidence_dir': tmp})
            def response(html, url):
                result = Mock(url=url, content=html.encode('utf-8'))
                return result
            with patch('municipio.adapters.vilamarxant.requests.Session') as session:
                session.return_value.__enter__.return_value.get.side_effect = [response(DETAIL_HTML, DETAIL), response(LIST_HTML, INVENTORY)]
                output = Path(tmp) / 'proyectos.jsonl'
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
                self.assertEqual(result['count'], 1)
                self.assertEqual(len(output.read_text().splitlines()), 1)
                self.assertEqual(json.loads(output.read_text())['codigo_ine'], '46256')
                self.assertTrue((Path(tmp) / 'sigif-detail.html').exists())
            lic = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(lic)['disabled'])
            self.assertEqual(lic.read_text(), '')


if __name__ == '__main__':
    unittest.main()
