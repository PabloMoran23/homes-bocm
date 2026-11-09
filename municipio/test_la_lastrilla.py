"""Offline parser and complete-snapshot contract tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_lastrilla import (
    BASE, SOURCE, LaLastrillaAyuntamientoAdapter, parse_files, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(doc_id='10', start=1, total=1, book='PU', title='PLAN PARCIAL', files=True):
    file_cell = (f'<a href="/PlanPublica/ldoc_files.do;jsessionid=temporary?cDocId={doc_id}">files</a>'
                 if files else '<img alt="No hay documentos">')
    next_link = ''
    if start < total:
        next_link = (f'<a onclick="doResults(\'results\',unescape(\'searchVPubDocMuniPlau.do?'
                     f'provincia=40%26municipio=112%26bInfoPublica=N%26pager.offset={start}\'))">Siguiente »</a>')
    return f'''LASTRILLA (LA) Código INE: 40112
    <table class="cuadroAplicacion"><tr>
    <th>Libro</th><th>Instrumento</th><th>Fecha de publicación</th><th>Fecha de acuerdo</th><th>Título</th><th></th></tr>
    <tr><td>{book}</td><td>PP</td><td><a onclick="doGoBoletin('{doc_id}', '40112-{book}-20260416-{doc_id}')">16/04/2026</a></td>
    <td>07/04/2026</td><td>{title}</td><td>{file_cell}</td></tr></table>
    Mostrando resultados {start}-{start} de {total} {next_link}'''


FILES = '''<h1>Lastrilla, La (Segovia )</h1><table class="cuadroAplicacion">
<tr><th>Nombre del Fichero</th><th>Fichero</th></tr>
<tr><td>memoria.pdf</td><td><a href="/PlanPublica/openFichero.do?cFicheroId=101">PDF</a></td></tr>
<tr><td>planos.pdf</td><td><a href="/PlanPublica/openFichero.do?cFicheroId=102">PDF</a></td></tr></table>'''


class LaLastrillaTests(unittest.TestCase):
    def test_identity_dates_and_session_free_links(self):
        rows, counts, next_url = parse_inventory(inventory(), first_page=True)
        self.assertEqual(counts, (1, 1, 1))
        self.assertIsNone(next_url)
        self.assertEqual(rows[0]['published'], '2026-04-16')
        self.assertEqual(rows[0]['agreement'], '2026-04-07')
        self.assertEqual(rows[0]['files_url'], BASE + 'ldoc_files.do?cDocId=10')
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace('Código INE: 40112', 'Código INE: 40001'), first_page=True)

    def test_document_grouping(self):
        docs = parse_files(FILES)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[1]['titulo'], 'planos.pdf')
        with self.assertRaises(ValueError):
            parse_files(FILES.replace('Lastrilla, La', 'Segovia'))
        with self.assertRaises(ValueError):
            parse_files(FILES + '<a class="rnavLink">Siguiente</a>')

    def test_pagination_missing_or_wrong_scope_rejected(self):
        html = inventory(total=2)
        self.assertIn('pager.offset=1', parse_inventory(html)[2])
        with self.assertRaises(ValueError):
            parse_inventory(html.replace('Siguiente', 'broken'))
        with self.assertRaises(ValueError):
            parse_inventory(html.replace('municipio=112', 'municipio=113'))
        with self.assertRaises(ValueError):
            parse_inventory(html.replace('1-1 de 2', '1-2 de 2'))

    def test_live_contract_traverses_pages_and_excludes_nonprojects(self):
        adapter = LaLastrillaAyuntamientoAdapter('la-lastrilla')
        pages = [inventory(total=3), inventory('20', start=2, total=3, title='SENTENCIA DEL RECURSO'),
                 inventory('30', start=3, total=3, files=False), FILES]
        # First discover every inventory page, then retrieve instrument files.
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=pages):
            path = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['inventory_entries'], 3)
            self.assertEqual(len(result['excluded']), 1)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(rows[1]['documentos_status'], 'sin_ficheros_en_inventario')
            self.assertIsNone(rows[0]['fecha_aprob'])
            self.assertIsNone(rows[0]['lat'])
            self.assertFalse(rows[0]['publication_ready'])

    def test_failure_does_not_overwrite_previous_snapshot(self):
        adapter = LaLastrillaAyuntamientoAdapter('la-lastrilla')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', return_value=inventory(total=2)):
            path = Path(directory) / 'proyectos.jsonl'
            path.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('la-lastrilla')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, LaLastrillaAyuntamientoAdapter)
        self.assertEqual(manifest.provincia, 'Segovia')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
