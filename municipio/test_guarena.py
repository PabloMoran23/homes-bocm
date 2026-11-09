"""Offline parser and adapter contract checks; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.guarena import SOURCE, GuarenaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(extra=''):
    return '''<div data-elementor-type="wp-page"><h1>Plan General Municipal</h1>
    <a href="/recursos/pdf/plan-general-municipal/a.pdf">2023 MEMORIA PGM</a>
    <a href="/recursos/pdf/plan-general-municipal/b.pdf">NORMATIVA PGM</a>
    <a href="/recursos/pdf/plan-general-municipal/a.pdf">Duplicado</a>
    <a href="/licencia.pdf">Licencia obra mayor</a>''' + extra + '</div>'


class GuarenaTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '06060')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['geometry'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertNotIn('fase', row)

    def test_no_navigation_or_forms_as_records(self):
        for html in ('<a>Plan General Municipal</a>', '<div data-elementor-type="wp-page"><h1>Plan General Municipal</h1><a href="/licencia.pdf">Licencia</a></div>', '<h1>Noticias</h1>'):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_explicitly(self):
        for extra in ('<a rel="next" href="?page=2">Siguiente</a>', '<div class="page-numbers">2</div>'):
            with self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(inventory(extra))

    def test_reject_redirect_and_untrusted_documents(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory(), 'https://example.org/')
        with self.assertRaises(ValueError):
            parse_inventory(inventory('<a href="https://example.org/recursos/pdf/plan-general-municipal/x.pdf">PGM</a>'))

    @patch('municipio.adapters.guarena.requests.get')
    def test_live_methods_and_disabled_licences(self, get):
        get.return_value = Mock(text=inventory(), url=SOURCE)
        adapter = load_portal_adapter(load_manifest('guarena'))
        with tempfile.TemporaryDirectory() as temp:
            out, state = Path(temp) / 'out.jsonl', Path(temp) / 'state.json'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['count'], 1)
            first = json.loads(out.read_text())
            adapter.update_proyectos(out, state)
            self.assertEqual(json.loads(out.read_text())['id'], first['id'])
            self.assertFalse(state.exists())
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')
            self.assertTrue(adapter.update_licencias(out, state)['disabled'])

    @patch('municipio.adapters.guarena.requests.get')
    def test_failed_fetch_keeps_previous_output(self, get):
        get.return_value = Mock(text='<h1>Error</h1>', url=SOURCE)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'out.jsonl'
            out.write_text('previous\n')
            with self.assertRaises(ValueError):
                GuarenaAyuntamientoAdapter().backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')


if __name__ == '__main__':
    unittest.main()
