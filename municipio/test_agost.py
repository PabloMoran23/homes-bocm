import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.agost import AgostAyuntamientoAdapter, SOURCE_URL, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def section(title, body):
    return ('<div class="gb-accordion__item"><button class="gb-accordion__toggle">'
            f'<span class="gb-button-text">{title}</span></button>'
            f'<div class="gb-accordion__content">{body}</div></div>')


def page(*sections):
    return '<div class="entry-content"><h2>PLANEAMIENTO MUNICIPAL</h2>' + ''.join(sections) + '</div>'


def link(label, name):
    return f'<a href="/documentos/{name}.pdf">{label}</a>'


class AgostParserTests(unittest.TestCase):
    def test_grouping_and_source_semantics(self):
        html = page(
            section('Revisión Normas Subsidiarias de Agost 1995',
                    link('Memoria', 'memoria') + link('Plano', 'plano')),
            section('Modificaciones puntuales', '<ul><li>' + link('Modificación puntual nª17', '17')
                    + '</li><li>' + link('Modificación puntual nª17 Anexo Mapas', 'mapas') + '</li></ul>'),
            section('Planeamiento en tramitación', '<ul><li>Modificación puntual nº24<ul><li>'
                    + link('Plano 01', '24') + '</li><li>03_usos del Suelo</li></ul></li></ul>'),
            section('Ordenanzas', link('Ordenanza', 'ordenanza')))
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1])
        self.assertEqual(rows[2]['fase'], 'en tramitación')
        self.assertEqual(rows[2]['documentos_sin_enlace'], ['03_usos del Suelo'])
        self.assertNotIn('fase', rows[0])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '03002')
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['geometry_status'], 'unavailable')
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon'):
                self.assertNotIn(field, row)
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in parse_inventory(html)])

    def test_sector_documents_do_not_leak_and_split_links_deduplicate(self):
        html = page(section('Planeamiento diferido', '<ul><li>SAU/I.1. LA ESCANDELLA<ul><li>parcial<ul><li>'
                    + link('Unidades', 'p04') + link('de ejecución', 'p04')
                    + '</li></ul></li></ul></li><li>SAU/I.2. ELS CASTELLANS<ul><li>'
                    + link('Memoria', 'castellans') + '</li></ul></li></ul>'))
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(rows[0]['documentos'][0]['titulo'], 'Unidades de ejecución')
        self.assertTrue(rows[1]['documentos'][0]['url'].endswith('castellans.pdf'))

    def test_missing_changed_paginated_or_unsafe_sources_fail(self):
        good = section('Revisión Normas Subsidiarias de Agost 1995', link('Memoria', 'memoria'))
        cases = ['', page(), page(section('Proyecto nuevo', link('Proyecto', 'new'))),
                 page(section('Planeamiento en tramitación', '<ul><li>Catálogo de Protecciones</li></ul>')),
                 page(good) + '<a rel="next" href="?page=2">2</a>',
                 page(good.replace('/documentos/memoria.pdf', 'https://example.org/a.pdf'))]
        for html in cases:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_adapter_snapshot_and_failure_preserves_previous_output(self):
        adapter = AgostAyuntamientoAdapter('agost')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch('municipio.adapters.agost.requests.get') as get:
                response = get.return_value
                response.url = SOURCE_URL
                response.text = page(section('Revisión Normas Subsidiarias de Agost 1995', link('Memoria', 'memoria')))
                self.assertEqual(adapter.update_proyectos(output, Path(directory) / 'state.json')['count'], 1)
                previous = output.read_text()
                self.assertEqual(json.loads(previous)['municipio'], 'Agost')
                response.text = '<html>Unavailable</html>'
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
                self.assertEqual(output.read_text(), previous)

    def test_manifest(self):
        manifest = load_manifest('agost')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Agost', 'Alicante', '03002'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
