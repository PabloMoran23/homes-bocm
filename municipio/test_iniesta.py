import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.iniesta import (
    HOST, INVENTORY, IniestaAyuntamientoAdapter, instrument_record, parse_listing,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def listing(items):
    return '<table class="TransparencyListPanel">' + ''.join(
        '<tr><td class="class_name">' + item + '</td></tr>' for item in items
    ) + '</table>'


def folder(title, count, token):
    return f'''<a class="gIconLink exp" href="#" onclick="wicketAjaxGet('../../?x={token}',null)">{title}<span> ( {count} )</span></a>'''


def document(title, key):
    return f'<a class="gIconLink" href="https://{HOST}/preview-document/{key}">{title}</a>'


class IniestaTests(unittest.TestCase):
    def test_group_documents_without_fabricated_metadata(self):
        docs = parse_listing(listing([document('POM INIESTA-NORMAS URBANÍSTICAS', 'normas'),
                                      document('POM INIESTA-MEMORIA INFORMATIVA', 'memoria')]))
        row = instrument_record('PLAN DE ORDENACIÓN MUNICIPAL DE INIESTA (POM INIESTA)', INVENTORY, docs)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '16113')
        self.assertEqual(row['documentos'][1]['titulo'], 'POM INIESTA-MEMORIA INFORMATIVA')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)
        self.assertFalse(row['publication_ready'])

    def test_does_not_promote_form_or_procurement_to_instrument(self):
        for title in ('Solicitud de licencia urbanística', 'Licitación de obra', 'Noticias del pleno'):
            with self.assertRaises(ValueError):
                instrument_record(title, INVENTORY, [{'titulo': 'form', 'url': INVENTORY}])

    def test_missing_table_empty_and_external_documents(self):
        with self.assertRaises(ValueError):
            parse_listing('<h1>Error</h1>')
        with self.assertRaises(ValueError):
            parse_listing(listing([]))
        self.assertEqual(parse_listing(listing([]) + 'No se han encontrado elementos'), [])
        with self.assertRaises(ValueError):
            parse_listing(listing(['<a class="gIconLink" href="https://other.es/preview-document/a">Doc</a>']))

    def test_pagination_fails_explicitly(self):
        for control in ('<a href="#" onclick="more()">Mostrar más</a>', '<a href="?page=2" rel="next">2</a>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_listing(listing([document('Doc', 'a')]) + control)

    def test_live_workflow_contract_and_count_guard(self):
        root = listing([folder('MODIFICACIÓN PUNTUAL NN.SS: CENTRO DE MAYORES', 0, 'empty'),
                        folder('PLAN DE ORDENACIÓN MUNICIPAL DE INIESTA (POM INIESTA)', 2, 'pom')])
        class Response:
            def __init__(self, text='', location=None):
                self.text = text
                self.headers = {'Ajax-Location': location} if location else {}
        adapter = IniestaAyuntamientoAdapter('iniesta')
        def responses(count=2):
            return [Response(root), Response(location='transparency/empty/'),
                    Response(listing([]) + 'No se han encontrado elementos'),
                    Response(location='transparency/pom/'),
                    Response(listing([document('Normas', 'a'), document('Memoria', 'b')][:count]))]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'rows.jsonl'
            with patch.object(adapter, '_get', side_effect=responses()):
                report = adapter.backfill_proyectos(output)
            self.assertEqual(report['count'], 1)
            self.assertEqual(report['skipped'][0]['reason'], 'empty_folder')
            self.assertEqual(len(json.loads(output.read_text())['documentos']), 2)
            original = output.read_text()
            with patch.object(adapter, '_get', side_effect=responses(1)):
                with self.assertRaisesRegex(ValueError, 'document count'):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), original)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('iniesta')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, IniestaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with self.assertRaises(NotImplementedError):
            adapter.backfill_licencias(Path('/unused'))


if __name__ == '__main__':
    unittest.main()
