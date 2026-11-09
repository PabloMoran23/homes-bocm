"""Offline semantic and service-shape regression tests for Moraña."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.morana import MoranaAyuntamientoAdapter, parse_inventory, parse_project
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture():
    entry = {'id': '22878', 'figura': 'Modificación Puntual',
             'fechaaddef': '2002-06-07', 'fechadog': '2002-07-16',
             'fechabop': '2002-06-28', 'fechanormativabop': '2002-06-28'}
    info = {**entry, 'denominacion': 'PXOM ', 'menutitle': 'Moraña',
            'folder': 'MORANA', 'filesroot': 'documentos/urbanismo/'}
    detail = {'datos_xerais': info, 'incidencias_iuris': None, 'elementos': [
        {'description': 'NORMATIVA', 'componentes': [
            {'id': '15383', 'pathesperado': '0835no001.pdf', 'descripcion': 'NORMATIVA BOP'},
            {'id': '15384', 'pathesperado': '0835no002.pdf', 'descripcion': 'ANTECEDENTES'}]}]}
    return entry, detail


class MoranaTests(unittest.TestCase):
    def test_grouping_dates_and_no_invented_geometry(self):
        row = parse_project(*fixture(), 'planeamiento_general')
        self.assertEqual(row['fecha_aprob'], '2002-06-07')
        self.assertEqual(row['fecha_publicacion'], '2002-07-16')
        self.assertEqual(row['fecha_publicacion_bop'], '2002-06-28')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(row['documentos'][0]['url'].endswith('/MORANA/documents/0835no001.pdf'))
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])

    def test_missing_dates_stay_missing(self):
        entry, detail = fixture()
        for key in ('fechaaddef', 'fechadog', 'fechabop', 'fechanormativabop'):
            entry[key] = detail['datos_xerais'][key] = None
        row = parse_project(entry, detail, 'planeamiento_general')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_reject_foreign_municipality_or_conflicting_dates(self):
        for key, value in [('menutitle', 'Moaña'), ('id', '999'), ('fechaaddef', '2020-01-01')]:
            entry, detail = fixture()
            detail['datos_xerais'][key] = value
            with self.assertRaises(ValueError):
                parse_project(entry, detail, 'planeamiento_general')

    def test_reject_unusable_documents(self):
        entry, detail = fixture()
        detail['elementos'] = []
        with self.assertRaises(ValueError):
            parse_project(entry, detail, 'planeamiento_general')
        entry, detail = fixture()
        detail['elementos'][0]['componentes'][0]['pathesperado'] = '../wrong.pdf'
        with self.assertRaises(ValueError):
            parse_project(entry, detail, 'planeamiento_general')

    def test_inventory_requires_complete_array(self):
        self.assertEqual(parse_inventory(None), [])
        entry, _ = fixture()
        self.assertEqual(len(parse_inventory([entry])), 1)
        for bad in ({'rows': [entry], 'next': 2}, '<form>Licence application</form>', [entry, entry], [{'id': '1'}]):
            with self.assertRaises(ValueError):
                parse_inventory(bad)

    def test_failure_preserves_existing_snapshot(self):
        adapter = MoranaAyuntamientoAdapter('morana')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with patch('municipio.adapters.morana.requests.Session.request', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_load_and_disabled_licences(self):
        manifest = load_manifest('morana')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, MoranaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
