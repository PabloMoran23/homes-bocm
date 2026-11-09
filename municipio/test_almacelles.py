import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.almacelles import AlmacellesAyuntamientoAdapter as Adapter, INVENTORY
from municipio.manifest import load_manifest, load_yaml


def inventory(items, next_link=''):
    return '<div id="content-core"><div class="entries">' + ''.join(
        f'<article class="entry"><div class="summary"><a href="{url}">{title}</a></div></article>'
        for url, title in items) + '</div>' + next_link + '</div>'


class AlmacellesTests(unittest.TestCase):
    def test_inventory_ignores_navigation(self):
        rows, pages = Adapter.parse_inventory(inventory([(INVENTORY + '/projectes-2024', 'Projectes 2024')]) +
            '<a href="https://example.org">Unrelated navigation</a>', INVENTORY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(pages, [])
        with self.assertRaises(ValueError):
            Adapter.parse_inventory('<html>Login</html>', INVENTORY)

    def test_full_pagination_grouping_and_date_semantics(self):
        archive = INVENTORY + '/projectes-2024'
        a, b = archive + '/project-a', archive + '/project-b'
        viewer = 'https://drive.google.com/file/d/real-document/view?usp=sharing'
        pages = {
            INVENTORY: (inventory([(archive, 'Projectes 2024')]), INVENTORY),
            archive: (inventory([(a, 'Projecte arranjament camins')], '<a rel="next" href="?b_start:int=1">Següent</a>'), archive),
            archive + '?b_start:int=1': (inventory([(b, 'Projecte arranjament camins annex')]), archive + '?b_start:int=1'),
            a: ('<meta property="og:title" content="20240603_PROJECTE.pdf">', viewer),
            b: ('<meta property="og:title" content="20240603_PROJECTE.pdf">', viewer),
        }
        adapter = Adapter('almacelles')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=lambda u: pages[u]):
            path = Path(directory) / 'projects.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['rows'], 1)
            row = json.loads(path.read_text())
            self.assertEqual(len(row['enlaces_municipales']), 2)
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
                self.assertIsNone(row[key])

    def test_closed_or_unexpected_document_rejected(self):
        viewer = 'https://drive.google.com/file/d/abc/view'
        with self.assertRaises(ValueError):
            Adapter.parse_document('<title>Login</title>', viewer)
        with self.assertRaises(ValueError):
            Adapter.parse_document('<meta property="og:title" content="project.pdf">', 'https://example.org/file')

    def test_new_archive_requires_review(self):
        adapter = Adapter('almacelles')
        with patch.object(adapter, '_inventory', return_value={INVENTORY + '/2025': 'Projectes 2025'}):
            with self.assertRaisesRegex(ValueError, 'archive changed'):
                adapter.backfill_proyectos(Path('/unused'))

    def test_manifest(self):
        manifest = load_manifest('almacelles')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Almacelles', 'Lleida', '25019'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
