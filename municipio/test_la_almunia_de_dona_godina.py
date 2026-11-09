"""Offline parser and traversal checks; no live network needed for unit tests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.la_almunia_de_dona_godina import (
    SOURCE, HOST, LaAlmuniaDeDonaGodinaAyuntamientoAdapter,
    build_record, parse_inventory,
)
from municipio.manifest import load_manifest

CHILD = f'https://{HOST}/transparency/ee98d956-7b2b-4982-a9c0-40422c61d008/'


def table(*cells):
    return '<table class="TransparencyListPanel"><tbody>' + ''.join(
        '<tr><td class="class_name">' + cell + '</td></tr>' for cell in cells
    ) + '</tbody></table>'


def folder(count=2):
    return ('<a class="exp" href="#" '
            'onclick="var wcall=wicketAjaxGet(\'../../?x=public-action\',null);">'
            f'1.- Modificación Número 1 - El Colmenar<span> ( {count} )</span></a>')


def doc(key, title):
    return f'<a class="gIconLink" href="/preview-document/{key}">{title}</a>'


class Response:
    def __init__(self, url, html):
        self.url, self.text = url, html

    def raise_for_status(self):
        pass


class PlanningTests(unittest.TestCase):
    def test_nested_document_wrappers_and_external_provenance(self):
        html = table('<span><a class="doc2">' + doc('a', 'BOPZ 13-05-2024 Aprobacion Definitiva') + '</a></span>',
                     '<a class="extUrl" href="https://drive.google.com/drive/folders/public">PLANOS</a>')
        page = parse_inventory(html, CHILD)
        self.assertEqual(len(page['documents']), 2)
        self.assertEqual(page['documents'][1]['hosting'], 'external_link_published_by_municipality')
        record = build_record('Modificación Número 1', CHILD, page['documents'], ['PGOU'])
        self.assertIsNone(record['fecha_aprob'])
        self.assertIsNone(record['fecha_publicacion'])
        self.assertIsNone(record['fecha_acuerdo'])
        self.assertIsNone(record['fase'])
        self.assertIsNone(record['geometry'])
        self.assertEqual(record['documentos'][0]['titulo'], 'BOPZ 13-05-2024 Aprobacion Definitiva')

    def test_folder_counts_and_session_action(self):
        parsed = parse_inventory(table(folder()), SOURCE)
        self.assertEqual(parsed['folders'][0]['count'], 2)
        self.assertEqual(parsed['folders'][0]['action_url'], f'https://{HOST}/?x=public-action')
        self.assertEqual(parsed['documents'], [])

    def test_reject_login_navigation_and_unrelated_rows(self):
        for html in ('<h1>Identifícate</h1>', '<a href="/urbanismo">Urbanismo</a>',
                     table('<a href="https://example.org/licitacion">Licitación</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)
        with self.assertRaises(ValueError):
            build_record('Solicitud de licencia', CHILD, [{'url': 'x'}], [])

    def test_fail_on_new_pagination(self):
        with self.assertRaisesRegex(ValueError, 'Pagination'):
            parse_inventory(table(doc('a', 'Plan')) + '<a rel="next" href="?page=2">Siguiente</a>', SOURCE)

    def test_missing_folder_count_is_error(self):
        with self.assertRaises(ValueError):
            parse_inventory(table(folder().replace('( 2 )', '')), SOURCE)

    def extract_fake(self, expected):
        adapter = LaAlmuniaDeDonaGodinaAyuntamientoAdapter('la-almunia-de-dona-godina')
        responses = [Response(SOURCE, table(folder(expected))),
                     Response(CHILD, table(doc('a', 'Memoria'), doc('b', 'Acuerdo')))]
        with TemporaryDirectory() as tmp, patch('requests.Session.get', side_effect=responses):
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            return result, rows

    def test_full_traversal_groups_documents_as_one_instrument(self):
        result, rows = self.extract_fake(2)
        self.assertEqual(result['document_links'], 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['codigo_ine'], '50025')
        self.assertEqual(rows[0]['url'], CHILD)

    def test_count_mismatch_fails_instead_of_silent_truncation(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete inventory'):
            self.extract_fake(3)

    def test_empty_source_fails(self):
        adapter = LaAlmuniaDeDonaGodinaAyuntamientoAdapter('la-almunia-de-dona-godina')
        with TemporaryDirectory() as tmp, patch('requests.Session.get', return_value=Response(SOURCE, table())):
            with self.assertRaisesRegex(ValueError, 'No usable'):
                adapter.backfill_proyectos(Path(tmp) / 'out.jsonl')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('la-almunia-de-dona-godina')
        self.assertEqual(manifest.provincia, 'Zaragoza')
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = LaAlmuniaDeDonaGodinaAyuntamientoAdapter(manifest.slug).backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
