import unittest
from unittest.mock import Mock

from municipio.adapters.albatera import AlbateraAyuntamientoAdapter, SOURCE, build_records, parse_page
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


DOC = '<a class="gIconLink" href="https://albatera.sedelectronica.es/preview-document/a">Plano</a>'
MORE = '''<button onclick="wicketAjaxGet('?x=next',null)">Mostrar más</button>'''


class AlbateraTests(unittest.TestCase):
    def test_wicket_append_and_pagination(self):
        adapter = AlbateraAyuntamientoAdapter('albatera')
        adapter._get = Mock(return_value=Mock(text=DOC + MORE))
        second = DOC.replace('/a"', '/b"')
        adapter._action = Mock(return_value=Mock(text='<?xml version="1.0"?><ajax-response><component><![CDATA[' + second + ']]></component></ajax-response>'))
        docs = adapter._inventory(None, SOURCE)
        self.assertEqual([d['url'].rsplit('/', 1)[-1] for d in docs], ['a', 'b'])
        adapter._action.assert_called_once()

    def test_stuck_pagination_fails(self):
        adapter = AlbateraAyuntamientoAdapter('albatera')
        adapter._get = Mock(return_value=Mock(text=DOC + MORE))
        adapter._action = Mock(return_value=Mock(text=DOC + MORE))
        with self.assertRaisesRegex(ValueError, 'no progress'):
            adapter._inventory(None, SOURCE)

    def test_grouping_shared_document_and_empty_folder(self):
        doc = parse_page(DOC)[0][0]
        shared = dict(doc, titulo='Doc Refundido de Modif 1 y 2 para NNSS', url=doc['url'] + 'shared')
        folders = [{'title': f'7.1.{i+1} MODIFICACION Nº {i} DE NNSS', 'count': 1} for i in (1, 2)]
        empty = {'title': '7.1.4 MODIFICACION Nº 3 DE NNSS', 'count': 0}
        rows = build_records([shared], [(f, SOURCE + str(i), [dict(doc, url=doc['url'] + str(i))]) for i, f in enumerate(folders)] + [(empty, SOURCE + 'empty', [])])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertNotEqual(rows[0]['documentos'][0]['url'], rows[1]['documentos'][0]['url'])
        self.assertEqual(rows[0]['documentos'][1]['url'], rows[1]['documentos'][1]['url'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['lat'])

    def test_missing_documents_and_unknown_standalone_fail(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            build_records([], [({'title': '7.1.1 NORMAS SUBSIDIARIAS', 'count': 22}, SOURCE, [])])
        with self.assertRaisesRegex(ValueError, 'standalone'):
            build_records(parse_page(DOC)[0], [])
        with self.assertRaises(ValueError):
            build_records([], [])

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('albatera')
        self.assertEqual(manifest.provincia, 'Alicante')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), AlbateraAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
