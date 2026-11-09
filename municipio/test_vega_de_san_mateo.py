import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.vega_de_san_mateo import (
    SOURCE, VegaDeSanMateoAyuntamientoAdapter, parse_inventory,
)


def table(title, name, path):
    return f'<table><tr><th colspan="3">{title}</th></tr><tr><td>{name}</td><td>10 Kb</td><td><a href="{path}">Descargar Pdf.</a></td></tr></table>'


def inventory():
    return '<article><div class="field--name-body">' + ''.join([
        table('TEXTO REFUNDIDO DE LA ADAPTACIÓN BÁSICA DEL P.G.O.', 'MEMORIA', '/ficheros_pdf/urb/01memoria.pdf'),
        table('1000-SUELOS URBANOS', '10E-PLAN ESPECIAL DE PROTECCIÓN Y REFORMA INTERIOR', '/ficheros_pdf/urb/1000/10.pdf'),
        table('PLAN PARCIAL HOYA VICIOSA', 'Memoria', '/ficheros_pdf/urb/hv/m.pdf'),
        table('PLANOS DE ORDENACIÓN', 'Plan de Etapas', '/ficheros_pdf/urb/hv/19.pdf'),
        table('PLAN PARCIAL LA VEGUETA', 'Memoria', '/ficheros_pdf/urb/v/m.pdf'),
        table('PLANOS DE INFORMACIÓN', 'Catastral', '/ficheros_pdf/urb/v/i3.pdf'),
    ]) + '</div></article>'


class PlanningTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 2])
        self.assertIn('/hv/19.pdf', rows[1]['documentos'][1]['url'])
        self.assertIn('/v/i3.pdf', rows[2]['documentos'][1]['url'])
        self.assertEqual(rows[2]['documentos'][1]['source_url'], SOURCE)
        self.assertEqual(rows, parse_inventory(inventory()))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '35033')
            self.assertFalse(row['publication_ready'])
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertNotIn(field, row)

    def test_fail_on_empty_unknown_or_paginated(self):
        for html in ('', '<article><div class="field--name-body"></div></article>',
                     inventory().replace('PLANOS DE INFORMACIÓN', 'OTRO PLAN'),
                     inventory() + '<nav class="pager"><a href="?page=1">2</a></nav>',
                     inventory().replace('</div>', '<a href="?page=1">Siguiente</a></div>'),
                     inventory().replace('/ficheros_pdf/urb/v/i3.pdf', 'https://example.org/a.pdf')):
            with self.subTest(html=html[-100:]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_duplicate_documents_and_unrelated_form(self):
        html = inventory().replace('</div>', '<a href="/licencias.pdf">Solicitud licencia</a></div>')
        rows = parse_inventory(html)
        self.assertEqual(sum(len(r['documentos']) for r in rows), 6)
        duplicated = inventory().replace('</div>', table('PLANOS DE INFORMACIÓN', 'Catastral', '/ficheros_pdf/urb/v/i3.pdf') + '</div>')
        self.assertEqual(parse_inventory(duplicated), rows)

    def test_backfill_and_update_and_failure_preserves_output(self):
        adapter = VegaDeSanMateoAyuntamientoAdapter('vega-de-san-mateo')
        response = Mock(url=SOURCE, text=inventory())
        with TemporaryDirectory() as directory, patch('municipio.adapters.vega_de_san_mateo.requests.get', return_value=response):
            out = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(out)['count'], 3)
            original = out.read_text()
            self.assertEqual(adapter.update_proyectos(out, Path(directory) / 'state.json')['count'], 3)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 3)
            response.text = ''
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), original)
            self.assertTrue(adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')['disabled'])


if __name__ == '__main__':
    unittest.main()
