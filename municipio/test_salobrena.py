"""Offline parser and adapter checks; run with python -m unittest municipio.test_salobrena."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from municipio.adapters.salobrena import (
    SOURCE, TITLE, SECTIONS, SalobrenaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def inventory(extra=''):
    groups = ''.join(
        f'<h4>{section}</h4><ul><li><a href="/web/wp-content/uploads/2013/04/{i}.{ext}">{label}</a></li></ul>'
        for i, (section, ext, label) in enumerate(zip(
            SECTIONS, ['zip', 'pdf', 'pdf', 'pdf'],
            ['Plan completo', 'Normas urbanísticas', 'Lobres', 'Lobres'])))
    return (f'<link rel="next" href="/otra-pagina/">'
            f'<div class="post"><h2>{TITLE}</h2><div class="entry">'
            f'{groups}{extra}</div></div><a href="/formulario.pdf">Licencia</a>')


class SalobrenaTests(unittest.TestCase):
    def test_groups_all_documents_without_inventing_metadata(self):
        extra = ''.join(f'<a href="/web/wp-content/uploads/2013/04/map{i}.pdf">Plano {i}</a>'
                        for i in range(30))
        rows = parse_inventory(inventory(extra))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 34)
        self.assertEqual(sum(d['titulo'] == 'Lobres' for d in row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '18173')
        for field in ['fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))

    def test_deduplicates_same_url_only(self):
        extra = '<a href="/web/wp-content/uploads/2013/04/3.pdf">Copia plano</a>'
        self.assertEqual(len(parse_inventory(inventory(extra))[0]['documentos']), 4)

    def test_rejects_empty_navigation_forms_and_missing_sections(self):
        for html in ['', '<a href="/pgou.pdf">Plan General</a>',
                     inventory().replace(TITLE, 'Solicitud de licencia'),
                     inventory().replace(f'<h4>{SECTIONS[2]}</h4>', '')]:
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_rejects_pagination_or_unexpected_document_links(self):
        for extra in ['<a rel="next" href="?page=2">Más</a>',
                      '<div class="pagination">2</div>',
                      '<a href="https://example.org/other.pdf">Otra fuente</a>',
                      '<a href="/formulario/">Formulario</a>']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(inventory(extra))

    def test_manifest_load_and_live_method_writes_parsed_snapshot(self):
        manifest = load_manifest('salobrena')
        self.assertEqual(manifest.provincia, 'Granada')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        response = Mock(url=SOURCE, text=inventory(), content=inventory().encode(),
                        headers={'Content-Type': 'text/html; charset=UTF-8'})
        with tempfile.TemporaryDirectory() as temp, patch(
                'municipio.adapters.salobrena.requests.get', return_value=response):
            out = Path(temp) / 'proyectos.jsonl'
            adapter.backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]['documentos']), 4)
            original = out.read_text()
            response.raise_for_status.side_effect = requests.HTTPError('403')
            with self.assertRaises(requests.HTTPError):
                adapter.update_proyectos(out, Path(temp) / 'state.json')
            self.assertEqual(out.read_text(), original)
        with self.assertRaises(NotImplementedError):
            SalobrenaAyuntamientoAdapter('salobrena').backfill_licencias(Path('unused'))


if __name__ == '__main__':
    unittest.main()
