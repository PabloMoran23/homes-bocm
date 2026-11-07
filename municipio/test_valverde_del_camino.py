import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.valverde_del_camino import (
    HOST, INVENTORY, SECTION, ValverdeDelCaminoAyuntamientoAdapter,
    build_record, parse_page,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml

TITLE = 'Proyecto Actuacion Suelo Rustico CAMPING POL. 16 - PARC. 15 COTO CARRASCO'
DOC = f'https://{HOST}/preview-document/07222d50-8607-4f57-9244-a02410cd7a08'
DETAIL = f'https://{HOST}/transparency/a32af2c8-45e9-4299-bc26-c207ebf8a810/'


def folder(title=TITLE, count=2):
    return f'''<a class="gIconLink exp" onclick="wicketAjaxGet('?x=live-token',null)">{title}<span class="linkExtraInfo"> ( {count} )</span></a>'''


def page(body):
    return f'<html><h1>{SECTION}</h1>{body}</html>'


class ParserTests(unittest.TestCase):
    def test_group_documents_and_no_invented_dates(self):
        _, docs = parse_page(page(f'<a href="{DOC}">1_Memoria PA Camping</a><a href="{DOC}-plan">2_Planimetría</a><a href="{DOC}">1_Memoria PA Camping</a>'))
        row = build_record(TITLE, DETAIL, docs)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '21072')
        self.assertEqual(row['titulo'], TITLE)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)
        self.assertFalse(row['publication_ready'])
        self.assertEqual(build_record('CA_Proyecto_Actuacion_acceso_PK2_235_HU-4100', DETAIL, docs)['titulo'],
                         'CA_Proyecto_Actuacion_acceso_PK2_235_HU-4100')

    def test_folder_title_and_count(self):
        folders, docs = parse_page(page(folder()))
        self.assertEqual(folders[0]['titulo'], TITLE)
        self.assertEqual(folders[0]['count'], 2)
        self.assertFalse(docs)

    def test_empty_folder_is_not_a_record(self):
        self.assertEqual(parse_page(page('No se han encontrado elementos')), ([], []))
        with self.assertRaises(ValueError):
            build_record(TITLE, DETAIL, [])

    def test_forms_and_announcements_are_not_projects(self):
        for title in ('Solicitud de licencia de obras', 'Obras y usos provisionales', 'Anuncio de contratación', 'Noticias'):
            with self.assertRaises(ValueError):
                build_record(title, DETAIL, [{'url': DOC}])

    def test_fail_on_changed_layout_pagination_and_offsite_docs(self):
        for html in ('<html>Error</html>', page('<p>Vacío inesperado</p>'),
                     page(folder() + '<a>Mostrar más</a>'),
                     page(folder() + '<a rel="next" href="?page=2">2</a>'),
                     page('<a href="https://other.example/preview-document/id">Memoria</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_page(html)

    def test_adapter_full_flow_and_count_guard(self):
        class Response:
            headers = {}
            def __init__(self, text='', url=INVENTORY, location=None):
                self.text, self.url = text, url
                self.headers = {'Ajax-Location': DETAIL} if location else {}
        for count in (2, 3):
            responses = [Response(page(folder(count=count))), Response(page(folder(count=count))),
                         Response(url=f'https://{HOST}/?x=live-token', location=True),
                         Response(page(f'<a href="{DOC}">Memoria</a><a href="{DOC}-plan">Planos</a>'), DETAIL)]
            adapter = ValverdeDelCaminoAyuntamientoAdapter('valverde-del-camino')
            with tempfile.TemporaryDirectory() as d, patch.object(adapter, '_fetch', side_effect=responses):
                output = Path(d) / 'records.jsonl'
                if count == 2:
                    report = adapter.backfill_proyectos(output)
                    self.assertEqual(report['count'], 1)
                    self.assertEqual(len(json.loads(output.read_text())['documentos']), 2)
                else:
                    output.write_text('previous snapshot')
                    with self.assertRaisesRegex(ValueError, 'count mismatch'):
                        adapter.backfill_proyectos(output)
                    self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('valverde-del-camino')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '21072')
        self.assertEqual(manifest.provincia, 'Huelva')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, ValverdeDelCaminoAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
