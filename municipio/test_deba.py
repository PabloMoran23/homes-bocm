"""Offline parser and adapter-contract tests; fixtures are not extracted records."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.deba import DebaAyuntamientoAdapter as Adapter
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def inventory(extra=''):
    return '''<main><h1>Normas Subsidiarias</h1><div class="accordion-block">
      <div class="accordion"><h2>Deba</h2><ul>
        <li><a href="/plan">PLAN ESPECIAL DE PRUEBA</a></li>
        <li><a href="/plan?set_language=es">PLAN ESPECIAL DE PRUEBA</a></li>
        <li><a href="/empty"></a></li>
        <li><a href="/convenio">CONVENIO DE CONCERTACIÓN</a></li>
      </ul></div>
      <div class="accordion"><h2>Itziar</h2></div>
      <div class="accordion"><h2>Lastur</h2></div>
      </div>''' + extra + '</main>'


class DebaTests(unittest.TestCase):
    def test_inventory_groups_and_does_not_infer_dates_or_coordinates(self):
        rows = Adapter.parse_inventory(inventory())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '20029')
        self.assertEqual(row['ambito'], 'Deba')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertNotIn('lat', row)
        self.assertEqual(row['id'], Adapter.parse_inventory(inventory())[0]['id'])

    def test_all_documents_retained_with_original_provenance(self):
        detail = '''<main><h1>Plan</h1><a href="#heading" aria-hidden="true"></a>
          <a href="/memoria.pdf">Memoria 2011</a>
          <a href="/memoria.pdf">Memoria repetida</a>
          <a href="http://backend:8080/Plone/eu/plan.pdf/@@download/file">Planos</a>
          <a href="https://ssl4.gipuzkoa.net/castell/bog/2012/05/15/c1204566.pdf">Aprobación definitiva</a>
          <a href="/resumen">Resumen del acuerdo del 29 de julio de 2010</a>
          </main>'''
        docs = Adapter.parse_documents(detail, 'https://www.deba.eus/plan')
        self.assertEqual(len(docs), 4)
        self.assertEqual(docs[1]['url'], 'https://www.deba.eus/eu/plan.pdf/@@download/file')
        self.assertTrue(docs[1]['href_publicado'].startswith('http://backend:8080/Plone/'))
        self.assertTrue(all(d['source_url'] == 'https://www.deba.eus/plan' for d in docs))
        self.assertEqual(docs[-1]['url'], 'https://www.deba.eus/resumen')

    def test_pagination_and_layout_changes_fail_explicitly(self):
        for extra in ['<a rel="next" href="?page=2">2</a>',
                      '<a href="?b_start=20">Siguiente</a>',
                      '<div class="pagination"><a href="?page=2">2</a></div>']:
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'Pagination'):
                Adapter.parse_inventory(inventory(extra))
        for html in ['<main><h1>Error</h1></main>', '<html>Unavailable</html>',
                     inventory().replace('PLAN ESPECIAL DE PRUEBA', 'Solicitud de licencia')]:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        with self.assertRaisesRegex(ValueError, 'no linked documentation'):
            Adapter.parse_documents('<main><h1>Plan</h1></main>', 'https://www.deba.eus/plan')

    def test_failed_live_fetch_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous snapshot\n')
            with patch('municipio.adapters.deba.requests.Session.get', side_effect=RuntimeError('offline')):
                with self.assertRaisesRegex(RuntimeError, 'offline'):
                    Adapter('deba').backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot\n')

    def test_manifest_loading_and_disabled_licences(self):
        manifest = load_manifest('deba')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')
            self.assertEqual(list(map(json.loads, output.read_text().splitlines())), [])


if __name__ == '__main__':
    unittest.main()
