"""Offline parser and snapshot safeguards; no network or evidence dependency."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.villacanas import (
    BASE, DOCS, MAPS, TEXTS, SOURCE, VillacanasAyuntamientoAdapter,
    build_project, inventory_url, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def item(identifier, filename, title='Memoria - URBANISMO', stamp='2025-03-24T12:46:27+01:00'):
    return f'''<div class="article"><div class="article-header"><h2>
    <a href="/component/content/article/{identifier}-entry?catid=109">{title}</a>
    </h2></div><li class="field-entry fichero"><a href="{DOCS + filename}"></a></li>
    <span class="published"><time datetime="{stamp}"></time></span></div>'''


def page(number, total, items, offsets):
    links = ''.join(f'<a href="/component/content/category/8-ayuntamiento/109-trámites?Itemid=101&amp;amp;start={offset}">{offset}</a>' for offset in offsets)
    return f'<div id="contenido" class="bloginicio">{items}<nav class="pagination">{links}</nav><div class="pagination-counter">Página {number} de {total}</div></div>'


def pages():
    names = list(MAPS)
    first = ''.join(item(4949 + i, name) for i, name in enumerate(names[:4]))
    first += item(4952, 'gestion.pdf', 'Catálogo - URBANISMO')
    second = ''.join(item(4954 + i, name, 'Inventario - URBANISMO') for i, name in enumerate(names[4:]))
    return {0: page(1, 2, first, [5]), 5: page(2, 2, second, [0])}


def texts():
    return {name: marker + '\nPOM. Villacañas Doc.Refundido-Julio 01.v1' for name, (_, marker) in TEXTS.items()}


class VillacanasTests(unittest.TestCase):
    def test_groups_plan_and_retains_mislabelled_provenance(self):
        docs = [doc for html in pages().values() for doc in parse_inventory(html)[0]]
        row = build_project(docs, texts())
        self.assertEqual(len(row['documentos']), 9)
        gestion = next(d for d in row['documentos'] if d['url'].endswith('/gestion.pdf'))
        self.assertEqual(len(gestion['procedencia']), 2)
        self.assertEqual(gestion['titulo'], 'P-3 Gestión del suelo')
        self.assertEqual(gestion['procedencia'][0]['fecha_publicacion_ficha'], '2025-03-24')
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase']:
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_pagination_decodes_joomla_double_escape(self):
        _, number, total, offsets = parse_inventory(pages()[0])
        self.assertEqual((number, total, offsets), (1, 2, {0, 5}))

    def test_rejects_login_and_missing_pagination(self):
        for html in ['<html>Login</html>', '<div id="contenido" class="bloginicio"></div>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_forms_news_and_related_content_do_not_become_records(self):
        html = page(1, 1, item(1, 'form.pdf', 'Solicitud de licencia') + item(2, 'news.pdf', 'Anuncio de licitación'), [])
        html += item(3, 'gestion.pdf')  # outside inventory, like related articles
        self.assertEqual(parse_inventory(html)[0], [])

    def test_rejects_unknown_document_or_external_attachment(self):
        for fragment in [item(4950, 'new-plan.pdf'), item(4950, 'gestion.pdf').replace(DOCS, 'https://example.org/')]:
            with self.subTest(fragment=fragment), self.assertRaises(ValueError):
                parse_inventory(page(1, 1, fragment, []))

    def test_rejects_wrong_plan_and_partial_document_inventory(self):
        docs = [doc for html in pages().values() for doc in parse_inventory(html)[0]]
        wrong = texts()
        wrong['memoriavilcan.pdf'] = 'MEMORIA PLAN DE ORDENACION MUNICIPAL Other municipality'
        with self.assertRaises(ValueError):
            build_project(docs, wrong)
        with self.assertRaises(ValueError):
            build_project(docs[:-1], texts())

    def test_crawler_refuses_unreachable_or_repeated_pages_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            adapter = VillacanasAyuntamientoAdapter('villacanas')
            cases = [page(1, 2, '', []), pages()[0]]
            for html in cases:
                with patch.object(adapter, '_fetch', return_value=html.encode()), self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
                self.assertEqual(out.read_text(), 'previous snapshot')

    def test_full_snapshot_follows_second_page(self):
        adapter = VillacanasAyuntamientoAdapter('villacanas')
        visited = []
        def fetch(url, pdf=False):
            visited.append(url)
            adapter.source_urls.append(url)
            if not pdf:
                return pages()[5 if 'start=5' in url else 0].encode()
            return b'%PDF-mocked'
        class Extracted:
            stdout = '\n'.join(texts().values()).encode()
        with tempfile.TemporaryDirectory() as folder, patch.object(adapter, '_fetch', side_effect=fetch), patch('municipio.adapters.villacanas.subprocess.run', return_value=Extracted()):
            out = Path(folder) / 'projects.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(result['inventory_pages'], 2)
            self.assertIn(inventory_url(5), visited)
            self.assertEqual(len(json.loads(out.read_text())['documentos']), 9)

    def test_manifest_loads_real_adapter_and_disables_licences(self):
        manifest = load_manifest('villacanas')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Villacañas', 'Toledo', '45185'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, VillacanasAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
