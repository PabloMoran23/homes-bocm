"""Offline parser contract tests for the provincial O Pino works inventory."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from municipio.adapters.o_pino import OPinoAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def pack(value):
    if isinstance(value, dict):
        return [0, {k: pack(v) for k, v in value.items()}]
    if isinstance(value, list):
        return [1, [pack(v) for v in value]]
    return [0, value]


def fixture(*, duplicate=False, conflict=False, dir3='L01150660'):
    works = [{'denominacion': 'Senda peonil de proba', 'presupuesto': '1234.56',
              'importeAprobado': '1000.00'}]
    if duplicate:
        works.append(dict(works[0]))
    if conflict:
        works.append({**works[0], 'presupuesto': '1300.00'})
    props = json.dumps({'municipio': pack({'dir3': dir3, 'nombreOficial': 'O Pino',
                        'ejercicios': {'2026': {'obras': works},
                                       'todos': {'totalAprobado': '1000.00'}}})}, ensure_ascii=False)
    table = ''.join('<tr><td>2026</td><td>Senda peonil de proba</td><td>' +
                    ('1.300,00 €' if w['presupuesto'] == '1300.00' else '1.234,56 €') +
                    '</td><td>1.000,00 €</td></tr>' for w in works)
    return ('<h1>PLAN ÚNICO <strong>O Pino</strong></h1>'
            '<select id="selector-exercicio"><option value="todos">Todos</option>'
            '<option value="2026">2026</option></select>'
            f"<astro-island component-url='/CmpObrasEjercicio.js' props='{props}'></astro-island>"
            '<table aria-label="Lista de obras e investimentos"><tbody>' + table + '</tbody></table>')


class OPinoTests(unittest.TestCase):
    def test_semantics_and_provenance(self):
        row, = parse_inventory(fixture())
        self.assertEqual(row['presupuesto_eur'], '1234.56')
        self.assertEqual(row['aportacion_deputacion_eur'], '1000.00')
        self.assertEqual(row['codigo_ine'], '15066')
        self.assertEqual(row['ejercicio'], 2026)
        self.assertEqual(row['source'], 'diputacion')
        self.assertEqual(len(row['documentos']), 1)
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon'):
            self.assertNotIn(field, row)
        self.assertFalse(row['publication_ready'])

    def test_duplicates_and_conflicts(self):
        self.assertEqual(parse_inventory(fixture()), parse_inventory(fixture(duplicate=True)))
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            parse_inventory(fixture(conflict=True))

    def test_reject_wrong_municipality(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            parse_inventory(fixture(dir3='L01150000'))

    def test_reject_truncation_or_changed_amount(self):
        for html in (fixture().replace('<tr>', '<!--').replace('</tr>', '-->'),
                     fixture().replace('1.234,56 €', '1.234,57 €'),
                     fixture().replace('value="2026"', 'value="2025"')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_reject_pagination_and_missing_data(self):
        for html in (fixture() + '<a rel="next" href="/o-pino/?page=2">2</a>',
                     fixture() + '<a href="/o-pino/page/2">Seguinte</a>',
                     '<h1>PLAN ÚNICO O Pino</h1>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('o-pino')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, OPinoAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
