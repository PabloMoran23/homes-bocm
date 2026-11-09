"""Offline parser and traversal tests. Run: python -m unittest municipio.test_consell."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.consell import (
    BASE, SOURCE, ConsellAyuntamientoAdapter, official_url, parse_inventory, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def page(title, body):
    return f'<main><div class="layout-content"><h1>{title}</h1>{body}</div></main>'


def folder(title, links, pager=''):
    cards = ''.join(f'<a href="{url}"><h3>{label}</h3></a>' for label, url in links)
    return page(title, f'<div class="taxonomy-term-files">{cards}</div>{pager}')


def document(title='Memòria', href='/sites/cilma_consell/files/memoria.pdf', date='29/01/2025'):
    return (f'<section class="multimedia--documents"><div><h3>{title}</h3>'
            f'<span>PDF · {date}</span><a download href="{href}">Descarregar</a></div></section>')


def detail(title, body):
    return page(title, f'<article class="basic-page-detail">{body}</article>')


def inventory(entries):
    cards = ''.join(f'<li><a href="{url}">chevron_right {title}</a></li>' for title, url in entries)
    return ('<main><aside><nav><li><span aria-current="page">chevron_right Urbanisme</span>'
            f'<ul>{cards}</ul></li></nav></aside><div class="layout-content"><h1>Urbanisme</h1></div></main>')


class ConsellTests(unittest.TestCase):
    def test_manifest_and_dynamic_adapter(self):
        m = load_manifest('consell')
        raw = load_yaml(m.path)
        self.assertEqual((m.nombre, m.provincia, raw['codigo_ine']), ('Consell', 'Illes Balears', '07016'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(m.licencias.enabled)
        module, name = m.portal.adapter.split(':')
        import importlib
        self.assertIs(getattr(importlib.import_module(module), name), ConsellAyuntamientoAdapter)

    def test_inventory_excludes_navigation_and_deduplicates(self):
        html = inventory([('Normes Subsidiàries', '/ca/normes'), ('Normes Subsidiàries', '/ca/normes')])
        self.assertEqual(parse_inventory(html), {BASE + '/ca/normes': 'Normes Subsidiàries'})
        with self.assertRaises(ValueError):
            parse_inventory(inventory([('Sol·licitud de llicència', '/ca/form')]))
        with self.assertRaises(ValueError):
            parse_inventory('<h1>Ajuntament de Consell</h1>')

    def test_attachment_provenance_and_dates(self):
        url = BASE + '/ca/plan'
        title, docs, links = parse_page(detail('Plan', document()).replace('basic-page-detail', 'node-file-or-document'), url)
        self.assertEqual(docs[0]['fecha_portal'], '2025-01-29')
        self.assertEqual(docs[0]['source_page'], url)
        self.assertNotIn('fecha_acuerdo', docs[0])
        self.assertEqual(links, [])
        self.assertEqual(title, 'Plan')

    def test_related_technical_package_but_not_generic_links(self):
        related = ('<div><h3>Documentació</h3><a href="/ca/arxius-i-documents/parking">Veure</a></div>'
                   '<div><h3>Documents d’interès</h3><a href="/ca/unrelated">Veure</a></div>')
        _, _, links = parse_page(detail('Plan', document() + related), BASE + '/ca/plan')
        self.assertEqual(links, [BASE + '/ca/arxius-i-documents/parking'])

    def test_reject_home_empty_detail_and_external_document(self):
        for html in ['<main><h1>Ajuntament</h1></main>', detail('Plan', ''), detail('Plan', document(href='https://example.com/x.pdf'))]:
            with self.assertRaises(ValueError):
                parse_page(html, BASE + '/ca/plan')
        with self.assertRaises(ValueError):
            official_url(BASE, 'http://ajconsell.net/file')

    def test_legacy_link_retained_without_fetching_external_host(self):
        html = page('Medi ambient', '<article class="link-detail"><a target="_blank" href="http://libre/www.ajconsell.net/Memoria_ambiental.pdf">Visitar</a></article>')
        _, docs, links = parse_page(html, BASE + '/ca/enllacos/medi-ambient')
        self.assertEqual(docs[0]['tipo'], 'referencia_externa')
        self.assertEqual(docs[0]['url'], 'http://libre/www.ajconsell.net/Memoria_ambiental.pdf')
        self.assertEqual(links, [])

    def test_pagination_fetch_failure_preserves_previous_output(self):
        root = BASE + '/ca/plan'
        pages = {SOURCE: inventory([('Normes Subsidiàries', root)]),
                 root: folder('Plan', [], '<nav><a href="?page=1">Pàgina 2</a></nav>')}
        adapter = ConsellAyuntamientoAdapter('consell')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            path.write_text('previous complete snapshot')
            with patch.object(adapter, '_fetch', side_effect=lambda url: pages[url]):
                with self.assertRaises(KeyError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous complete snapshot')

    def test_complete_pagination_and_grouping_shared_document(self):
        root = BASE + '/ca/plan'
        first, second = BASE + '/ca/doc1', BASE + '/ca/doc2'
        pages = {
            SOURCE: inventory([('Adaptació de les NNSS', root)]),
            root: folder('Plan', [('First', first)], '<nav><a href="?page=1">Pàgina següent</a><a href="?page=1">2</a></nav>'),
            root + '?page=1': folder('Plan', [('Second', second)]),
            first: detail('First', document()),
            second: detail('Second', document() + document('Plànol', '/sites/cilma_consell/files/map.pdf')),
        }
        adapter = ConsellAyuntamientoAdapter('consell')
        with patch.object(adapter, '_fetch', side_effect=lambda url: pages[url]) as fetch:
            rows, limitations = adapter.collect()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][0]['source_pages'], [first, second])
        self.assertEqual(len(rows[0]['paginas_fuente']), 4)
        self.assertEqual(fetch.call_count, 5)
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['lat'])
        self.assertFalse(rows[0]['publication_ready'])

    def test_broken_catalogue_reported_and_disabled_licences(self):
        root = BASE + '/ca/normes'
        broken = BASE + '/ca/arxius-i-documents/cataleg-de-proteccio-x'
        pages = {SOURCE: inventory([('Normes Subsidiàries', root), ('Catàleg', broken)]),
                 root: detail('Normes', document()), broken: '<main>Ajuntament de Consell</main>'}
        adapter = ConsellAyuntamientoAdapter('consell')
        with patch.object(adapter, '_fetch', side_effect=lambda url: pages[url]):
            rows, limitations = adapter.collect()
        self.assertEqual(len(rows), 1)
        self.assertTrue(any(broken in text for text in limitations))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
            adapter._write(path, rows)
            self.assertEqual(json.loads(path.read_text())['codigo_ine'], '07016')


if __name__ == '__main__':
    unittest.main()
