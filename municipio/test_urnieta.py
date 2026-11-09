import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.urnieta import SOURCE, UrnietaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest


def entry(title='PLAN PARCIAL AIU 31 AZKARATE', uuid='fa7d20a5-1042-9ae7-86f9-700b32e07797', date='01·10·2025'):
    url = '/documents/9774148/43144179/PP AZKARATE.zip/' + uuid
    return f'''<div class="documento"><a href="{url}">zip</a>
    <span class="fecha">{date}</span><div class="titulo"><a href="{url}">{title}</a></div></div>'''


def page(body):
    return '<main id="main-content"><div class="documentos">' + body + '</div></main>'


class UrnietaTests(unittest.TestCase):
    def test_documents_grouped_and_dates_not_invented(self):
        rows = Adapter.parse_inventory(page(entry() + entry(uuid='48476402-601d-5a8d-68f3-fc9fa8b4e7f7')))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['fecha_catalogo'], '2025-10-01')
        self.assertIn('PP%20AZKARATE.zip', row['documentos'][0]['url'])
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'geometry', 'lat', 'lon', 'fase'):
            self.assertIsNone(row[field])
        self.assertEqual(row['codigo_ine'], '20072')
        self.assertEqual(row['id'], Adapter.parse_inventory(page(entry()))[0]['id'])

    def test_distinct_instruments_same_area_and_explicit_phase(self):
        rows = Adapter.parse_inventory(page(entry('PLAN PARCIAL AIU 32 BABILONIA') +
            entry('APROBACIÓN INICIAL DEL PROYECTO DE URBANIZACIÓN DEL AIU 32 BABILONIA')))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['fase'], 'aprobación inicial')
        self.assertIsNone(rows[1]['fecha_aprob'])

    def test_reject_partial_or_unrelated_sources(self):
        for body in ('', entry('Solicitud de licencia de obra'), entry().replace('class="fecha"', 'class="other"'),
                     entry().replace('/documents/', 'https://example.org/documents/'),
                     entry() + '<div class="pagination"><a href="?cur=2">2</a></div>',
                     entry() + '<a rel="next" href="?cur=2">More</a>'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                Adapter.parse_inventory(page(body))

    def test_live_method_writes_and_failure_preserves_output(self):
        response = Mock(url=SOURCE, content=page(entry()).encode(), headers={'Content-Type': 'text/html'})
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            adapter = Adapter('urnieta')
            with patch('municipio.adapters.urnieta.requests.get', return_value=response), patch.object(
                    Adapter, 'check_document', return_value={'http_status': 404, 'availability': 'unavailable'}):
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 1)
                before = output.read_bytes()
                self.assertEqual(json.loads(before)['municipio'], 'Urnieta')
                self.assertEqual(json.loads(before)['documentos'][0]['availability'], 'unavailable')
                response.content = page('').encode()
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(output, Path(tmp) / 'state.json')
                self.assertEqual(output.read_bytes(), before)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('urnieta')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.urnieta:UrnietaAyuntamientoAdapter')

    def test_document_availability_and_misleading_success(self):
        response = Mock(status_code=200, headers={'Content-Type': 'application/pdf'})
        response.iter_content.return_value = iter([b'%PDF-1.6'])
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with patch('municipio.adapters.urnieta.requests.get', return_value=context):
            self.assertEqual(Adapter.check_document(SOURCE)['availability'], 'available')
            response.status_code = 404
            self.assertEqual(Adapter.check_document(SOURCE)['availability'], 'unavailable')
            response.status_code = 200
            response.iter_content.return_value = iter([b'<html>'])
            with self.assertRaises(ValueError):
                Adapter.check_document(SOURCE)


if __name__ == '__main__':
    unittest.main()
