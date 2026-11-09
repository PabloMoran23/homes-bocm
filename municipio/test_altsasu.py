"""Offline parser/crawler tests; live captures are kept separately in evidence/."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.altsasu import (
    AltsasuAyuntamientoAdapter, BASE, EXCLUDED, PROJECTS, SOURCE, _page_url,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(slug, title='Proyecto', links=''):
    return f'''<main><h2 class="titulo-listado">Proyectos y acciones municipales</h2>
    <article class="entrada"><div class="list-title"><a href="/{slug}/">{title}</a></div></article>
    <div id="paginacion">{links}</div></main>'''


def detail(slug, title='Proyecto', links=''):
    return f'''<main><h2 class="titulo-single">{title}</h2>
    <h3 class="categoria_gene">Ayuntamiento - Proyectos y acciones municipales</h3>
    <div class="contenido content"><ul><li>Facebook</li></ul><div class="mt-3">
    <p>{PROJECTS[slug][1]}.</p>{links}</div></div></main>'''


class AltsasuTests(unittest.TestCase):
    def test_manifest_contract(self):
        manifest = load_manifest('altsasu')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('31010', 'Navarra'))
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.altsasu:AltsasuAyuntamientoAdapter')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)

    def test_group_documents_without_guessing_dates_or_geometry(self):
        slug = 'piscina-cubierta-en-zelandi'
        docs = ''.join(f'<a href="/wp-content/uploads/2022/09/plano-{n}.pdf">Plano {n}</a>' for n in range(4))
        docs += '<a href="/wp-content/uploads/2022/09/plano-0.pdf">Duplicado</a>'
        html = detail(slug, links=docs) + '<meta property="article:published_time" content="2022-09-01">'
        row = AltsasuAyuntamientoAdapter.parse_project(html, BASE + '/' + slug + '/', 'Proyecto')
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['codigo_ine'], '31010')
        self.assertNotIn('Facebook', row['descripcion'])
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[field])

    def test_pagination_normalizes_mixed_wordpress_links(self):
        self.assertEqual(_page_url(SOURCE + 'page/2/?paged=3'), SOURCE + '?paged=3')
        self.assertEqual(_page_url(SOURCE + 'page/2/'), SOURCE + '?paged=2')
        self.assertEqual(_page_url(SOURCE + 'page/4/?paged=1'), SOURCE)
        for link in ('https://example.org/?paged=2', SOURCE + '?paged=abc', BASE + '/other/'):
            with self.assertRaises(ValueError):
                _page_url(link)

    def test_crawl_follows_all_discovered_pages_and_excludes_services(self):
        slug = 'nueva-escuela-de-musica'
        excluded = 'mejoras-en-espacios-ajardinados-y-abiertos'
        last = SOURCE + '?paged=8'
        pages = {SOURCE: inventory(excluded, links='<a href="?paged=8">8</a>'),
                 last: inventory(slug, links='<a href="?paged=1">1</a>'),
                 BASE + '/' + slug + '/': detail(slug)}
        with tempfile.TemporaryDirectory() as tmp, patch.object(AltsasuAyuntamientoAdapter, '_fetch', side_effect=pages.__getitem__) as fetch:
            out = Path(tmp) / 'projects.jsonl'
            result = AltsasuAyuntamientoAdapter().backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(result['inventory_pages'], [SOURCE, last])
            self.assertEqual(result['inventory_entries'], 2)
            self.assertEqual(result['excluded'][0]['reason'], EXCLUDED[excluded])
            self.assertEqual(fetch.call_count, 3)

    def test_repeated_pages_and_unreviewed_entries_preserve_previous_output(self):
        slug = 'plan-de-movilidad'
        repeated = inventory(slug, links='<a href="?paged=2">SIGUIENTE »</a>')
        for html in (repeated, inventory('new-unreviewed-project')):
            with tempfile.TemporaryDirectory() as tmp, patch.object(AltsasuAyuntamientoAdapter, '_fetch', return_value=html):
                out = Path(tmp) / 'projects.jsonl'
                out.write_text('previous snapshot\n')
                with self.assertRaises(ValueError):
                    AltsasuAyuntamientoAdapter().backfill_proyectos(out)
                self.assertEqual(out.read_text(), 'previous snapshot\n')

    def test_rejects_missing_inventory_and_unverified_detail(self):
        with self.assertRaises(ValueError):
            AltsasuAyuntamientoAdapter.parse_inventory('<main>Licencias: solicitud</main>')
        slug = 'nueva-escuela-de-musica'
        html = detail(slug).replace(PROJECTS[slug][1], 'Solicitud de licencia de obra')
        with self.assertRaises(ValueError):
            AltsasuAyuntamientoAdapter.parse_project(html, BASE + '/' + slug + '/', 'Proyecto')

    def test_disabled_licences(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(AltsasuAyuntamientoAdapter().backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
