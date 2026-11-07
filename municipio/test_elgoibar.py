import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.elgoibar import ElgoibarAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest


def inventory():
    return '''<main>
    <div class="lsow-panel"><div class="lsow-panel-title">Plan General de Ordenación Urbana (PGOU)</div>
    <div class="lsow-panel-content"><a href="/es/pgou/">PGOU</a><a href="/es/pgou/">Modificación</a></div></div>
    <div class="lsow-panel"><div class="lsow-panel-title">Planes de Ordenación Pormenorizada</div>
    <div class="lsow-panel-content"><a href="/es/plan/">Plan</a></div></div>
    <div class="lsow-panel"><div class="lsow-panel-title">Planes en proceso de tramitación</div>
    <div class="lsow-panel-content"></div></div>
    <a href="/es/noticia/">Noticias</a></main>'''


DETAIL = '''<main><h1>Plan general</h1><div class="entry-content">
<span class="lsow-tab-title">Plan general</span><span class="lsow-tab-title">1.ª Modificación del plan general</span>
<div class="lsow-tab-pane"><a href="/info/memoria.pdf">Memoria</a><a href="/info/plano.pdf">Plano</a>
<a href="/info/memoria.pdf">Texto completo</a></div>
<div class="lsow-tab-pane"><a href="/info/bog.pdf">Acuerdo BOG 2023-03-09</a></div>
</div><time>2026-11-07</time></main>'''


class ElgoibarTests(unittest.TestCase):
    def test_inventory_deduplicates_pages_and_ignores_news(self):
        self.assertEqual(Adapter.parse_inventory(inventory()),
                         ['https://elgoibar.eus/es/pgou/', 'https://elgoibar.eus/es/plan/'])

    def test_group_documents_and_do_not_invent_dates(self):
        rows = Adapter.parse_detail(DETAIL, SOURCE)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(rows[0]['documentos'][0]['etiquetas_fuente'], ['Memoria', 'Texto completo'])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[0]['id'], Adapter.parse_detail(DETAIL.replace('Plano', 'Mapa'), SOURCE)[0]['id'])
        for row in rows:
            for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertIsNone(row[field])

    def test_untabbed_instrument_relative_documents(self):
        rows = Adapter.parse_detail('<main><h1>Plan especial Santa Klara</h1><div class="entry-content">'
                                    '<a href="/info/plan.pdf">Texto refundido</a></div></main>', SOURCE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['documentos'][0]['url'], 'https://elgoibar.eus/info/plan.pdf')

    def test_fail_on_pagination_missing_documents_or_changed_structure(self):
        for html in (inventory().replace('</main>', '<a rel="next" href="?page=2">2</a></main>'), '<main></main>'):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        for html in (DETAIL.replace('lsow-tab-pane', 'changed'), DETAIL.replace('.pdf', '.html'),
                     '<main><h1>Plan</h1><div class="entry-content"></div></main>'):
            with self.assertRaises(ValueError):
                Adapter.parse_detail(html, SOURCE)

    def test_live_path_atomic_failure_and_disabled_licences(self):
        adapter = Adapter('elgoibar')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'out.jsonl'
            out.write_text('previous')
            with patch.object(adapter, '_fetch', side_effect=[inventory(), DETAIL, '<main></main>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous')
            with patch.object(adapter, '_fetch', side_effect=[inventory(), DETAIL, DETAIL]):
                result = adapter.backfill_proyectos(out)
            self.assertEqual(result['rows'], 4)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 4)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('elgoibar')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.elgoibar:ElgoibarAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
