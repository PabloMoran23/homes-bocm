import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_llagosta import LaLlagostaAyuntamientoAdapter, agreement_date, parse_detail, parse_inventory

URL = 'https://www.llagosta.cat/ajuntament-seu-electronica/informacio-oficial/exposicio-publica/projecte-test.html'
TITLE = 'Projecte de reforma del Centre Cultural'


def inventory(title=TITLE):
    return f'<main><li class="article-item"><a href="{URL}">{title}</a><div class="date">11/06/2026</div></li></main>'


def detail():
    return f'''<div id="readspeakerPage"><h1>{TITLE}</h1><div class="ddbbtext">La Junta en sessió de data 10 de juny de 2026 va aprovar inicialment el projecte.</div></div><section id="page-documents"><a href="/media/projecte.pdf">Projecte</a><a href="/media/planols.pdf">Plànols</a><a href="/media/projecte.pdf">Duplicat</a></section>'''


class ParserTests(unittest.TestCase):
    def test_grouping_dates_and_semantics(self):
        entries = parse_inventory(inventory().replace('</main>', inventory().removeprefix('<main>')))
        self.assertEqual(len(entries), 1)
        row = parse_detail(detail(), entries[0])
        self.assertEqual(row['fecha_publicacion'], '2026-06-11')
        self.assertEqual(row['fecha_acuerdo'], '2026-06-10')
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['source_url'], URL)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['id'], parse_detail(detail(), entries[0])['id'])

    def test_dates_without_year_not_inferred(self):
        self.assertIsNone(agreement_date('de data 29 de setembre va aprovar inicialment'))
        self.assertEqual(agreement_date('de data 28 d’octubre de 2026'), '2026-10-28')
        self.assertEqual(agreement_date("de data 22 d'abril de 2026"), '2026-04-22')

    def test_reject_unrelated_and_changed_sources(self):
        for title in ['Llicència: formulari', 'Bases subvencions', 'Reglament del Mercat', 'Notícia esportiva']:
            with self.assertRaises(ValueError):
                parse_inventory(inventory(title))
        with self.assertRaises(ValueError):
            parse_inventory('<main>Unavailable</main>')
        entry = parse_inventory(inventory())[0]
        with self.assertRaises(ValueError):
            parse_detail(detail().replace('id="page-documents"', 'id="other"'), entry)
        with self.assertRaises(ValueError):
            parse_detail(detail().replace(TITLE, 'Login'), entry)

    def test_no_silent_pagination(self):
        for link in ['<a rel="next" href="?page=2">2</a>', '<a href="?pagina=2">2</a>', '<div class="pagination">2</div>']:
            with self.assertRaises(ValueError):
                parse_inventory(inventory().replace('</main>', link + '</main>'))

    def test_backfill_and_update_snapshot(self):
        adapter = LaLlagostaAyuntamientoAdapter('la-llagosta')
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            output = Path(tmp) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory(), detail()]):
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 1)
            before = output.read_text()
            with patch.object(adapter, '_fetch', side_effect=[inventory(), detail()]):
                adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(before, output.read_text())
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
