"""Offline parser regression tests; no website or evidence directory required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.redovan import RedovanAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(body, heading='Plan Parcial de Ordenación del Polígono Industrial San Carlos'):
    return ('<div class="entry-content"><h1 class="page-title">Sector B-7</h1>'
            '<div class="et_pb_toggle"><h5 class="et_pb_toggle_title">' + heading + '</h5>'
            '<div class="et_pb_toggle_content">' + body + '</div></div></div>')


PLAN = ('<p>Aprobado por la Comisión Territorial de Urbanismo en fecha 08/10/1996 '
        'y publicado en el B.O.P. de fecha 09/03/1998.</p>'
        '<p><a href="/wp-content/uploads/plan.pdf">Ordenanzas</a></p>')
URBAN = ('<p><strong>2.-Proyecto de Urbanización</strong>. Aprobado en Junta de Gobierno '
         'Local de fecha 01/03/2004 y publicado en el B.O.P. de fecha 13/04/2004.</p>'
         '<p><a href="/wp-content/uploads/MEMORIA.pdf">Memoria</a></p>')


class RedovanTests(unittest.TestCase):
    def test_separate_instruments_and_date_semantics(self):
        rows = RedovanAyuntamientoAdapter.parse_projects(inventory(PLAN + URBAN))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['fecha_aprob'], '1996-10-08')
        self.assertEqual(rows[0]['fecha_publicacion'], '1998-03-09')
        self.assertEqual(rows[1]['fecha_acuerdo'], '2004-03-01')
        self.assertEqual(rows[1]['fecha_publicacion'], '2004-04-13')
        self.assertEqual(rows[1]['tipo'], 'proyecto_urbanizacion')
        self.assertEqual([len(r['documentos']) for r in rows], [1, 1])
        self.assertTrue(rows[1]['documentos'][0]['url'].endswith('/MEMORIA.pdf'))
        for row in rows:
            self.assertIsNone(row['fecha'])
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['geometry'])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '03111')

    def test_document_grouping_deduplication_and_case(self):
        html = inventory(PLAN + URBAN + '<p><a href="/wp-content/uploads/MEMORIA.pdf">Repeated</a>'
                         '<a href="/wp-content/uploads/Memoria.pdf">Different document</a></p>')
        rows = RedovanAyuntamientoAdapter.parse_projects(html)
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][0]['source_url'], SOURCE)
        edited = RedovanAyuntamientoAdapter.parse_projects(html.replace('Ordenanzas', 'Ordenanzas revisadas'))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in edited])

    def test_pgou_and_two_digit_approval_year(self):
        pgou = inventory(PLAN.replace('en fecha 08/10/1996', 'en fecha (C.T.U.) de fecha 11/05/2007'), 'PGOU')
        self.assertEqual(RedovanAyuntamientoAdapter.parse_projects(pgou)[0]['fecha_aprob'], '2007-05-11')
        modification = inventory(PLAN.replace('08/10/1996', '22/07/11'), 'Modificación Puntual Nº 1')
        self.assertEqual(RedovanAyuntamientoAdapter.parse_projects(modification)[0]['fecha_aprob'], '2011-07-22')

    def test_reparcelation_and_modified_urbanisation_boundaries(self):
        reparcelation = URBAN.replace('2.-Proyecto de Urbanización', '3.Proyecto de Reparcelación')
        modified = URBAN.replace('2.-Proyecto de Urbanización', '4.-Proyecto Modificado Nº1 de Urbanización')
        modified = modified.replace('01/03/2004', '28/01/2008').replace('13/04/2004', '28/05/2008')
        rows = RedovanAyuntamientoAdapter.parse_projects(inventory(PLAN + URBAN + reparcelation + modified))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[2]['tipo'], 'proyecto_reparcelacion')
        self.assertEqual(rows[3]['fecha_aprob'], '2008-01-28')
        self.assertEqual(rows[3]['fecha_publicacion'], '2008-05-28')
        self.assertEqual([len(row['documentos']) for row in rows], [1, 1, 1, 1])

    def test_missing_dates_documents_or_inventory_rejected(self):
        for html in ['<form>Login</form>', '<a href="plan.pdf">PGOU</a>',
                     inventory(PLAN.replace('Aprobado', 'Solicitado')),
                     inventory(PLAN.replace('publicado', 'pendiente')),
                     inventory('<p>Aprobado en fecha 01/01/2000 y publicado en fecha 02/01/2000</p>'),
                     inventory(PLAN, 'Solicitud de licencia'),
                     inventory(PLAN.replace('08/10/1996', '31/02/1996'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                RedovanAyuntamientoAdapter.parse_projects(html)

    def test_pagination_rejected(self):
        for link in ['<a rel="next" href="?paged=2">Más</a>',
                     '<a href="/page/2/">2</a>', '<a href="?page=2">Siguiente</a>',
                     '<a class="page-numbers" href="/2/">2</a>']:
            with self.subTest(link=link), self.assertRaises(ValueError):
                RedovanAyuntamientoAdapter.parse_projects(inventory(PLAN) + link)

    def test_unknown_approval_duplicate_or_external_document_rejected(self):
        for html in [inventory(PLAN + '<p>Otra actuación aprobada en fecha 01/01/2000</p>'),
                     inventory(PLAN) + inventory(PLAN),
                     inventory(PLAN.replace('/wp-content/uploads/plan.pdf', 'https://example.org/plan.pdf'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                RedovanAyuntamientoAdapter.parse_projects(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest(Path(__file__).resolve().parents[1] / 'data/municipios/redovan/manifest.yaml')
        self.assertEqual(manifest.nombre, 'Redován')
        self.assertEqual(manifest.provincia, 'Alicante')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')

    def test_update_refreshes_snapshot(self):
        adapter = RedovanAyuntamientoAdapter('redovan')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 9}) as backfill:
            path = Path('proyectos.jsonl')
            self.assertEqual(adapter.update_proyectos(path, Path('state.json')), {'rows': 9})
            backfill.assert_called_once_with(path)


if __name__ == '__main__':
    unittest.main()
