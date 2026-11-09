"""Offline fixtures model the reviewed municipal WordPress markup."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.peralta import PeraltaAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml

TITLE = 'Proyecto construcción de Aula Mentor'
URL = SOURCE + '19418/'


def inventory(links=None, extra=''):
    links = links or [(URL, TITLE)]
    return '<main id="content"><h1>Archivos: Proyectos</h1>' + ''.join(
        f'<article><h2 class="entry-title"><a href="{u}">{t}</a></h2></article>'
        for u, t in links
    ) + extra + '</main>'


def detail(content='', title=TITLE, ident='19418'):
    return f'''<main id="content" class="post-{ident} type-fondos_europeos">
    <h1 class="entry-title">{title}</h1><div class="page-content">{content}</div></main>'''


class PeraltaTests(unittest.TestCase):
    def test_inventory_deduplication_and_next_page(self):
        entries, pages = Adapter.parse_inventory(inventory([(URL, TITLE), (URL, TITLE)],
            '<a class="next page-numbers" href="/fondos-europeos/page/2/">Siguiente</a>'))
        self.assertEqual(entries, {URL: TITLE})
        self.assertEqual(pages, {SOURCE + 'page/2/'})

    def test_sparse_real_detail_does_not_invent_dates_or_geometry(self):
        row = Adapter.parse_project(detail(), URL, TITLE)
        self.assertEqual(row['id'], 'peralta-proy-19418')
        self.assertEqual(row['codigo_ine'], '31202')
        for field in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertEqual(row['documentos'], [])
        self.assertFalse(row['publication_ready'])

    def test_documents_grouped_under_project(self):
        content = '<a href="/one.pdf">Memoria</a><a href="/two.pdf">Plano</a><a href="/one.pdf">Duplicado</a>'
        row = Adapter.parse_project(detail(content), URL, TITLE)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['pagina_origen'], URL)

    def test_unrecognized_sources_and_non_projects_fail(self):
        for html in ('<main id="content"><h1>Proyectos</h1></main>', '<h1>Sign in</h1>',
                     inventory(extra='<button>Cargar más</button>'),
                     inventory(extra='<a rel="next" href="?page=2">Next</a>'),
                     inventory(extra='<a href="?paged=2">Siguiente »</a>'),
                     inventory([('https://example.org/fondos-europeos/1/', TITLE)])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        for title in ('Solicitud de licencia de construcción', 'Licitación de construcción de aula', 'Oferta de empleo'):
            with self.subTest(title=title), self.assertRaises(ValueError):
                Adapter.parse_project(detail(title=title), URL, title)
        with self.assertRaises(ValueError):
            Adapter.parse_project(detail(title='Otro título'), URL, TITLE)

    def test_full_refresh_traverses_pages_and_keeps_old_output_on_failure(self):
        second_url = SOURCE + '19420/'
        second_title = 'Proyecto de adaptación al riesgo de inundaciones'
        pages = {SOURCE: inventory(extra='<a rel="next" href="/fondos-europeos/page/2/">Next</a>'),
                 SOURCE + 'page/2/': inventory([(second_url, second_title)]),
                 URL: detail(), second_url: detail(title=second_title, ident='19420')}
        adapter = Adapter()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
                report = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(report['rows'], 2)
            self.assertEqual(report['inventory_pages'], 2)
            self.assertEqual(fetch.call_count, 4)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)
            before = out.read_bytes()
            with patch.object(adapter, '_fetch', return_value='<html>error</html>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), before)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('peralta')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '31202')
        self.assertEqual(manifest.provincia, 'Navarra')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertEqual(Adapter().backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
