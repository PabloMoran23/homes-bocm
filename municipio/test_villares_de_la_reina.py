import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.villares_de_la_reina import (
    METADATA, PHASES, SOURCE, VillaresDeLaReinaAyuntamientoAdapter, parse_projects,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory(extra='', title='Obra de pavimentación'):
    return '<div id="main-content"><article><div class="entry-content"><h1>Proyectos</h1><p>los siguientes proyectos:</p>' + ''.join(
        f'<h3>{phase}</h3><ul><li>{title} {i}{extra}</li></ul>' for i, phase in enumerate(PHASES)
    ) + '</div></article></div>'


class VillaresTests(unittest.TestCase):
    def test_phases_identity_links_and_no_invented_dates(self):
        rows = parse_projects(inventory('<a href="/obra.pdf">Memoria</a><a href="/plano.pdf">Plano</a>'))
        self.assertEqual(len(rows), 4)
        self.assertEqual([r['fase_fuente'] for r in rows], list(PHASES))
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][0]['url'], 'https://villaresdelareina.es/obra.pdf')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '37362')
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])

    def test_reject_missing_unknown_or_paginated_content(self):
        for html in ('<h1>Login</h1>', inventory().replace('Fase de obras', 'Otra fase'),
                     inventory() + '<a rel="next" href="/page/2">Más</a>',
                     inventory().replace('<li>Obra de pavimentación 0</li>', '')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_stable_ids_and_duplicate_document_grouping(self):
        html = inventory()
        first = parse_projects(html)[0]
        duplicate = html.replace('</ul>', '<li>Obra de pavimentación 0</li></ul>', 1)
        self.assertEqual(len(parse_projects(duplicate)), 4)
        self.assertEqual(first['id'], parse_projects(html.replace('Fase de obras', 'Fase de obras '))[0]['id'])

    def test_adapter_metadata_update_and_manifest(self):
        manifest = load_manifest('villares-de-la-reina')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '37362')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        meta = json.dumps({'id': 3367, 'status': 'publish', 'link': SOURCE,
                           'date': '2021-02-22T08:26:15', 'modified': '2021-10-28T13:04:47'}).encode()
        with tempfile.TemporaryDirectory() as d, patch.object(adapter, '_fetch', side_effect=[inventory().encode(), meta]):
            target = Path(d) / 'projects.jsonl'
            result = adapter.update_proyectos(target, Path(d) / 'state.json')
            rows = [json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual(result['rows'], 4)
            self.assertEqual(rows[0]['source_page_modificada'], '2021-10-28T13:04:47')
            self.assertIsNone(rows[0]['fecha_aprob'])
            self.assertEqual(rows[0]['source_metadata_url'], METADATA)
            self.assertEqual(adapter.backfill_licencias(Path(d) / 'lic.jsonl')['rows'], 0)


if __name__ == '__main__':
    unittest.main()
