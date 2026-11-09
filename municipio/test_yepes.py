import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.yepes import SOURCE, YepesAyuntamientoAdapter
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory(date='18-06-2021'):
    cards = ''.join(f'''<div class="card-file"><p class="card-file__title">
    <a href="/fileadmin/{file}.pdf">{title}</a></p>
    <time datetime="{date}"></time><a href="/fileadmin/{file}.pdf">Descargar PDF</a></div>'''
                    for title, file in [('Planos', 'planos'), ('Normas urbanísticas', 'normas')])
    return '<div class="col-6@sm"><h2>Plan de ordenación municipal</h2>' + cards + '</div>'


class YepesTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        html = inventory()
        html = html.replace('</div></div>', '</div>' + inventory().split('</h2>')[1])
        rows = YepesAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][0]['fecha_publicacion'], '2021-06-18')
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon']:
            self.assertIsNone(rows[0][key])
        self.assertFalse(rows[0]['publication_ready'])

    def test_changed_or_incomplete_inventory_fails(self):
        for html in ['', '<a href="/fileadmin/form.pdf">Licencia de obra mayor. Solicitud</a>',
                     inventory() + '<a rel="next" href="?page=2">2</a>',
                     inventory().replace('Normas urbanísticas', 'Solicitud de licencia'),
                     inventory().replace('/fileadmin/normas.pdf', 'https://example.org/normas.pdf'),
                     inventory().replace('card-file__title', 'missing'),
                     inventory('31-02-2021')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                YepesAyuntamientoAdapter.parse_inventory(html)

    def test_missing_date_not_invented(self):
        rows = YepesAyuntamientoAdapter.parse_inventory(inventory().replace('<time datetime="18-06-2021"></time>', ''))
        self.assertTrue(all(d['fecha_publicacion'] is None for d in rows[0]['documentos']))

    def test_live_contract_and_bad_pdf_preserves_output(self):
        adapter = load_portal_adapter(load_manifest('yepes'))
        raw = load_yaml(load_manifest('yepes').path)
        self.assertEqual(raw['codigo_ine'], '45202')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), b'%PDF-test', b'%PDF-test']):
                result = adapter.update_proyectos(out, Path(temp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            row = json.loads(out.read_text())
            self.assertEqual(len(row['documentos'][0]['sha256']), 64)
            previous = out.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), b'<html>error</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(previous, out.read_bytes())
            adapter.backfill_licencias(Path(temp) / 'licencias.jsonl')
            self.assertEqual((Path(temp) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
