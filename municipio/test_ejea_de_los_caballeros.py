"""Offline semantic fixtures and mocked adapter contract checks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.ejea_de_los_caballeros import (
    EjeaDeLosCaballerosAyuntamientoAdapter, SOURCE_URL, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def link(title, filename):
    return f'<li><a href="https://st1.ejea.es/media/2026/06/{filename}.pdf">{title}</a></li>'


FIXTURE = (
    '<div><h2>Planeamiento</h2><h3>Plan general</h3><h4>Memoria</h4><ul>'
    + link('Memoria', 'memoria') + link('Estudio económico', 'estudio')
    + '</ul><h4>Modificaciones PGOU</h4><ul>'
    + link('Modificación PGOU 1 2007 Parte 1', 'mod-1')
    + link('Modificación PGOU 1 2007 Parte 2', 'mod-2')
    + link('Modificación PGOU 2 2007', 'mod-otro')
    + '</ul><h3>Planes parciales</h3><ul>'
    + link('Plan Parcial Sector 1 Luchan', 'luchan')
    + '</ul><h3>Planes especiales</h3><ul>'
    + link('Plan Especial Boalares El Gancho', 'boalares')
    + '</ul><h2>Topografía</h2><ul>' + link('Coordenadas', 'coords')
    + '</ul><h2>Solicitudes</h2><ul>' + link('Impreso Licencia Obras Mayores', 'impreso')
    + '</ul><h2>Noticias</h2>Una noticia ajena</div>'
)


class PlanningTests(unittest.TestCase):
    def test_grouping_scope_provenance_and_no_inferred_metadata(self):
        rows = parse_inventory(FIXTURE)
        self.assertEqual(len(rows), 5)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1, 1, 1])
        self.assertEqual(rows[1]['titulo'], 'Modificación PGOU 1 2007')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '50095')
            self.assertFalse(set(row) & {'fecha', 'fecha_aprob', 'fecha_acuerdo',
                                          'fecha_publicacion', 'lat', 'lon', 'fase'})
            for doc in row['documentos']:
                self.assertEqual(doc['source_url'], SOURCE_URL)
                self.assertNotIn(doc['titulo'], {'Coordenadas', 'Impreso Licencia Obras Mayores'})

    def test_duplicate_documents_and_stable_ids(self):
        original = parse_inventory(FIXTURE)
        duplicate = parse_inventory(FIXTURE.replace(link('Memoria', 'memoria'),
                                                     link('Memoria', 'memoria') * 2))
        self.assertEqual(original, duplicate)
        revised = parse_inventory(FIXTURE.replace('/2026/06/', '/2027/01/'))
        self.assertEqual([r['id'] for r in original], [r['id'] for r in revised])

    def test_empty_changed_and_paginated_fail(self):
        for html in ['', '<h2>Planeamiento</h2>',
                     FIXTURE.replace('Planes especiales', 'Otros instrumentos'),
                     FIXTURE.replace('https://st1.ejea.es', 'https://example.org'),
                     FIXTURE + '<a rel="next" href="?page=2">Más</a>',
                     FIXTURE.replace('<h2>Topografía</h2>',
                                     '<button class="load-more">Más</button><h2>Topografía</h2>')]:
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_adapter_and_refresh(self):
        manifest = load_manifest('ejea-de-los-caballeros')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('50095', 'Zaragoza'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), EjeaDeLosCaballerosAyuntamientoAdapter)
        response = Mock(text=FIXTURE, url=SOURCE_URL)
        adapter = EjeaDeLosCaballerosAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as directory, patch(
                'municipio.adapters.ejea_de_los_caballeros.requests.get', return_value=response):
            output = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(output, Path(directory) / 'state')['written'], 5)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 5)
            output.write_text('previous successful extraction')
            response.text = '<html>Broken source</html>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous successful extraction')
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
