"""Offline regression tests for the provincial approved-works inventory."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.oza_cesuras import OzaCesurasAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def card(title, year=2026, budget='1.234,56', links=''):
    return f'''<div><div><span class="uppercase">Exercicio {year}</span></div>
    <div><p class="text-sm font-medium leading-tight mb-4">{title}</p>
    <div><span>Orzamento:</span><span>{budget} €</span></div>
    <div><span>Aportación:</span><span>900,00 €</span></div>{links}</div></div>'''


def page(cards, total=2):
    return f'''<h1>PLAN ÚNICO Oza-Cesuras</h1>
    <li><div><span>Obras aprobadas</span></div><div>{total}</div></li>{cards}'''


class InventoryTests(unittest.TestCase):
    def test_physical_works_dates_money_provenance_and_document_grouping(self):
        html = page(card('Rede de auga', links='<a href="/a.pdf">Memoria</a><a href="/a.pdf">Copia</a><a href="/b.pdf">Planos</a>')
                    + card('Beirarrúas', 2017)) + '<p>Solicitude de licenza</p>'
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 2)
        row = rows[0]
        self.assertEqual((row['codigo_ine'], row['source']), ('15902', 'diputacion'))
        self.assertEqual(row['presupuesto_eur'], '1234.56')
        self.assertEqual(row['ejercicio'], 2026)
        self.assertTrue(all(row[k] is None for k in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon']))
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], 'https://plan-unico.dacoruna.gal/a.pdf')

    def test_ids_survive_reordering_and_budget_changes(self):
        first = Adapter.parse_projects(page(card('Rede') + card('Ponte', 2025)))
        second = Adapter.parse_projects(page(card('Ponte', 2025) + card('Rede', budget='2.345,00')))
        self.assertEqual([r['id'] for r in first], [r['id'] for r in second])

    def test_incomplete_ambiguous_changed_or_paginated_source_rejected(self):
        good = page(card('Rede'), 1)
        cases = [page(card('Rede'), 2), page('', 0), page(card('Rede') * 2),
                 good.replace('Oza-Cesuras', 'Outro concello'),
                 good.replace('Orzamento:', 'Unknown:'),
                 good + '<a rel="next" href="/2">2</a>',
                 good + '<a href="?page=2">2</a>',
                 good.replace('1.234,56', 'bad')]
        for html in cases:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_loading_live_method_and_disabled_licences(self):
        adapter = load_portal_adapter(load_manifest('oza-cesuras'))
        html = page(card('Rede'), 1)
        class Response:
            url = SOURCE
            text = html
            def raise_for_status(self):
                pass
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'projects.jsonl'
            with patch('municipio.adapters.oza_cesuras.requests.get', return_value=Response()):
                self.assertEqual(adapter.backfill_proyectos(out)['rows'], 1)
                self.assertEqual(adapter.update_proyectos(out, Path(directory) / 'state')['rows'], 1)
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
