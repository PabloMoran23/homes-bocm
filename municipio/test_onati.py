"""Parser and refresh contract tests; no live network needed."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.onati import (
    BASE, SOURCE, OnatiAyuntamientoAdapter, canonical, parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest

SECTION = SOURCE + '/a-dokumentua-memoria'
HAPO = BASE + '/eu/udala/planak/hapo-edo-hiri-antolamenduaren-plan-orokorra/prozesua'
AMENDMENT = SOURCE + '/arau-aldaketa'


def html(body, title='Inventario', nav=''):
    return f'<main id="content"><h1>{title}</h1><div id="parent-fieldname-text">{body}</div>{nav}</main>'


INVENTORY = html(
    '<strong>OÑATIKO HIRI ANTOLAKETAKO ARAUAK. DOKUMENTU BATEGINA.</strong>'
    f'<a href="{SECTION}">Memoria</a><a href="{SECTION}">Duplicate</a>'
    f'<a href="{HAPO}">HAPO</a><a href="https://herrigis.gis-cdn.net/oinati/">Mapa</a>',
    nav=f'<div class="secondarynav"><a href="{AMENDMENT}">Arau aldaketa</a></div>',
)


class OnatiTests(unittest.TestCase):
    def test_discovery_groups_sections_and_instruments(self):
        _, sections, instruments = parse_inventory(INVENTORY)
        self.assertEqual(list(sections), [SECTION])
        self.assertEqual(instruments, {HAPO: 'hapo', AMENDMENT: 'modificacion'})

    def test_document_provenance_excludes_news_and_tender(self):
        document = html(
            '<h3>Hasierako onespenaren agiriak</h3>'
            '<a href="arau.pdf">Araudi orokorra</a><a href="arau.pdf">Duplicate</a>'
            '<a href="planoa.jpg">Planoa</a><table><tr><td>2017-10-24</td>'
            '<td><a href="https://apps.euskadi.eus/tender">Idaztea</a></td></tr></table>'
            '<a href="/eu/berbia/albisteak/foo">Albistea</a>', title='HAPO',
        )
        _, _, docs = parse_documents(document, HAPO)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]['source_url'], HAPO)
        self.assertEqual(docs[0]['url'], HAPO.rsplit('/', 1)[0] + '/arau.pdf')
        self.assertEqual(docs[0]['seccion'], 'HAPO')

    def test_complete_refresh_and_unknown_dates(self):
        pages = {SOURCE: INVENTORY}
        for url in (SECTION, HAPO, AMENDMENT):
            pages[url] = html('<a href="instrument.pdf">Document</a>', title=url.rsplit('/', 1)[-1])
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            adapter = OnatiAyuntamientoAdapter('onati')
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
                report = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(report['live_records'], 3)
            self.assertEqual(len({r['id'] for r in rows}), 3)
            self.assertEqual(rows[0]['tipo'], 'normas_subsidiarias')
            for row in rows:
                self.assertEqual(row['codigo_ine'], '20059')
                self.assertIsNone(row['fecha_aprob'])
                self.assertIsNone(row['fecha_publicacion'])
                self.assertIsNone(row['fecha_acuerdo'])
                self.assertNotIn('lat', row)
            # A later fetch failure must not replace existing successful output.
            before = out.read_bytes()
            pages[AMENDMENT] = html('<a href="form">Formulario de licencia</a>')
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), before)
            adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')

    def test_pagination_missing_content_and_host_drift_fail(self):
        for extra in ('<div class="listingBar"><a href="?b_start:int=20">2</a></div>',
                      '<a rel="next" href="?page=2">2</a>',
                      '<a href="?page=2">Hurrengoa</a>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(INVENTORY.replace('</main>', extra + '</main>'))
        with self.assertRaises(ValueError):
            parse_inventory('<html>Unavailable</html>')
        with self.assertRaises(ValueError):
            parse_documents(html('<a href="https://other.invalid/a.pdf">PDF</a>'), HAPO)
        self.assertEqual(canonical('https://www.oñati.eus/a#top'), BASE + '/a')

    def test_manifest(self):
        manifest = load_manifest('onati')
        self.assertEqual(manifest.nombre, 'Oñati')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
