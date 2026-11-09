"""Offline parser/adapter tests; no network or local evidence fixtures required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.astigarraga import (
    AstigarragaAyuntamientoAdapter, SOURCE, parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml

TITLE = 'Plan especial de ampliación de la Herri eskola'
URL = 'https://www.astigarraga.eus/es/-/herri-eskola-handitzeko-plan-berezia'


def inventory(title=TITLE, url=URL, date='17-11-2021', extra=''):
    return f'''<main id="main-content"><h1>Desarrollo del PGOU</h1>
    <div class="destacado_contenido"><p class="titulo"><a href="{url}">{title}</a></p>
    <p class="pre-titulo">Fecha de publicación: {date}</p></div>{extra}</main>'''


def detail(title=TITLE, docs=True):
    links = '''<a href="/documents/120801/1/DOC_A.pdf/id?t=123">Memoria</a>
    <a href="/documents/120801/1/DOC_A.pdf/id?t=456">Memoria duplicada</a>
    <a href="/documents/120801/1/DOC_I.pdf/id">Planos</a>''' if docs else ''
    return f'''<main id="main-content"><div class="asset-full-content">
    <span class="asset-title">{title}</span><div class="journal-content-article">{links}</div>
    </div><a href="/documents/unrelated.pdf">Navigation document</a></main>'''


class AstigarragaTests(unittest.TestCase):
    def test_dates_and_grouped_document_provenance(self):
        row = parse_inventory(inventory())[0]
        self.assertEqual(row['fecha_publicacion'], '2021-11-17')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fase'])
        self.assertIsNone(row['geometry'])
        docs = parse_documents(detail(), row)
        self.assertEqual(len(docs), 2)
        self.assertTrue(docs[0]['url'].endswith('?t=123'))
        self.assertEqual(docs[0]['source_url'], URL)
        self.assertEqual(row['id'], parse_inventory(inventory(date='18-11-2021'))[0]['id'])

    def test_fail_closed_inventory(self):
        for html in ('<html>login</html>', inventory(title='Solicitud de licencia'),
                     inventory(date='31-02-2021'), inventory(url='https://other.invalid/es/-/x'),
                     inventory(extra='<a rel="next" href="?page=2">2</a>'),
                     inventory(extra='<a href="?cur=2">Siguiente</a>'),
                     inventory(extra='<div class="lfr-pagination">2</div>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_detail_requires_matching_title_and_documents(self):
        row = parse_inventory(inventory())[0]
        for html in (detail(title='Otro plan'), detail(docs=False), '<html/>',
                     detail().replace('/documents/120801/1/DOC_I.pdf/id', 'https://other.invalid/documents/x')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_documents(html, row)

    def test_conflicting_duplicates_rejected(self):
        other = inventory(date='18-11-2021').split('<div class="destacado_contenido">')[1].split('</main>')[0]
        with self.assertRaises(ValueError):
            parse_inventory(inventory(extra='<div class="destacado_contenido">' + other))

    def test_snapshot_and_failure_preserves_previous_output(self):
        adapter = AstigarragaAyuntamientoAdapter('astigarraga')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory(), detail()]):
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(result['source_urls'], [SOURCE, URL])
            before = output.read_text()
            self.assertEqual(len(json.loads(before)['documentos']), 2)
            with patch.object(adapter, '_fetch', side_effect=[inventory(), detail(docs=False)]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), before)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'lic.jsonl')['status'], 'disabled')
            self.assertEqual((Path(tmp) / 'lic.jsonl').read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('astigarraga')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Astigarraga', 'Gipuzkoa', '20903'))
        for section, flag in [('licencias', 'enabled'), ('schedule', 'enabled'), ('geocode', 'jitter_missing')]:
            self.assertIs(raw[section][flag], False)


if __name__ == '__main__':
    unittest.main()
