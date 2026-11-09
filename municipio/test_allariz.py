import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.allariz import (
    AllarizAyuntamientoAdapter, PECHA_URL, PXOM_URL, parse_pecha, parse_pxom,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def table(name, date=''):
    return (f'<table class="tabla-documentos"><tr><td>{date}</td><td>{name}</td>'
            f'<td><a href="/wp-content/uploads/{name}.pdf">Download</a></td></tr></table>')


PXOM = ('<h2>Plan Especial de Reforma Interior (PERI)</h2>' + table('memoria', '09/05/1995')
        + table('normativa') + '<h2>Normativa e Planos do Plan Xeral Vixente</h2>'
        + table('plan') + table('plano') + '<h2>Outros Plans e Normativas</h2>'
        + table('encauzamento', '26/06/2009'))
PECHA = ('<main><h1>Documentación PECHA</h1>'
         '<h2>Fase aprobación inicial: Exposición pública Plan Especial Casco Histórico Allariz;</h2>'
         '<a href="/wp-content/uploads/32001_PECHA_202412_AI_NU.pdf">Normas</a>'
         '<a href="/wp-content/uploads/32001_PECHA_202412_AI_MX_01INF.pdf">Memoria</a>'
         '<a href="/wp-content/uploads/Allariz_modelo-de-alegacion-1.pdf">Modelo alegación</a></main>')


class AllarizTests(unittest.TestCase):
    def test_grouped_documents_and_unknown_dates(self):
        rows = parse_pxom(PXOM)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1])
        self.assertEqual(rows[0]['documentos'][0]['fecha_fuente'], '1995-05-09')
        self.assertEqual(rows[2]['documentos'][0]['fecha_fuente'], '2009-06-26')
        for r in rows:
            self.assertIsNone(r['fecha_publicacion'])
            self.assertIsNone(r['fecha_acuerdo'])
            self.assertIsNone(r['fecha_aprob'])
            self.assertIsNone(r['geometry'])
            self.assertEqual(r['codigo_ine'], '32001')
        self.assertEqual(rows[1]['fase'], 'vixente')

    def test_pecha_excludes_forms_and_retains_phase(self):
        row, = parse_pecha(PECHA)
        self.assertEqual(len(row['documentos']), 2)
        self.assertIn('aprobación inicial', row['fase'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertTrue(all(d['source_url'] == PECHA_URL for d in row['documentos']))

    def test_duplicate_links_do_not_duplicate_instrument(self):
        rows = parse_pxom(PXOM + '<h2>Normativa e Planos do Plan Xeral Vixente</h2>' + table('plan'))
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[1]['documentos']), 2)

    def test_navigation_login_and_missing_sections_fail(self):
        for parser in (parse_pxom, parse_pecha):
            for html in ('<h1>Login</h1><a href="/login">Entrar</a>', '', '<a>Urbanismo</a>'):
                with self.subTest(parser=parser.__name__, html=html), self.assertRaises(ValueError):
                    parser(html)
        with self.assertRaises(ValueError):
            parse_pxom(PXOM.replace('Normativa e Planos do Plan Xeral Vixente', 'Unknown section'))
        with self.assertRaises(ValueError):
            parse_pecha(PECHA.replace('Fase aprobación inicial:', 'Fase aprobación definitiva:'))

    def test_pagination_fails_without_partial_output(self):
        for parser, html in ((parse_pxom, PXOM), (parse_pecha, PECHA)):
            for more in ('<a rel="next" href="/page/2">2</a>', '<a href="?page=2">Seguinte</a>',
                         '<div class="pagination"><a href="/2">2</a></div>'):
                with self.subTest(more=more), self.assertRaises(ValueError):
                    parser(html + more)

    def test_unrecognized_pecha_document_fails(self):
        with self.assertRaises(ValueError):
            parse_pecha(PECHA.replace('Allariz_modelo-de-alegacion-1.pdf', 'new-plan.pdf'))

    def test_external_document_rejected(self):
        with self.assertRaises(ValueError):
            parse_pxom(PXOM.replace('/wp-content/uploads/memoria.pdf', 'https://example.org/memoria.pdf'))
        with self.assertRaises(ValueError):
            parse_pecha(PECHA.replace('/wp-content/uploads/32001_PECHA_202412_AI_NU.pdf',
                                      'https://example.org/wp-content/uploads/32001_PECHA_202412_AI_NU.pdf'))

    def test_manifest_and_snapshot_refresh(self):
        raw = load_yaml(Path('data/municipios/allariz/manifest.yaml'))
        self.assertEqual(raw['codigo_ine'], '32001')
        self.assertEqual(raw['provincia'], 'Ourense')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        adapter = load_portal_adapter(load_manifest('allariz'))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[PXOM, PECHA, PXOM, PECHA]):
                adapter.backfill_proyectos(output)
                first = output.read_text()
                adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(output.read_text(), first)
            self.assertEqual(len([json.loads(line) for line in first.splitlines()]), 4)

    def test_source_failure_preserves_existing_snapshot(self):
        adapter = AllarizAyuntamientoAdapter('allariz')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[PXOM, '<h1>Error</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
