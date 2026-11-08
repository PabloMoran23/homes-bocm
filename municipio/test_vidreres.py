import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.vidreres import SOURCE, VidreresAyuntamientoAdapter
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter
from municipio.entity_policy import classify


def inventory(extra='', pgou_extra=''):
    return '''<article id="the-post"><h1>Pgou</h1>
    <div class="single-post-meta"><span class="date">7 de juliol de 2021</span></div>
    <div class="entry-content"><h3>Documents PGOU</h3>
    <p><a href="/wp-content/uploads/2021/01/normes.pdf">1 Normativa PGOU 2003</a></p>
    <p><a href="/wp-content/uploads/2021/01/mapa.pdf">2 Plànol PGOU</a></p>''' + pgou_extra + '''
    <h3>Modificacions PGOU</h3><p><a href="https://drive.google.com/file/d/shared/view?usp=sharing">MP PGOU sus 2</a></p>
    <p><a href="https://drive.google.com/file/d/shared/view?usp=sharing">MP PGOU </a><a href="https://drive.google.com/file/d/sus8/view?usp=sharing">sus</a><a href="https://drive.google.com/file/d/shared/view?usp=sharing"> 8</a></p>
    <h3>Plans especials</h3><p><a href="/wp-content/uploads/2021/01/peu.pdf">PEU catàleg de masies</a></p>
    <h3>Altres</h3><p><a href="/wp-content/uploads/2021/01/tuc.pdf">Plànol delimitació Vidreres</a></p>
    <p><a href="/wp-content/uploads/2021/01/ppu.pdf">PPU sus 4</a></p>''' + extra + '</div></article>'


class VidreresTests(unittest.TestCase):
    def test_grouping_provenance_and_dates(self):
        rows = VidreresAyuntamientoAdapter.parse_projects(inventory())
        self.assertEqual(len(rows), 5)
        pgou = rows[0]
        self.assertEqual(len(pgou['documentos']), 2)
        self.assertEqual(pgou['source_page_fecha_publicacion'], '2021-07-07')
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fase'])
            self.assertIsNone(row['geometry'])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '17213')
            self.assertEqual(classify(row)['entity_type'], 'documento')
            self.assertFalse(classify(row)['activity_eligible'])
        sus8 = next(r for r in rows if r['titulo'] == 'MP PGOU sus 8')
        self.assertEqual(len({d['url'] for d in sus8['documentos']}), 2)
        self.assertTrue(sus8['shared_document_urls'])
        self.assertEqual(sus8['documentos'][0]['source_url'], SOURCE)
        self.assertEqual(pgou['excluded_inventory_entries'], ['Plànol delimitació Vidreres'])

    def test_identity_does_not_depend_on_document_order(self):
        first = VidreresAyuntamientoAdapter.parse_projects(inventory())[0]
        second = VidreresAyuntamientoAdapter.parse_projects(inventory(pgou_extra='<p><a href="/wp-content/uploads/2026/01/new.pdf">3 Plànol nou</a></p>'))[0]
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(second['documentos']), 3)

    def test_reject_navigation_forms_and_changed_content(self):
        for html in ['<a href="/pgou/">Pgou</a>', '<h1>Login</h1>',
                     inventory('<p><a href="/form.pdf">Sol·licitud llicència</a></p>'),
                     inventory().replace('Plans especials', 'Llicències'),
                     inventory().replace('/wp-content/uploads/2021/01/peu.pdf', 'https://example.org/peu.pdf')]:
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                VidreresAyuntamientoAdapter.parse_projects(html)

    def test_pagination_is_not_silently_ignored(self):
        for link in ['<a rel="next" href="/pgou/2/">2</a>',
                     '<a href="?paged=2">2</a>', '<a href="/pgou/page/2/">Més</a>']:
            with self.subTest(link=link), self.assertRaises(ValueError):
                VidreresAyuntamientoAdapter.parse_projects(inventory(link))

    def test_manifest_and_adapter_contract(self):
        manifest = load_manifest('vidreres')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Vidreres', 'Girona', '17213'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            rows = VidreresAyuntamientoAdapter.parse_projects(inventory())
            with patch.object(adapter, 'backfill_proyectos', wraps=lambda p: (adapter._write(p, rows) or {'rows': len(rows)})):
                result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 5)
            self.assertEqual(len([json.loads(s) for s in path.read_text().splitlines()]), 5)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
