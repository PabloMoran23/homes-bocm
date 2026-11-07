import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path

from municipio.adapters.soller import SollerAyuntamientoAdapter as Adapter, FOLDERS, SOURCE


def inventory():
    return '<main><h1>Normativa - Urbanismo</h1>' + ''.join(
        f'<a href="/ca/arxius-i-documents/urbanisme/{key}">{title} 2 documents</a>'
        for key, (title, _) in FOLDERS.items()) + '</main>'


def folder(key):
    return f'<main><h1>01 {FOLDERS[key][0]}</h1>' + ''.join(
        f'<div><h3>{title}</h3><span>19/11/2019</span><a href="/sites/cilma_soller/files/{i}.pdf">Descarregar</a></div>'
        for i, title in enumerate(['Aprovació def. PGOU', 'Plànols'])) + '</main>'


class SollerTests(unittest.TestCase):
    def test_group_and_date_semantics(self):
        key = next(iter(FOLDERS))
        row = Adapter.parse_folder(folder(key), key, SOURCE + '/' + key, 2)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['fecha_listado_archivo'], '2019-11-19')
        for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase']:
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_missing_or_changed_content(self):
        for html in ['<html>Login</html>', '<main><h1>Normativa</h1><a>Formulario licencia</a></main>', inventory().replace('2 documents', '')]:
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_pagination_rejected(self):
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(inventory() + '<a rel="next" href="?page=1">Next</a>')

    def test_count_and_origin(self):
        key = next(iter(FOLDERS))
        for html, count in [(folder(key), 3), (folder(key).replace('href="/sites', 'href="https://evil.example/sites'), 2)]:
            with self.assertRaises(ValueError):
                Adapter.parse_folder(html, key, SOURCE, count)

    def test_full_snapshot_and_disabled_licences(self):
        adapter = Adapter()
        pages = {SOURCE: inventory()}
        pages.update({url: folder(key) for key, (url, _) in Adapter.parse_inventory(inventory()).items()})
        with TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            out = Path(tmp) / 'projects.jsonl'
            self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state.json')['rows'], 3)
            first = out.read_text()
            adapter.backfill_proyectos(out)
            self.assertEqual(first, out.read_text())
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
