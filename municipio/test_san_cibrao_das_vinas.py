"""Offline contract tests; fixtures model the reviewed ROTPG table, not news."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.san_cibrao_das_vinas import (
    HEADERS, SOURCE, SanCibraoDasVinasAyuntamientoAdapter, merge_rows, page_url, parse_page,
)
from municipio.manifest import load_manifest


def fixture(reference='ROTPG/P/2/2026', approval='30/10/2025', extra_doc='', pager=''):
    cells = ['Estudo de Detalle', '', 'ED NA RÚA ALDEA DE ABAIXO, A CARBALLEIRA',
             '09/01/2026', reference, 'Ourense', 'Municipal', approval, '18/11/2025',
             '29/01/2026', '', '<a href="http://www.planeamentourbanistico.xunta.es/siotuga/rexistro/index.php?url=plan.zip">Descargar</a>' + extra_doc]
    return ('<select name="provincia"><option value="32" selected>Ourense</option></select>'
            '<select name="concello"><option value="677" selected>San Cibrao das Viñas</option></select>'
            '<table id="edit-table"><thead><tr>' + ''.join('<th>' + h + '</th>' for h in HEADERS)
            + '</tr></thead><tbody><tr>' + ''.join('<td>' + c + '</td>' for c in cells)
            + '</tr></tbody></table><ul class="pagination">' + pager + '</ul>')


class ParserTests(unittest.TestCase):
    def test_identity_dates_and_document_grouping(self):
        rows, _ = parse_page(fixture(extra_doc='<a href="/second.zip">Anexo</a>'), SOURCE)
        row = rows[0]
        from municipio.entity_policy import classify
        self.assertTrue(classify(row)['activity_eligible'])
        self.assertEqual(row['codigo_ine'], '32075')
        self.assertEqual(row['fecha_aprob'], '2025-10-30')
        self.assertEqual(row['fecha_inscripcion'], '2026-01-09')
        self.assertEqual(row['fecha_publicacion_doga'], '2025-11-18')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertNotIn('fase', row)
        self.assertIsNone(row['geometry'])
        self.assertEqual(len(row['documentos']), 2)
        grouped = {}
        merge_rows(grouped, rows)
        more, _ = parse_page(fixture(extra_doc='<a href="/third.zip">Outro</a>'), page_url(1))
        merge_rows(grouped, more)
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(next(iter(grouped.values()))['documentos']), 3)

    def test_inconsistent_source_dates_are_flagged_not_repaired(self):
        rows, _ = parse_page(fixture(approval='29/11/2026'), SOURCE)
        self.assertEqual(rows[0]['fecha_aprob'], '2026-11-29')
        self.assertEqual(len(rows[0]['advertencias_fechas']), 3)

    def test_fail_closed_on_wrong_scope_schema_or_non_project(self):
        for html in [fixture().replace('value="677"', 'value="678"'),
                     fixture().replace('Ourense</td>', 'Lugo</td>'),
                     fixture().replace('Fecha inscripción', 'Fecha'),
                     '<h1>Solicitude de licenza de obra</h1>',
                     fixture().replace('ROTPG/P/2/2026', 'Licitación 2026')]:
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                parse_page(html, SOURCE)

    def test_pagination_keeps_scope(self):
        _, pages = parse_page(fixture(pager='<a href="?provincia=32&amp;concello=677&amp;page=1">2</a>'), SOURCE)
        self.assertEqual(pages, {1})
        with self.assertRaises(ValueError):
            parse_page(fixture(pager='<a href="?page=1">2</a>'), SOURCE)

    def test_live_path_follows_all_pages_and_rejects_repeats(self):
        first = fixture(pager='<a href="?provincia=32&amp;concello=677&amp;page=1">2</a>')
        second = fixture(reference='RPG/00040/2019')
        class Response:
            def __init__(self, html, url):
                self.text, self.url, self.content = html, url, html.encode()
            def raise_for_status(self):
                pass
        adapter = SanCibraoDasVinasAyuntamientoAdapter('san-cibrao-das-vinas')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            with patch('requests.Session.get', side_effect=[Response(first, SOURCE), Response(second, page_url(1))]) as get:
                result = adapter.backfill_proyectos(path)
            self.assertEqual(result['pages'], 2)
            self.assertEqual(len(path.read_text().splitlines()), 2)
            self.assertEqual(get.call_count, 2)
            original = path.read_text()
            with patch('requests.Session.get', side_effect=[Response(first, SOURCE), Response(first, page_url(1))]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), original)
            result = adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')
            self.assertEqual(result['status'], 'disabled')

    def test_manifest_resolves_and_safety_settings(self):
        import yaml
        manifest = load_manifest('san-cibrao-das-vinas')
        raw = yaml.safe_load(manifest.path.read_text())
        self.assertEqual(raw['codigo_ine'], '32075')
        self.assertEqual(manifest.provincia, 'Ourense')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
