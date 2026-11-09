import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from municipio.adapters.cadrete import (
    BASE, CadreteAyuntamientoAdapter, action_url, entries, fragment,
)
from municipio.manifest import load_manifest, load_yaml

DOC = BASE + '/preview-document/67153940-4422-4b8f-8fef-d8565b48629f'
FOLDER = BASE + '/transparency/79563926-62f4-45aa-a6de-76ba50373a99/'
HTML = f'<table><tr><td class="class_name"><a class="gIconLink" href="{DOC}">Memoria</a></td></tr></table>'


class CadreteTests(unittest.TestCase):
    def test_document_provenance_and_date_semantics(self):
        docs = entries(fragment(HTML), FOLDER)
        row = CadreteAyuntamientoAdapter.record('Plan General de Ordenación Urbana de Cadrete', FOLDER, docs)
        self.assertEqual(row['documentos'], [{'titulo': 'Memoria', 'url': DOC}])
        for key in ['fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase']:
            self.assertIsNone(row[key])
        self.assertEqual(row['codigo_ine'], '50066')
        for title in ['Licencia de obras mayores', 'Anuncio licitación', 'Curso de robótica']:
            with self.assertRaises(ValueError):
                CadreteAyuntamientoAdapter.record(title, FOLDER, docs)

    def test_fragment_and_navigation_guards(self):
        xml = f'<?xml version="1.0"?><ajax-response><component><![CDATA[{HTML}]]></component></ajax-response>'
        self.assertEqual(entries(fragment(xml), FOLDER)[0]['url'], DOC)
        for value in [' ', '<?xml version="1.0"?><ajax-response><redirect>/login</redirect></ajax-response>']:
            with self.assertRaises(ValueError):
                fragment(value)
        a = fragment('<a onclick="wicketAjaxGet(\'https://example.org/\')"></a>').a
        with self.assertRaises(ValueError):
            action_url(a, FOLDER)

    def test_pagination_including_explicit_empty_end(self):
        adapter = CadreteAyuntamientoAdapter('cadrete')
        first = HTML + '<button onclick="wicketAjaxGet(\'?more\')">Mostrar más</button>'
        end = '<?xml version="1.0"?><ajax-response><component><![CDATA[<div style="display:none"></div>]]></component></ajax-response>'
        adapter._fetch = Mock(side_effect=[Mock(url=FOLDER, text=first), Mock(url=BASE + '/?more', text=end)])
        self.assertEqual(len(adapter._inventory(None, FOLDER)[1]), 1)
        self.assertEqual(adapter._fetch.call_count, 2)
        adapter._fetch = Mock(side_effect=[Mock(url=FOLDER, text=first), Mock(url=BASE + '/?more', text=HTML)])
        with self.assertRaisesRegex(ValueError, 'repeated'):
            adapter._inventory(None, FOLDER)

    def test_recursive_count_and_grouping(self):
        adapter = CadreteAyuntamientoAdapter('cadrete')
        adapter._inventory = Mock(return_value=(FOLDER, [{'titulo': 'Memoria', 'url': DOC}]))
        url, docs = adapter._documents(None, {'action': FOLDER, 'count': 1})
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['source_url'], url)
        with self.assertRaisesRegex(ValueError, 'count'):
            adapter._documents(None, {'action': FOLDER, 'count': 2})

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('cadrete')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('50066', 'Zaragoza'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = CadreteAyuntamientoAdapter('cadrete').backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
