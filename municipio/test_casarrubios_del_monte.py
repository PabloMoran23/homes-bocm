import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.casarrubios_del_monte import (
    SOURCE, CasarrubiosDelMonteAyuntamientoAdapter, parse_inventory,
)


def inventory(*links):
    return '<div class="wpr-accordion-item-wrap">' + ''.join(
        f'<a href="{url}">{title}</a>' for title, url in links) + '</div>'


BASE = 'https://casarrubiosdelmonte.es/documentos/'


class ParserTests(unittest.TestCase):
    def test_group_parts_keep_modification_separate(self):
        html = inventory(
            ('Parte 1', BASE + 'urbanismo/plan_parcial_pol_industrial_monte_boyal_-_parte_1.pdf'),
            ('Parte 2', BASE + 'urbanismo/plan_parcial_pol_industrial_monte_boyal_-_parte_2.pdf'),
            ('Parte 1', BASE + 'urbanismo/plan_parcial_pol_industrial_monte_boyal_-_parte_1.pdf'),
            ('MODIFICACIÓN ART.63 PLAN PARCIAL POLÍGONO MONTE BOYAL', BASE + 'monteboyal/APROBACION-MODIFICACION-ART-63-PLAN-PARCIAL-MONTE-BOYAL.pdf'),
        )
        rows = parse_inventory(html)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[1]['tipo'], 'modificacion_planeamiento')
        for row in rows:
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertNotIn('lat', row)
            self.assertNotIn('fase', row)

    def test_excludes_forms_external_links_ordinances_and_anonymous_maps(self):
        rows = parse_inventory(inventory(
            ('NNSS', BASE + 'urbanismo/normas_subsidiarias_de_planeamiento._normativa.pdf'),
            ('Solicitud de licencia', BASE + 'urbanismo/solicitud.pdf'),
            ('Plan parcial', 'https://example.org/urbanismo/monte-boyal.pdf'),
            ('Ordenanza', BASE + 'urbanismo/ordenanza_municipal_edificacion.pdf'),
            ('P01', BASE + 'urbanismo/p01_-_clasificacion_del_suelo_urbano.pdf'),
        ))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)

    def test_named_plans_and_associated_maps(self):
        rows = parse_inventory(inventory(
            ('Plan Parcial Urbanización Calypo Fado', BASE + 'urbanismo/Plan%20Parcial%20Urb%20Calypo%20Fado.PDF'),
            ('P02', BASE + 'urbanismo/P02%20-%20Fado-Calypo.pdf'),
            ('Plan parcial Los Guindales', BASE + 'urbanismo/los_guindales_p-2.9.pdf'),
            ('024', BASE + 'urbanismo/024.pdf'),
            ('026', BASE + 'urbanismo/026.pdf'),
        ))
        self.assertEqual([len(r['documentos']) for r in rows], [2, 3])
        self.assertEqual(rows[0]['codigo_ine'], '45041')

    def test_empty_changed_layout_and_pagination_fail(self):
        for html in ['', '<h1>Login</h1>', inventory(), inventory(('Siguiente', '?paged=2'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_backfill_and_update_use_live_response(self):
        html = inventory(('Plan Calypo', BASE + 'urbanismo/Plan%20Parcial%20Urb%20Calypo%20Fado.PDF'))
        response = Mock(text=html, url=SOURCE)
        adapter = CasarrubiosDelMonteAyuntamientoAdapter('casarrubios-del-monte')
        with tempfile.TemporaryDirectory() as directory, patch(
                'municipio.adapters.casarrubios_del_monte.requests.get', return_value=response) as get:
            output = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(output)['count'], 1)
            before = output.read_text()
            adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(output.read_text(), before)
            self.assertEqual(get.call_count, 2)
            self.assertEqual(adapter.backfill_licencias(output)['count'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
