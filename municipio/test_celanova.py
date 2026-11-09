import copy
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.celanova import CelanovaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml


def fixture(identifier='1'):
    row = {'id': identifier, 'docnome': 'PARCELA SANITARIA', 'figura': 'Estudio de Detalle',
           'fechaaddef': '2008-07-21'}
    detail = {'datos_xerais': {'id': identifier, 'denominacion': row['docnome'],
                             'figura': row['figura'], 'fechaaddef': row['fechaaddef'],
                             'menutitle': 'Celanova', 'folder': 'CELANOVA',
                             'filesroot': 'documentos/urbanismo/',
                             'fechabop': '2008-08-01', 'fechadog': '2008-09-01'},
              'elementos': [{'description': 'NORMATIVA', 'componentes': [
                  {'pathesperado': 'normativa.pdf', 'descripcion': 'Normas'}]}]}
    return row, detail


class CelanovaTests(unittest.TestCase):
    def test_date_semantics_and_provenance(self):
        row, detail = fixture()
        record = Adapter.parse_detail(row, detail, 'desarrollo')
        self.assertEqual(record['fecha_aprob'], '2008-07-21')
        self.assertIsNone(record['fecha_acuerdo'])
        self.assertIsNone(record['fecha_publicacion'])
        self.assertEqual(record['publicaciones'][0]['fecha'], '2008-08-01')
        self.assertEqual(record['publicaciones'][1]['medio'], 'DOG')
        self.assertIn('/CELANOVA/documents/normativa.pdf', record['documentos'][0]['url'])
        self.assertIsNone(record['geometry'])
        self.assertFalse(record['publication_ready'])

    def test_duplicate_dossiers_grouped_with_all_links_and_dates(self):
        row, detail = fixture()
        first = Adapter.parse_detail(row, detail, 'desarrollo')
        row2, detail2 = fixture('2')
        detail2['datos_xerais']['fechadog'] = None
        detail2['elementos'][0]['componentes'][0]['pathesperado'] = 'plan.jpg'
        second = Adapter.parse_detail(row2, detail2, 'desarrollo')
        grouped = Adapter.group_records([first, second])
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]['source_ids'], ['1', '2'])
        self.assertEqual(len(grouped[0]['documentos']), 2)
        self.assertEqual(len(grouped[0]['procedencia']), 2)
        self.assertEqual(first['id'], second['id'])

    def test_different_approval_is_separate_instrument(self):
        row, detail = fixture()
        first = Adapter.parse_detail(row, detail, 'general')
        row['fechaaddef'] = detail['datos_xerais']['fechaaddef'] = '2009-07-21'
        second = Adapter.parse_detail(row, detail, 'general')
        self.assertEqual(len(Adapter.group_records([first, second])), 2)

    def test_metadata_without_digitised_files_is_retained(self):
        row, detail = fixture()
        detail['elementos'] = None
        detail['datos_xerais']['fechadog'] = None
        record = Adapter.parse_detail(row, detail, 'desarrollo')
        self.assertEqual(record['documentos'], [])
        self.assertIsNone(record['procedencia'][0]['fechas_fuente']['fechadog'])

    def test_fail_on_wrong_municipality_or_conflicting_detail(self):
        row, detail = fixture()
        for field, value in [('menutitle', 'Ourense'), ('id', '9'),
                             ('denominacion', 'Different'), ('fechaaddef', '2001-01-01')]:
            modified = copy.deepcopy(detail)
            modified['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                Adapter.parse_detail(row, modified, 'general')

    def test_no_silent_server_pagination_or_invalid_records(self):
        row, _ = fixture()
        for bad in [{'results': [row], 'next': '?page=2'}, '<html>Login</html>',
                    [dict(row, figura='Formulario de licencia')], [row, row],
                    [dict(row, fechaaddef='2008-02-31')]]:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(bad)
        self.assertEqual(Adapter.parse_inventory(None), [])
        self.assertEqual(len(Adapter.parse_inventory([dict(row, id=str(i)) for i in range(151)])), 151)

    def test_bad_document_origin_rejected(self):
        row, detail = fixture()
        detail['datos_xerais']['filesroot'] = 'https://example.com/'
        with self.assertRaises(ValueError):
            Adapter.parse_detail(row, detail, 'general')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('celanova')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('32024', 'Celanova', 'Ourense'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'licencias.jsonl'
            self.assertEqual(Adapter().backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
