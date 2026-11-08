import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.vilassar_de_dalt import (
    HEADINGS, POUM, PROCESSING, VilassarDeDaltAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def row(title, label, url):
    return f'<tr><td>{title}</td><td>{label}</td><td><a href="{url}">Enllaç</a></td></tr>'


def inventory(source, rows):
    return (f'<h1>{HEADINGS[source]}</h1><table><thead><tr>'
            '<th>Títol</th><th>Document</th><th>Url</th></tr></thead><tbody>'
            + rows + '</tbody></table>'
            "<p>Data i hora de la darrera actualització d'aquest contingut: 29-10-2020 11:43</p>")


class ParserTests(unittest.TestCase):
    def test_groups_instruments_and_preserves_document_provenance(self):
        html = inventory(PROCESSING,
            row('Modificacions puntuals en tràmit', 'Desclassificació sector Matagalls', '/media/m.pdf')
            + row('Pla parcial de Can Reig', 'Memòria', '/media/Can_Reic_aprovacio_definitiva/m.pdf')
            + row('', 'Normativa', '/media/n.pdf')
            + row('Horts de Can Jaumetó', 'Memòria', '/media/j.pdf'))
        rows = parse_inventory(html, PROCESSING)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['titulo'], 'Desclassificació sector Matagalls')
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertEqual(rows[1]['documentos'][1]['source_url'], PROCESSING)
        self.assertTrue(rows[1]['documentos'][1]['url'].startswith('https://www.vilassardedalt.cat/'))
        for item in rows:
            for key in ('fase', 'fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(item[key])
            self.assertEqual(item['source_page_updated_text'], '29-10-2020 11:43')

    def test_poum_annexes_do_not_become_independent_projects(self):
        html = inventory(POUM, row('Normativa', 'Normativa urbanística', '/media/a.pdf')
                         + row('Annexes', 'PPU Can Reig', '/media/b.pdf')
                         + row('', 'PMU Les Sedes', '/media/c.pdf'))
        rows = parse_inventory(html, POUM)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['documentos'][1]['seccion'], 'Annexes')

    def test_ids_survive_document_reordering(self):
        a = row('Can Reig', 'Memòria', '/media/a.pdf')
        b = row('', 'Normativa', '/media/b.pdf')
        first = parse_inventory(inventory(PROCESSING, a + b), PROCESSING)[0]
        second = parse_inventory(inventory(PROCESSING, row('Can Reig', 'Normativa', '/media/b.pdf')
                                           + row('', 'Memòria', '/media/a.pdf')), PROCESSING)[0]
        self.assertEqual(first['id'], second['id'])

    def test_rejects_missing_table_login_or_navigation(self):
        for html in ('<h1>Login</h1>', inventory(POUM, ''), '<a href="/media/a.pdf">POUM</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, POUM)

    def test_rejects_pagination(self):
        html = inventory(POUM, row('Normativa', 'Normativa', '/media/a.pdf'))
        for extra in ('<a rel="next" href="?p=2">Next</a>',
                      '<div class="pagination"><a href="?p=2">2</a></div>',
                      '<a href="?page=2">2</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(html + extra, POUM)

    def test_rejects_malformed_or_untrusted_documents(self):
        for body in (row('', 'Orphan', '/media/a.pdf'),
                     row('Plan', '', '/media/a.pdf'),
                     row('Plan', 'Document', 'https://example.com/a.pdf'),
                     row('Plan', 'Document', '/tramits/form'), '<tr><td>bad</td></tr>'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_inventory(inventory(PROCESSING, body), PROCESSING)

    def test_no_partial_output_on_second_source_failure(self):
        adapter = VilassarDeDaltAyuntamientoAdapter('vilassar-de-dalt')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'rows.jsonl'
            out.write_text('prior snapshot\n')
            with patch.object(adapter, '_fetch', side_effect=[
                inventory(POUM, row('Normativa', 'Normativa', '/media/a.pdf')).encode(),
                RuntimeError('source unavailable')
            ]), self.assertRaises(RuntimeError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'prior snapshot\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('vilassar-de-dalt')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('08214', 'Vilassar de Dalt', 'Barcelona'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = VilassarDeDaltAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
