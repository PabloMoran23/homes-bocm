import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.santa_comba import SOURCE_URL, SantaCombaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def fixture(rows=None, count=None):
    rows = rows or [
        ('2026', 'Mellora de vías nas parroquias de Cicere e Grixoa', '173.634,60 €', '173.634,60 €'),
        ('2025', 'Subministración pequeno equipamento Brigada municipal', '61.831,00 €', '61.258,28 €'),
    ]
    body = ''.join('<tr>' + ''.join(f'<td>{v}</td>' for v in row) + '</tr>' for row in rows)
    return f'''<h1>PLAN ÚNICO <strong>Santa Comba</strong></h1>
    <select id="selector-exercicio"><option selected value="todos">Todos</option></select>
    <li><div><span>Obras aprobadas</span></div><div class="grow">{count if count is not None else len(rows)}</div></li>
    <table aria-label="Lista de obras e investimentos"><thead><tr>
    <th>Exercicio</th><th>Obxecto</th><th>Orzamento</th><th>Aportación</th>
    </tr></thead><tbody>{body}</tbody></table>'''


class SantaCombaTests(unittest.TestCase):
    def test_physical_works_dates_and_amounts(self):
        rows, report = parse_inventory(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['ejercicio'], 2026)
        self.assertEqual(row['presupuesto_eur'], '173634.60')
        self.assertEqual(row['codigo_ine'], '15077')
        self.assertEqual(row['organismo_fuente'], 'Deputación Provincial da Coruña')
        self.assertFalse(any(k.startswith('fecha') for k in row))
        self.assertNotIn('lat', row)
        self.assertEqual(len(report['excluded']), 1)

    def test_group_documents_and_ignore_duplicate_cards(self):
        title = 'Reforma local para Centro de Día'
        linked = title + '<a href="/proyecto.pdf">Proxecto</a><a href="/acordo.pdf">Acordo</a>'
        html = fixture([('2025', linked, '259.549,21 €', '259.549,21 €')])
        rows, _ = parse_inventory(html + '<div>Exercicio 2025 Reforma local para Centro de Día</div>')
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][0]['url'], 'https://plan-unico.dacoruna.gal/proyecto.pdf')

    def test_reject_incomplete_filtered_or_paginated_source(self):
        for html in [fixture(count=70), fixture().replace('value="todos"', 'value="2026"'),
                     fixture() + '<a rel="next" href="?page=2">2</a>',
                     fixture().replace('Santa Comba', 'Outro Concello'), '<html>Unavailable</html>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_reject_non_projects_and_invalid_data(self):
        for title in ['Solicitude de licenza de obras', 'Anuncio de licitación', 'Festa municipal']:
            with self.subTest(title=title), self.assertRaises(ValueError):
                parse_inventory(fixture([('2026', title, '100,00 €', '100,00 €')]))
        with self.assertRaises(ValueError):
            parse_inventory(fixture().replace('173.634,60', 'not-an-amount'))

    def test_stable_ids_across_order_and_amount_changes(self):
        a = ('2026', 'Mellora de vías en Cicere', '100,00 €', '100,00 €')
        b = ('2025', 'Reforma local para Centro de Día', '200,00 €', '200,00 €')
        first, _ = parse_inventory(fixture([a, b]))
        second, _ = parse_inventory(fixture([b, a]).replace('100,00', '110,00'))
        self.assertEqual({r['id'] for r in first}, {r['id'] for r in second})

    def test_adapter_refresh_and_failure_preserves_output(self):
        response = Mock(url=SOURCE_URL, text=fixture())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            adapter = SantaCombaAyuntamientoAdapter('santa-comba')
            with patch('municipio.adapters.santa_comba.requests.get', return_value=response):
                report = adapter.update_proyectos(output, Path(directory) / 'state.json')
                self.assertEqual(report['count'], 1)
                original = output.read_text()
                self.assertEqual(json.loads(original)['tipo'], 'obra_publica')
                response.text = '<html>failure</html>'
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
                self.assertEqual(output.read_text(), original)
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('santa-comba')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Santa Comba', 'A Coruña', '15077'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
