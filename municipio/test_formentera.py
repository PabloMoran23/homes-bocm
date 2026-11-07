"""Offline parser/adapter checks; synthetic markup mirrors captured Joomla structure."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.formentera import (
    BASE, SOURCE, FormenteraAyuntamientoAdapter as Adapter,
    article_url, publication_date,
)
from municipio.manifest import load_manifest


def link(ident, title):
    return f'<a href="/index.php?option=com_content&amp;view=article&amp;id={ident}&amp;lang=ca">{title}</a>'


def detail(title, content='', posted=''):
    return f'<div class="rt-article"><h1 class="rt-article-title">{title}</h1>{posted}{content}</div>'


class FormenteraTests(unittest.TestCase):
    def test_manifest(self):
        manifest = load_manifest('formentera')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.formentera:FormenteraAyuntamientoAdapter')

    def test_inventory_deduplicates_stages_and_menu_alias(self):
        html = '<ul class="menu">' + link(2490, 'Text refós i planimetria NNSS 2013')
        html += link(2491, 'Aprovació definitiva de la modificació núm. 1 de les NNSS 2013')
        html += link('8715:slug', 'Aprovació inicial de la modificació puntual núm. 6 del PTI Formentera')
        html += link('8715:other', 'II. Aprovació inicial de la modificació puntual núm. 6 del PTI Formentera')
        html += link(9958, 'Aprovació definitiva de la modificació puntual núm. 6 del PTI Formentera') + '</ul>'
        groups = Adapter.parse_inventory(html)
        self.assertEqual(set(groups), {'mod-1', 'mod-6'})
        self.assertEqual(len(groups['mod-6']['pages']), 2)
        self.assertIn('definitiva', groups['mod-6']['titulo'])
        self.assertEqual(article_url('/index.php?option=com_content&view=article&id=8715:slug&Itemid=4'),
                         article_url('/index.php?option=com_content&view=article&id=8715&Itemid=8'))
        with self.assertRaisesRegex(ValueError, 'pagination'):
            Adapter.parse_inventory(html.replace('</ul>', '<a rel="next" href="?page=2">Next</a></ul>'))
        with self.assertRaisesRegex(ValueError, 'Unrecognized'):
            Adapter.parse_inventory(html.replace('</ul>', link(100, 'Nou Pla Especial Formentera') + '</ul>'))

    def test_detail_provenance_and_publication_not_agreement(self):
        url = article_url('/index.php?option=com_content&view=article&id=9957')
        html = detail('Aprovació definitiva de la modificació puntual núm. 6 del PTI Formentera',
                      '<a href="/images/certificat.pdf">Certificat del Ple de 31-03-2023</a>'
                      '<a href="http://www.caib.es/eboibfront/pdf/ca/2023/56/123">Anunci BOIB</a>'
                      '<div class="rt-article-icons"><a href="?format=pdf">PDF</a></div>',
                      '<span class="rt-date-posted">Dimecres, 17 de Maig de 2023 11:41</span>')
        page, docs, children = Adapter.parse_detail(html, url)
        self.assertEqual(page['fecha_publicacion'], '2023-05-17')
        self.assertNotIn('fecha_acuerdo', page)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]['source_urls'], [url])
        self.assertFalse(children)
        self.assertEqual(publication_date("Dimarts, 12 d'Abril de 2022 10:14"), '2022-04-12')
        with self.assertRaises(ValueError):
            Adapter.parse_detail('<h1>Missing article</h1>', url)
        with self.assertRaises(ValueError):
            Adapter.parse_detail(html.replace('</div>', '<div class="pagination"></div></div>', 1), url)

    def test_full_snapshot_groups_docs_and_fails_before_replacing(self):
        alias = 'Text refós i planimetria NNSS 2013'
        mod1 = 'Aprovació definitiva de la modificació núm. 1 de les NNSS 2013'
        mod6 = 'Aprovació definitiva de la modificació puntual núm. 6 del PTI Formentera'
        child6 = 'Aprovació inicial de la modificació puntual núm. 6 del PTI Formentera'
        doc = '<a href="/images/shared.pdf">Publicació de la modificació núm. 1 de les NNSS Formentera</a>'
        urls = {i: article_url(f'/index.php?option=com_content&view=article&id={i}') for i in [2490, 2491, 9958, 8715]}
        responses = {SOURCE: '<ul class="menu">' + link(2490, alias) + link(2491, mod1) + link(9958, mod6) + '</ul>',
                     urls[2490]: detail(alias, doc), urls[2491]: detail(mod1, doc),
                     urls[9958]: detail(mod6, link(8715, child6)),
                     urls[8715]: detail(child6, '<a href="/images/project.zip">Memòria i plànols</a>')}
        adapter = Adapter('formentera')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=lambda session, url: responses[url]):
            out = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(out)['rows'], 2)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows[0]['documentos']), 1)
            self.assertEqual(len(rows[0]['documentos'][0]['source_urls']), 2)
            self.assertEqual(len(rows[1]['paginas_fuente']), 2)
            self.assertIsNone(rows[1]['fecha_aprob'])
            self.assertIsNone(rows[1]['lat'])
            previous = out.read_bytes()
            responses[urls[8715]] = detail(child6)
            with self.assertRaisesRegex(ValueError, 'no supporting documents'):
                adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(out.read_bytes(), previous)
            licenses = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(licenses)['status'], 'disabled')
            self.assertEqual(licenses.read_text(), '')


if __name__ == '__main__':
    unittest.main()
