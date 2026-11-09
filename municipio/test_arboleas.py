"""Offline parser/adapter checks; fixtures are illustrative HTML, not live records."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.arboleas import (
    ArboleasAyuntamientoAdapter, SOURCE, page_url, parse_section,
    parse_category, parse_documents, group_instruments,
)
from municipio.manifest import load_manifest, load_yaml


def section(count=2):
    return f'''<div id="content"><div class="sectionlist"><ul><li>
    <a class="category" href="/index.php?option=com_content&view=category&id=80%3Annss">NNSS 1997</a>
    <span class="number">({count} Ítems)</span></li></ul></div></div>'''


def category(article, next_offset=None):
    pagination = (f'<a href="{page_url("category", "80", next_offset)}">Siguiente</a>'
                  if next_offset is not None else '')
    return f'''<div id="content"><div class="categorylist"><table><tr><td>
    <a href="{page_url('article', article)}">Memoria {article}</a></td></tr></table>
    <div class="pagination">{pagination}</div></div></div>'''


ARTICLE = '''<div id="content"><div class="article"><div class="headline">
<a href="/index.php?format=pdf">PDF</a></div>
<a href="/images/pdf/a document.pdf">Memoria</a>
<a href="/images/pdf/a document.pdf">Duplicado</a></div></div>
<a href="/images/pdf/unrelated.pdf">Sidebar</a>'''


class ArboleasTests(unittest.TestCase):
    def test_inventory_scope_and_empty_failure(self):
        cats = parse_section(section())
        self.assertEqual((cats[0]['id'], cats[0]['expected']), ('80', 2))
        with self.assertRaises(ValueError):
            parse_section('<a href="licencia.pdf">Solicitud de licencia</a>')
        with self.assertRaises(ValueError):
            parse_section(section().replace('NNSS 1997', 'Modelos de solicitud'))

    def test_pagination_and_article_identity(self):
        articles, pages = parse_category(category('260', 50), page_url('category', '80'))
        self.assertEqual(articles[0]['url'], page_url('article', '260'))
        self.assertEqual(pages, [page_url('category', '80', 50)])
        with self.assertRaises(ValueError):
            parse_category(category('260', 50).replace('id=80', 'id=81'), page_url('category', '80'))

    def test_attachment_scope_provenance_and_encoding(self):
        url = page_url('article', '260')
        docs = parse_documents(ARTICLE, url)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['source_page'], url)
        self.assertTrue(docs[0]['url'].endswith('a%20document.pdf'))
        with self.assertRaises(ValueError):
            parse_documents('<div id="content"><div class="article">No documents</div></div>', url)

    def test_legacy_junta_links_are_retained_and_municipality_scoped(self):
        legacy = 'http://www.juntadeandalucia.es/viviendayordenaciondelterritorio/iws/pua_ext/ALMERIA/04017/map.PDF'
        html = f'<div id="content"><div class="article"><a href="{legacy}">Plano</a></div></div>'
        self.assertEqual(parse_documents(html, SOURCE)[0]['url'], legacy)
        with self.assertRaises(ValueError):
            parse_documents(html.replace('/04017/', '/04018/'), SOURCE)
        with self.assertRaisesRegex(ValueError, 'Paginated'):
            parse_documents(ARTICLE.replace('<div class="headline">', '<div class="contenttoc"></div><div class="headline">'), SOURCE)

    def test_group_versions_and_preserve_isolation(self):
        cats = []
        for ident in ['89', '94', '87']:
            cats.append({'id': ident, 'titulo': 'Instrumento ' + ident, 'url': page_url('category', ident),
                         'articles': [{'url': ident}], 'documents': [{'url': ident}]})
        rows = group_instruments(cats)
        self.assertEqual(len(rows), 2)
        self.assertEqual([d['url'] for d in rows[0]['documentos']], ['89', '94'])
        self.assertEqual(rows[1]['documentos'], [{'url': '87'}])
        self.assertEqual(rows[0]['titulo'], 'Instrumento 94')
        for row in rows:
            for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase']:
                self.assertNotIn(field, row)

    def test_full_crawl_follows_second_page(self):
        fixtures = {SOURCE: section(), page_url('category', '80'): category('260', 50),
                    page_url('category', '80', 50): category('261', 0),
                    page_url('article', '260'): ARTICLE, page_url('article', '261'): ARTICLE}
        with TemporaryDirectory() as tmp, patch.object(ArboleasAyuntamientoAdapter, '_fetch', side_effect=fixtures.__getitem__):
            output = Path(tmp) / 'rows.jsonl'
            result = ArboleasAyuntamientoAdapter('arboleas').backfill_proyectos(output)
            row = json.loads(output.read_text())
            self.assertEqual(result['document_articles'], 2)
            self.assertEqual(len(row['fichas_documentales']), 2)

    def test_incomplete_inventory_preserves_output(self):
        fixtures = {SOURCE: section(3), page_url('category', '80'): category('260')}
        with TemporaryDirectory() as tmp, patch.object(ArboleasAyuntamientoAdapter, '_fetch', side_effect=fixtures.__getitem__):
            output = Path(tmp) / 'rows.jsonl'
            output.write_text('previous result')
            with self.assertRaisesRegex(ValueError, 'Incomplete category'):
                ArboleasAyuntamientoAdapter('arboleas').backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous result')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('arboleas')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '04017')
        self.assertEqual(manifest.provincia, 'Almería')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = ArboleasAyuntamientoAdapter('arboleas').backfill_licencias(out)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
