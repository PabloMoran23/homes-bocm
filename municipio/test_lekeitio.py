import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.lekeitio import API, SOURCE, LIBRARY, BASE, LekeitioAyuntamientoAdapter
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

DOC = BASE + LIBRARY + '/technical.pdf'


def section(title='Proyecto de reurbanización del entorno de Zumatzeta de Lekeitio', doc=DOC):
    return ('<div class="ms-WPHeader"><h3>' + title + '</h3></div>'
            '<div class="ms-WPBody"><a href="' + doc + '">Memoria y planos</a></div>')


def page(content=None):
    return '<div id="ProcedureZone">' + (section() if content is None else content) + '</div>'


class LekeitioTests(unittest.TestCase):
    def test_grouping_dates_and_no_coordinates(self):
        rows = LekeitioAyuntamientoAdapter.parse_projects(page(section() + section(doc=DOC.replace('technical', 'annex'))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
            self.assertIsNone(rows[0][key])
        self.assertNotIn('fase', rows[0])
        self.assertEqual(rows[0]['codigo_ine'], '48057')

    def test_reject_forms_empty_and_pagination(self):
        for html in [page(''), '<html>login</html>', page(section('Solicitud de licencia')),
                     page(section() + '<a href="?Paged=TRUE">2</a>'),
                     page(section() + '<a href="?page=2" rel="next">Next</a>'),
                     page(section(doc='https://example.org/technical.pdf'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                LekeitioAyuntamientoAdapter.parse_projects(html)

    def test_library_pagination_and_cycle(self):
        adapter = LekeitioAyuntamientoAdapter('lekeitio')
        def response(data):
            result = Mock()
            result.json.return_value = {'d': data}
            return result
        with patch.object(adapter, '_get', side_effect=[
            response({'results': [{'Name': 'first'}], '__next': API + '/Files?page=2'}),
            response({'results': [{'Name': 'second'}]})]):
            self.assertEqual(len(list(adapter._collection(API + '/Files'))), 2)
        with patch.object(adapter, '_get', return_value=response({'results': [], '__next': API + '/Files'})):
            with self.assertRaises(ValueError):
                list(adapter._collection(API + '/Files'))

    def test_mismatch_does_not_overwrite_output(self):
        adapter = LekeitioAyuntamientoAdapter('lekeitio')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'rows.jsonl'
            out.write_text('previous snapshot')
            response = Mock(text=page())
            with patch.object(adapter, '_get', return_value=response), patch.object(adapter, '_collection', return_value=iter([])):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('lekeitio')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('48057', 'Lekeitio', 'Bizkaia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
