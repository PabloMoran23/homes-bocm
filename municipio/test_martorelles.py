import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.martorelles import MartorellesAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest


def inventory(title='Projecte renovació vials', page_count=3):
    return f'''<div id="readspeakerPage"><h1>Plans, projectes, campanyes, programes</h1>
    <ul class="paginacio"><li>{page_count} pàgines</li></ul>
    <ul class="articlelist"><li class="article-item"><a href="{SOURCE}/work.html">
    <p class="subtitle">{title}</p></a><div class="date">05/11/2026</div></li></ul></div>'''


def detail(title, filenames=('work.pdf',)):
    docs = ''.join(f'<a href="/media/repository/{name}">{name}</a>' for name in filenames)
    return f'''<div id="readspeakerPage"><h1>{title}</h1><div class="ddbbtext">
    <p>Projecte en exposició pública</p>{docs}{docs}</div>
    <span class="updated">Darrera actualització: 09.11.2026</span></div>'''


class MartorellesTests(unittest.TestCase):
    def test_inventory_dates_and_pagination(self):
        rows, pages = Adapter.parse_inventory(inventory())
        self.assertEqual(rows[0]['fecha_publicacion'], '2026-11-05')
        self.assertEqual(pages, {SOURCE, SOURCE+'?pag=2', SOURCE+'?pag=3'})

    def test_unrelated_items_excluded(self):
        for title in ('Pla de mesures antifrau', 'Subvencions i ajuts', 'Sol·licitud de llicència', 'Licitació obres'):
            self.assertEqual(Adapter.parse_inventory(inventory(title))[0], [])

    def test_grouping_and_date_semantics(self):
        entry = Adapter.parse_inventory(inventory())[0][0]
        row = Adapter.parse_detail(detail(entry['titulo'], ('projecte.pdf', 'anunci.pdf')), entry)[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_publicacion'], '2026-11-05')
        for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertEqual(row['documentos'][0]['source_url'], entry['url'])

    def test_school_instruments_separate(self):
        title = "Obres de millora a l'Escola Bressol Municipal Els Cirerers"
        entry = Adapter.parse_inventory(inventory(title))[0][0]
        files = tuple(f'2391_2025_EBM_Obres_{group}_{kind}.pdf' for group in ('Exterior', 'Pati') for kind in ('Anunci', 'Projecte'))
        rows = Adapter.parse_detail(detail(title, files), entry)
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertTrue(all(len(r['documentos']) == 2 for r in rows))

    def test_changed_sources_fail(self):
        for html in ('<h1>Login</h1>', inventory().replace('3 pàgines', '101 pàgines'), inventory().replace('05/11/2026', 'bad')):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        entry = Adapter.parse_inventory(inventory())[0][0]
        for html in (detail('Other project'), detail(entry['titulo'], ())):
            with self.assertRaises(ValueError):
                Adapter.parse_detail(html, entry)

    def test_full_snapshot_and_failure_preserves_previous_output(self):
        adapter = Adapter()
        entry = Adapter.parse_inventory(inventory())[0][0]
        responses = {SOURCE: inventory(), SOURCE+'?pag=2': inventory('Pla de mesures antifrau'),
                     SOURCE+'?pag=3': inventory('Subvencions i ajuts'), entry['url']: detail(entry['titulo'])}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=responses.__getitem__) as fetch:
                result = adapter.update_proyectos(output, Path(directory)/'state.json')
                self.assertEqual(result['rows'], 1)
                self.assertEqual(result['inventory_pages'], 3)
                self.assertEqual(fetch.call_count, 4)
            previous = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=RuntimeError('network failure')):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('martorelles')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'licencias.jsonl'
            self.assertEqual(Adapter().backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
