import copy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.mondariz import MondarizAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml


def fixture():
    row = {'id': '22873', 'docnome': 'PROXECTO DE ORDENACIÓN DO MEDIO RURAL',
           'figura': 'Proxecto de Ordenación do Medio Rural', 'fechaaddef': '1999-02-26',
           'fechabop': '1999-06-01', 'fechadog': '1999-05-28', 'fechanormativabop': '1999-06-01'}
    info = dict(row, menutitle='Mondariz', folder='MONDARIZ', filesroot='documentos/urbanismo/')
    detail = {'datos_xerais': info, 'elementos': [
        {'description': 'NORMATIVA', 'componentes': [{'pathesperado': '0830no100.pdf', 'descripcion': 'Normas'}]},
        {'description': 'PLANOS', 'componentes': [{'pathesperado': '0830pl001.jpg', 'descripcion': 'Plano'}]}]}
    return row, detail


class MondarizTests(unittest.TestCase):
    def test_grouping_and_distinct_date_semantics(self):
        row, detail = fixture()
        result = Adapter.parse_project(row, detail, 14)
        self.assertEqual(len(result['documentos']), 2)
        self.assertEqual(result['fecha_aprob'], '1999-02-26')
        self.assertEqual(result['fecha_publicacion'], '1999-05-28')
        self.assertEqual(result['fecha_publicacion_bop'], '1999-06-01')
        self.assertIsNone(result['fecha_acuerdo'])
        self.assertIsNone(result['lat'])
        self.assertFalse(result['publication_ready'])
        self.assertTrue(all('/MONDARIZ/documents/' in doc['url'] for doc in result['documentos']))

    def test_missing_dates_and_documents_are_explicit(self):
        row, detail = fixture()
        for key in ('fechaaddef', 'fechadog', 'fechabop', 'fechanormativabop'):
            row[key] = detail['datos_xerais'][key] = None
        detail['elementos'] = None
        result = Adapter.parse_project(row, detail, 13)
        self.assertIsNone(result['fecha_aprob'])
        self.assertIsNone(result['fecha_publicacion'])
        self.assertIsNone(result['fase'])
        self.assertEqual(result['documentacion_status'], 'sin_documentos_en_ficha')

    def test_wrong_municipality_and_identity_rejected(self):
        row, detail = fixture()
        for field, value in [('menutitle', 'Mondariz-Balneario'), ('folder', 'MONDARIZ_BALNEARIO'), ('id', '99')]:
            changed = copy.deepcopy(detail)
            changed['datos_xerais'][field] = value
            with self.assertRaises(ValueError):
                Adapter.parse_project(row, changed, 14)

    def test_conflicting_dates_and_external_document_rejected(self):
        row, detail = fixture()
        changed = copy.deepcopy(detail)
        changed['datos_xerais']['fechadog'] = '2000-01-01'
        with self.assertRaises(ValueError):
            Adapter.parse_project(row, changed, 14)
        detail['datos_xerais']['filesroot'] = 'https://example.org/'
        with self.assertRaises(ValueError):
            Adapter.parse_project(row, detail, 14)

    def test_inventory_no_silent_truncation(self):
        row, _ = fixture()
        rows = [dict(row, id=str(i)) for i in range(125)]
        self.assertEqual(len(Adapter.parse_inventory(rows)), 125)
        self.assertEqual(Adapter.parse_inventory(None), [])
        for payload in ({'data': rows, 'recordsTotal': 300}, '<html>login</html>', [{}]):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(payload)
        changed = dict(row, docnome='Conflicting title')
        with self.assertRaises(ValueError):
            Adapter.parse_inventory([row, changed])
        with self.assertRaises(ValueError):
            Adapter.parse_inventory([dict(row, fechaaddef='1999-02-30')])

    def test_failed_extraction_does_not_replace_previous_snapshot(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            output.write_text('previous snapshot')
            with patch('municipio.adapters.mondariz.requests.Session.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    Adapter().backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('mondariz')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '36030')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = Adapter().backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
