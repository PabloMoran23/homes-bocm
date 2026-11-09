import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.artes import ArtesAyuntamientoAdapter, INVENTORY, POUM, DOCUMENTS
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml

INVENTORY_HTML = '''<h1>Projectes i estudis urbanístics</h1>
<div class="journal-content-article"><ul>
<li><a href="/documents/949642/1/rotonda.pdf/abc">Projecte de disseny de rotonda</a>
<a href="/documents/949642/1/annex.pdf/def">Annex</a></li>
<li><a href="/documents/949642/2/riera.pdf/ghi">Estudi de la riera</a></li>
</ul><div>Actualització: 13/10/2025 | Font: Propi ens</div></div>
<a href="/tramits/llicencia">Formulari de llicència</a>'''
POUM_HTML = '''<article><div class="field-name-body"><p>L’Ajuntament va aprovar pel Ple en data 21 de març de 2024 el document per a l'aprovació inicial del POUM.</p>
<a href="/sites/default/files/documents/Publicacio_DOGC_AI.pdf">DOGC</a></div></article>'''
DOC_HTML = '''<h1>Documentació del POUM aprovat inicialment</h1><article><div class="field-name-body">
<a href="https://ajartes-my.sharepoint.com/:b:/g/memoria?e=123">Memòria</a>
<a href="https://ajartes-my.sharepoint.com/:b:/g/normes?e=456">Normativa</a>
<a href="https://ajartes-my.sharepoint.com/:f:/g/planols">Plànols</a></div></article>'''


class ArtesTests(unittest.TestCase):
    def test_inventory_grouping_and_date_semantics(self):
        rows = ArtesAyuntamientoAdapter.parse_inventory(INVENTORY_HTML)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['fecha_actualizacion_fuente'], '2025-10-13')
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['lon'])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '08010')
        self.assertEqual(rows[0]['id'], ArtesAyuntamientoAdapter.parse_inventory(INVENTORY_HTML)[0]['id'])

    def test_poum_groups_documents_and_separates_dates(self):
        row = ArtesAyuntamientoAdapter.parse_poum(POUM_HTML, DOC_HTML)
        self.assertEqual(row['fecha_acuerdo'], '2024-03-21')
        self.assertEqual(row['fecha_aprob'], '2024-03-21')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual({d['source_url'] for d in row['documentos']}, {POUM, DOCUMENTS})

    def test_rejects_empty_navigation_forms_or_changed_content(self):
        for html in ['<h1>Login</h1>', '<h1>Projectes i estudis urbanístics</h1><a href="/form.pdf">Llicència</a>']:
            with self.assertRaises(ValueError):
                ArtesAyuntamientoAdapter.parse_inventory(html)
        with self.assertRaises(ValueError):
            ArtesAyuntamientoAdapter.parse_poum(POUM_HTML.replace('21 de març de 2024', 'data desconeguda'), DOC_HTML)
        with self.assertRaises(ValueError):
            ArtesAyuntamientoAdapter.parse_poum(POUM_HTML, '<article>Documentació</article>')

    def test_pagination_is_not_silently_truncated(self):
        for link in ['<a rel="next" href="?p=2">2</a>', '<a href="?page=2">2</a>', '<a href="?p=2">Següent</a>']:
            with self.assertRaises(ValueError):
                ArtesAyuntamientoAdapter.parse_inventory(INVENTORY_HTML + link)

    def test_snapshot_update_and_failure_preserves_output(self):
        adapter = ArtesAyuntamientoAdapter()
        pages = {INVENTORY: INVENTORY_HTML, POUM: POUM_HTML, DOCUMENTS: DOC_HTML}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda url, name: pages[url]):
                result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 3)
            original = path.read_text()
            self.assertEqual(len([json.loads(line) for line in original.splitlines()]), 3)
            with patch.object(adapter, '_fetch', return_value='<h1>Login</h1>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), original)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('artes')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08010')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, ArtesAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
