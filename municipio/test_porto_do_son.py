import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.porto_do_son import (
    INVENTORY, PortoDoSonAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(*paths, next_page=''):
    cards = ''.join(f'<div class="item category-proxectos"><h2><a href="/{p}/">Project</a></h2></div>' for p in paths)
    return cards + (f'<a rel="next" href="{next_page}">Next</a>' if next_page else '')


def detail(title='Humanización do núcleo do Cruceiro', narrative='Parroquia de Xuño, orzamento de 77.715,25 euros', docs=('plan.pdf',)):
    links = ''.join(f'<a href="/wp-content/uploads/{p}">{p}</a><a href="/wp-content/uploads/{p}">Descarga</a>' for p in docs)
    return f'''<h1 class="entry-title">{title}</h1><p class="meta"><span class="post-date">Xaneiro 16, 2025 |</span></p>
    <div class="entry" itemprop="text"><p>{narrative}</p>{links}</div>
    <aside><a href="/unrelated.pdf">Other plan</a></aside>'''


class ParserTests(unittest.TestCase):
    def test_group_documents_and_distinguish_dates(self):
        row = parse_project(detail('Aprobación definitiva PEID construción de equipamento educativo en Portosín',
            'O Plan especial foi aprobado definitivamente polo Pleno municipal, en sesión extraordinaria o 14 de xaneiro de 2025.',
            ('plan.pdf', 'certificate.pdf')), 'https://portodoson.gal/peid/')
        self.assertEqual(row['fecha_publicacion'], '2025-01-16')
        self.assertEqual(row['fecha_aprob'], '2025-01-14')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['titulo'], 'plan.pdf')
        self.assertFalse(row['publication_ready'])
        self.assertNotIn('lat', row)

    def test_works_do_not_inherit_approval(self):
        row = parse_project(detail(), 'https://portodoson.gal/cruceiro/')
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('fase', row)
        self.assertEqual(len(row['documentos']), 1)
        other = parse_project(detail(docs=('silva.pdf',)), 'https://portodoson.gal/silva/')
        self.assertNotEqual(row['id'], other['id'])
        self.assertNotEqual(row['documentos'], other['documentos'])

    def test_reject_non_projects_and_changed_sources(self):
        for title in ['Solicitude de obra maior', 'Anuncio de licitación', 'Festa da auga', 'Adquisición do inmoble situado na Rúa Outeiro Alto']:
            self.assertIsNone(parse_project(detail(title), 'https://portodoson.gal/test/'))
        for html in ['', detail(docs=()), detail().replace('Xaneiro', 'Unknown')]:
            with self.assertRaises(ValueError):
                parse_project(html, 'https://portodoson.gal/test/')
        with self.assertRaises(ValueError):
            parse_inventory('<a href="/project/">Project</a>')
        with self.assertRaises(ValueError):
            parse_inventory(inventory('work', next_page='https://external.example/page/2/'))

    def test_all_pages_and_update_snapshot(self):
        second = INVENTORY + 'page/2/'
        sources = {INVENTORY: inventory('cruceiro', next_page=second),
                   second: inventory('silva', next_page=INVENTORY),
                   'https://portodoson.gal/cruceiro/': detail(),
                   'https://portodoson.gal/silva/': detail('Humanización do núcleo da Silva', docs=('silva.pdf',))}
        adapter = PortoDoSonAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=sources.__getitem__):
            out = Path(folder) / 'projects.jsonl'
            result = adapter.update_proyectos(out, Path(folder) / 'state.json')
            self.assertEqual(result['count'], 2)
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)

    def test_pagination_failure_preserves_previous_output(self):
        second = INVENTORY + 'page/2/'
        adapter = PortoDoSonAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'projects.jsonl'
            out.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', return_value=inventory('work', next_page=second)):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest(self):
        manifest = load_manifest('porto-do-son')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '15071')
        self.assertEqual(manifest.provincia, 'A Coruña')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
