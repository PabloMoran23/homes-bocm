import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.zas import SOURCE, ZasAyuntamientoAdapter
from municipio.manifest import load_manifest, load_yaml


def inventory(titles=("Mellora capa rodaxe de Sobreira-O Sisto",), count=None):
    rows = "".join(f'<tr><td>2025</td><td>{title}</td><td>47.809,08 €</td>'
                   '<td>47.809,08 €</td></tr>' for title in titles)
    return ('<h1>PLAN <span>ÚNICO </span><strong>Zas</strong></h1>'
            f'<ul><li><div><span>Obras aprobadas</span></div><div>{len(titles) if count is None else count}</div></li></ul>'
            '<table aria-label="Lista de obras e investimentos"><thead><tr>'
            '<th>Exercicio</th><th>Obxecto</th><th>Orzamento</th><th>Aportación</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>')


class ZasTests(unittest.TestCase):
    def test_real_work_semantics_and_stable_identity(self):
        rows, report = ZasAyuntamientoAdapter.parse_inventory(inventory())
        self.assertEqual(report['inventory_rows'], 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '15093')
        self.assertEqual(row['presupuesto_eur'], 47809.08)
        self.assertEqual(row['ejercicio'], 2025)
        for field in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertEqual(row['url'], SOURCE)
        other, _ = ZasAyuntamientoAdapter.parse_inventory(inventory((
            'Rehabilitación enerxética da Escola Infantil de Zas', row['titulo'])))
        self.assertEqual(row['id'], other[1]['id'])

    def test_supply_is_not_a_work(self):
        rows, report = ZasAyuntamientoAdapter.parse_inventory(inventory((
            'Subministración dunha miniexcavadora con brazo hidraúlico',
            'Rede de saneamento de Rial de Abaixo')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(report['excluded'][0]['reason'], 'equipment_supply')

    def test_document_links_grouped_without_additional_records(self):
        html = inventory(('<a href="/project.pdf">Rede de saneamento</a> '
                          '<a href="/agreement.pdf">Acordo</a>',))
        rows, _ = ZasAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual([d['url'] for d in rows[0]['documentos']],
                         ['https://plan-unico.dacoruna.gal/project.pdf',
                          'https://plan-unico.dacoruna.gal/agreement.pdf'])

    def test_incomplete_inventory_and_pagination_fail(self):
        for html in (inventory(count=2), inventory() + '<a rel="next" href="?page=2">2</a>',
                     inventory() + '<button>Cargar máis</button>',
                     inventory().replace('Zas', 'Outro concello')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                ZasAyuntamientoAdapter.parse_inventory(html)

    def test_changed_or_unrelated_rows_fail(self):
        for html in (inventory(('Modelo de solicitude de licenza',)),
                     inventory(('Anuncio de licitación',)),
                     inventory().replace('47.809,08', 'unknown'),
                     inventory(('Rede de saneamento', 'Rede de saneamento')),
                     inventory(())):
            with self.subTest(html=html), self.assertRaises(ValueError):
                ZasAyuntamientoAdapter.parse_inventory(html)

    def test_refresh_and_failure_preserve_previous_output(self):
        adapter = ZasAyuntamientoAdapter('zas')
        with tempfile.TemporaryDirectory() as tmp:
            out, state = Path(tmp) / 'works.jsonl', Path(tmp) / 'state.json'
            with patch('municipio.adapters.zas.requests.get', return_value=Mock(text=inventory())):
                result = adapter.update_proyectos(out, state)
            self.assertEqual(result['rows'], 1)
            original = out.read_text()
            self.assertEqual(json.loads(original)['municipio'], 'Zas')
            self.assertFalse(state.exists())
            with patch('municipio.adapters.zas.requests.get', return_value=Mock(text=inventory(count=3))):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), original)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('zas')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Zas', 'A Coruña', '15093'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
