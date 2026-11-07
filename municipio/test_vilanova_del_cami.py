import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.vilanova_del_cami import (
    BASE, SOURCE, VilanovaDelCamiAyuntamientoAdapter, apply_notice, inventory,
    page_date, parse_detail,
)


def listing(href='plan.html', pager=''):
    return f'''<div id="readspeakerPage"><h1>Urbanisme</h1>
    <ul class="articlelist"><li class="article-item"><a href="{href}">
    <p class="subtitle">Pla de millora urbana Sector PMU r8 “Barri Centre”</p></a></li>
    <li class="article-item"><a href="form.html"><p class="subtitle">Sol·licitud de llicència</p></a></li>
    <li class="article-item"><a href="map.html"><p class="subtitle">Mapa Acústic</p></a></li>
    </ul><div class="pager">{pager}</div></div>'''


def detail():
    return '''<div id="readspeakerPage"><h1>Pla de millora urbana Sector PMU r8 “Barri Centre”</h1>
    <div class="date">Dimarts, 27 de juliol de 2021</div>
    <div class="ddbbtext"><p>Aprovació definitiva del Pla de Millora Urbana</p></div></div>
    <section id="page-documents"><a href="/media/notice.pdf">anunci BOPB</a>
    <a href="/media/plan.pdf">Pla PMU r8</a><a href="/media/plan.pdf">Duplicate</a></section>'''


class ParserTests(unittest.TestCase):
    def test_inventory_filters_and_pagination(self):
        links, pages = inventory(listing(pager='<a href="?page=2">2</a>'))
        self.assertEqual(links, [SOURCE + 'plan.html'])
        self.assertEqual(pages, [SOURCE + '?page=2'])
        for bad in ['<h1>Login</h1>', listing(pager='Next page')]:
            with self.assertRaises(ValueError):
                inventory(bad)
        with self.assertRaises(ValueError):
            inventory(listing(href='https://unrelated.example/plan'))

    def test_documents_grouped_and_dates_distinct(self):
        row = parse_detail(detail(), SOURCE + 'plan.html')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_publicacion'], '2021-07-27')
        self.assertIsNone(row['fecha_aprob'])
        apply_notice(row, 'Data Signatura: 15/07/2021 Per Acord del Ple de data 12/07/2021, '
                     'es va aprovar definitivament el Pla de Millora Urbana Sector PMU r8', BASE + '/media/notice.pdf')
        self.assertEqual(row['fecha_acuerdo'], '2021-07-12')
        self.assertEqual(row['fecha_publicacion'], '2021-07-27')
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])

    def test_r3_document_overrides_inaccurate_page_label(self):
        row = parse_detail(detail().replace('PMU r8', 'PMU r3'), SOURCE + 'plan.html')
        apply_notice(row, 'Exp. Núm.: AP/2019072 Data Signatura: 18/05/2020 '
                     'Per resolució de l’Alcaldia de data 04/02/2020, Primer.- Aprovar definitivament '
                     'el Projecte d’Urbanització del Pla de Millora Urbana r3 Barri Bonavista', 'notice.pdf')
        self.assertEqual(row['tipo'], 'proyecto de urbanización')
        self.assertEqual(row['fecha_aprob'], '2020-02-04')
        self.assertEqual(row['expediente'], 'AP/2019072')
        with self.assertRaises(ValueError):
            apply_notice(row, 'Data Signatura: 18/05/2020 Aprovar definitivament', 'notice.pdf')

    def test_catalan_dates_and_invalid_detail(self):
        self.assertEqual(page_date('Divendres, 9 d’abril de 2021'), '2021-04-09')
        self.assertEqual(page_date('Dimecres, 20 de maig de 2020'), '2020-05-20')
        with self.assertRaises(ValueError):
            parse_detail('<h1>Sol·licitud de llicència</h1>', SOURCE)
        with self.assertRaises(ValueError):
            parse_detail(detail().replace('Aprovació definitiva', 'Informació'), SOURCE)

    def test_crawler_follows_later_pages_and_deduplicates(self):
        adapter = VilanovaDelCamiAyuntamientoAdapter('vilanova-del-cami')
        pages = {
            SOURCE: listing('a.html', '<a href="?page=2">2</a>'),
            SOURCE + '?page=2': listing('b.html', f'<a href="{SOURCE}">1</a>'),
            SOURCE + 'a.html': detail(), SOURCE + 'b.html': detail(),
        }
        def fetch(url, pdf=False):
            if pdf:
                return b'%PDF-fake'
            return pages[url].encode()
        notice = 'Per Acord del Ple de data 12/07/2021, es va aprovar definitivament el Pla de Millora Urbana Sector PMU r8'
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=fetch), patch(
            'municipio.adapters.vilanova_del_cami.subprocess.run'
        ) as run:
            run.return_value.stdout = notice.encode()
            out = Path(directory) / 'projects.jsonl'
            result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len({r['id'] for r in rows}), 2)

    def test_failed_snapshot_preserves_previous_output(self):
        adapter = VilanovaDelCamiAyuntamientoAdapter('vilanova-del-cami')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'projects.jsonl'
            out.write_text('previous\n')
            with patch.object(adapter, '_fetch', return_value=b'<h1>Login</h1>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')
            licenses = Path(directory) / 'licenses.jsonl'
            self.assertEqual(adapter.backfill_licencias(licenses)['status'], 'disabled')
            self.assertEqual(licenses.read_text(), '')


if __name__ == '__main__':
    unittest.main()
