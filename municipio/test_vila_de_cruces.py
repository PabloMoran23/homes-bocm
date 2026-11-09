"""Offline semantic and traversal tests; no network or local evidence dependency."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.vila_de_cruces import (
    BASE, INVENTORY, URBANISMO, VilaDeCrucesAyuntamientoAdapter,
    parse_instrument, parse_inventory, parse_urbanismo,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

TITLE = ('APROBACIÓN INICIAL DA MODIFICACIÓN PUNTUAL DA NORMAS SUBSIDIARIAS '
         'DE PLANEAMENTO PARA A DELIMITACIÓN DO NÚCLEO RURAL DE CUMEIRO')
DETAIL = BASE + '/2025/10/15/cumeiro/'
PDF = BASE + '/wp-content/uploads/certificado.pdf'
SHARE = 'https://nextcloud.viladecruces.gal/s/example'
URBAN_HTML = '''<article><div class="jupiterx-post-content">
<p>O Concello de Vila de Cruces acordou no Pleno celebrado o día 17 de febreiro de 2014 a aprobación inicial do Plan Xeral de Ordenación Municipal.</p>
<p>O día 19 de maio de 2014 rematou o prazo para a presentación de alegacións.</p>
</div></article>'''


def inventory(items, pagination=''):
    return '<main>' + ''.join('<h3 class="raven-post-title"><a href="' + url + '">' + title + '</a></h3>'
                            for title, url in items) + pagination + '</main>'


def instrument(title=TITLE):
    return f'''<main><h1>{title}</h1><article>
<time itemprop="datePublished" datetime="2025-10-15T01:07:46+02:00"></time>
<div class="jupiterx-post-content"><a href="{SHARE}">DOCUMENTACIÓN</a>
<a href="{PDF}">Certificado de acordos</a><a href="{PDF}">Descarga</a></div></article>
<aside><a href="{BASE}/unrelated.pdf">Decoy</a></aside></main>'''


class ParserTests(unittest.TestCase):
    def test_explicit_agreement_not_comment_deadline(self):
        row = parse_urbanismo(URBAN_HTML)
        self.assertEqual(row['fecha_acuerdo'], '2014-02-17')
        self.assertEqual(row['fecha_aprob'], '2014-02-17')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['documentos'], [])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])

    def test_groups_documents_and_keeps_publication_separate(self):
        row = parse_instrument(instrument(), DETAIL)
        self.assertEqual(row['fecha_publicacion'], '2025-10-15')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual([d['url'] for d in row['documentos']], [SHARE, PDF])
        self.assertEqual(row['codigo_ine'], '36059')
        self.assertEqual(row['fase'], 'aprobación inicial')

    def test_rejects_forms_procurement_and_unrelated_news(self):
        for title in ('ANEXO I – COMUNICACIÓN PREVIA SACA MADEIRA',
                      'Licitación de obras', 'Feira da castaña'):
            self.assertEqual(parse_inventory(inventory([(title, DETAIL)]), INVENTORY)[0], [])
            with self.assertRaises(ValueError):
                parse_instrument(instrument(title), DETAIL)

    def test_fail_closed_on_changed_markup_and_external_sources(self):
        for parser, args in ((parse_urbanismo, ('<main>Urbanismo</main>',)),
                             (parse_inventory, ('<main>Access denied</main>', INVENTORY)),
                             (parse_inventory, (inventory([(TITLE, 'https://example.org/')]), INVENTORY)),
                             (parse_instrument, (instrument().replace(PDF, '#').replace(SHARE, '#'), DETAIL))):
            with self.assertRaises(ValueError):
                parser(*args)
        with self.assertRaises(ValueError):
            parse_inventory(inventory([(TITLE, DETAIL)], '<a class="raven-load-more">More</a>'), INVENTORY)

    def test_traverses_pages_cycles_deduplicates_and_refreshes(self):
        page2 = INVENTORY + 'page/2/'
        pages = {URBANISMO: URBAN_HTML,
                 INVENTORY: inventory([('COMUNICACIÓN PREVIA', BASE + '/form/')],
                                      f'<a class="page-numbers" href="{page2}">2</a>'),
                 page2: inventory([(TITLE, DETAIL), (TITLE, DETAIL)],
                                  f'<a rel="next" href="{INVENTORY}">1</a>'),
                 DETAIL: instrument()}
        adapter = VilaDeCrucesAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda url: pages[url]) as fetch:
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 2)
            self.assertEqual(result['inventory_pages'], 2)
            self.assertEqual(fetch.call_count, 4)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len({r['id'] for r in rows}), 2)
            out.write_text('previous complete snapshot')
            with patch.object(adapter, '_fetch', side_effect=lambda url: '<main>Broken</main>' if url == page2 else pages[url]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous complete snapshot')

    def test_manifest_adapter_and_disabled_licences(self):
        manifest = load_manifest('vila-de-cruces')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
