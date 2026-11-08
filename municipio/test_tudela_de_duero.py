"""Offline parser and pagination regressions; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.tudela_de_duero import (
    BASE, TudelaDeDueroAyuntamientoAdapter, build_records, clean_url,
    date_value, parse_files, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def row(doc='301974', title='ESTUDIO DE DETALLE CALLEJÓN DE LA IGLESIA', code='ED', book='PU'):
    return f'''<tr><td>{book}</td><td>{code}</td>
    <td><a onclick="doGoBoletin('{doc}', '47175-PU-20261022-{doc}')">22/10/2026</a></td>
    <td>24/09/2026</td><td>{title}</td><td>
    <a href="/PlanPublica/ldoc_files.do;jsessionid=token?cDocId={doc}">Files</a></td></tr>'''


def inventory(rows, start=1, end=1, total=1):
    return f'''<h1>TUDELA DE DUERO</h1><p>Código INE: 47175</p>
    <table class="cuadroAplicacion">{rows}</table>
    <p>Mostrando resultados {start}-{end} de {total}</p>'''


FILES = '''<h1>Tudela de Duero (Valladolid)</h1><table class="cuadroAplicacion">
<tr><td>Memoria.pdf</td><td><a href="openFichero.do;jsessionid=secret?cFicheroId=11">PDF</a></td></tr>
<tr><td>Planos.pdf</td><td><a href="openFichero.do?cFicheroId=12">PDF</a></td></tr></table>'''


class ParserTests(unittest.TestCase):
    def test_publication_and_agreement_are_distinct(self):
        entries, counts = parse_inventory(inventory(row()))
        self.assertEqual(counts, (1, 1, 1))
        record = build_records(entries)[0]
        self.assertEqual(record['fecha_publicacion'], '2026-10-22')
        self.assertEqual(record['fecha_acuerdo'], '2026-09-24')
        self.assertNotIn('fecha_aprob', record)
        self.assertNotIn('fase', record)
        self.assertIsNone(record['geometry'])
        self.assertFalse(record['publication_ready'])

    def test_files_are_grouped_and_session_tokens_removed(self):
        entries, _ = parse_inventory(inventory(row()))
        entries[0]['documentos'] = parse_files(FILES)
        records = build_records(entries)
        self.assertEqual(len(records), 1)
        self.assertEqual([d['nombre'] for d in records[0]['documentos']], ['Memoria.pdf', 'Planos.pdf'])
        self.assertTrue(all(';jsessionid' not in d['url'] for d in records[0]['documentos']))

    def test_excludes_non_projects_and_retains_pgou_events(self):
        rows = (row('1', 'PLAN GENERAL DE ORDENACIÓN URBANA (REVISIÓN)', 'PGOU') +
                row('2', 'SENTENCIA NULIDAD DE VARIOS APARTADOS DEL PGOU', 'PGOU') +
                row('3', 'CONVENIO URBANÍSTICO SECTOR 17', 'CN_UR', 'CU') +
                row('4', 'DIRECTRICES VALLADOLID Y ENTORNO', 'DOAS', 'OT') +
                row('5', 'SOLICITUD DE LICENCIA DE OBRAS', 'ED'))
        entries, _ = parse_inventory(inventory(rows, end=5, total=5))
        records = build_records(entries)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['eventos_relacionados'][0]['doc_id'], '2')
        self.assertEqual(records[0]['source_document_id'], '1')

    def test_wrong_municipality_or_missing_total_fails(self):
        for html in [inventory(row()).replace('47175', '31232'), '<html>Maintenance</html>',
                     inventory(row()).replace('Mostrando resultados', 'Other')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_wrong_count_and_invalid_dates_fail(self):
        with self.assertRaises(ValueError):
            parse_inventory(inventory(row(), end=2, total=2))
        with self.assertRaises(ValueError):
            date_value('31/02/2026')
        self.assertIsNone(date_value('01/01/1970'))
        self.assertIsNone(date_value(''))

    def test_documents_without_downloads_keep_inventory_record(self):
        html = inventory(row()).replace('<a href="/PlanPublica/ldoc_files.do;jsessionid=token?cDocId=301974">Files</a>', '')
        entries, _ = parse_inventory(html)
        self.assertEqual(build_records(entries)[0]['documentos'], [])
        with self.assertRaises(ValueError):
            parse_files('<h1>Tudela de Duero</h1>')
        with self.assertRaises(ValueError):
            clean_url('https://other.invalid/a')

    def test_complete_pagination_and_separate_document_packages(self):
        adapter = TudelaDeDueroAyuntamientoAdapter('tudela-de-duero')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[
            inventory(row('1'), total=2), inventory(row('2'), start=2, end=2, total=2),
            FILES, FILES.replace('11', '21').replace('12', '22'),
        ]) as fetch:
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            records = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['inventory_entries'], 2)
            self.assertEqual(len(records), 2)
            self.assertIn('pager.offset=1', fetch.call_args_list[1].args[1])
            self.assertTrue(records[1]['documentos'][0]['url'].endswith('=21'))
            self.assertTrue(records[0]['documentos'][0]['url'].endswith('=11'))

    def test_repeated_page_does_not_write_partial_output(self):
        adapter = TudelaDeDueroAyuntamientoAdapter('tudela-de-duero')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[
            inventory(row(), total=2), inventory(row(), total=2),
        ]):
            out = Path(tmp) / 'proyectos.jsonl'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertFalse(out.exists())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('tudela-de-duero')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '47175')
        self.assertEqual(manifest.provincia, 'Valladolid')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
