import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.librilla import LibrillaAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory(links=''):
    return ('<a href="/solicitudes/licencia.pdf">Solicitud de licencia</a>'
            '<div id="noticias"><h2>Plan General Municipal de Ordenación '
            '(Modificaciones Aprobación Provisional)</h2>' + links + '</div>')


def doc(name):
    return f'<a href="http://descargas.librilla.es/pgom/{name}.pdf">{name}</a>'


class LibrillaTests(unittest.TestCase):
    def test_group_all_documents_and_deduplicate(self):
        rows = parse_inventory(inventory(doc('MEMORIAS/Normas') + doc('PLANOS/Hoja1') + doc('MEMORIAS/Normas')))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '30023')
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE)
        self.assertFalse(row['publication_ready'])
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)

    def test_no_document_limit(self):
        self.assertEqual(len(parse_inventory(inventory(''.join(doc(f'PLANOS/{i}') for i in range(240))))[0]['documentos']), 240)

    def test_empty_changed_or_untrusted_inventory_fails(self):
        for html in ('<html>error</html>', inventory(), inventory('<a href="https://example.org/plan.pdf">Plan</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails(self):
        for pagination in ('<a rel="next" href="?p=2">2</a>', '<div class="pagination">2</div>', '<a href="?pagina=2">2</a>', '<a href="?p=2">Siguiente</a>'):
            with self.subTest(pagination=pagination), self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(inventory(doc('Plan') + pagination))

    def test_adapter_live_path_and_failure_preserves_output(self):
        response = Mock(url=SOURCE, headers={'Content-Type': 'text/html'}, text=inventory(doc('MEMORIAS/Normas')))
        adapter = LibrillaAyuntamientoAdapter('librilla')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch('municipio.adapters.librilla.requests.get', return_value=response) as fetch:
                report = adapter.update_proyectos(output, Path(directory) / 'state.json')
                self.assertEqual(fetch.call_args.args[0], SOURCE)
                self.assertEqual(report['count'], 1)
                self.assertEqual(json.loads(output.read_text())['id'], 'librilla-pgmo')
                saved = output.read_text()
                response.text = inventory()
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
                self.assertEqual(output.read_text(), saved)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('librilla')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('30023', 'Librilla', 'Murcia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, LibrillaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
