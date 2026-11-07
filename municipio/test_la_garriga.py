import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_garriga import HEADINGS, SOURCES, LaGarrigaAyuntamientoAdapter
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def row(title='', label='Memòria', href='/media/memoria.pdf'):
    return f'<tr><td>{title}</td><td>{label}</td><td><a href="{href}">Enllaç</a></td></tr>'


def page(rows, inventory='en_tramit', extra=''):
    return (f'<h1>{HEADINGS[inventory]}</h1><div id="cos_info1"><table><tbody>'
            + rows + '</tbody></table></div>' + extra)


class LaGarrigaTests(unittest.TestCase):
    def test_documents_grouped_and_dates_do_not_become_approval_dates(self):
        html = page(row('Aprovació inicial del projecte de reparcel·lació UA 6')
                    + row('', 'Publicació BOPB 18-07-2024', '/edict.pdf')
                    + row('', 'Certificat de Ple de data 29.04.2020', '/agreement.pdf'))
        result = LaGarrigaAyuntamientoAdapter.parse_inventory(html, 'en_tramit')
        self.assertEqual(len(result), 1)
        r = result[0]
        self.assertEqual(len(r['documentos']), 3)
        self.assertEqual(r['documentos'][1]['fecha_publicacion'], '2024-07-18')
        self.assertIsNone(r['documentos'][2]['fecha_publicacion'])
        self.assertIsNone(r['fecha_aprob'])
        self.assertIsNone(r['fecha_publicacion'])
        self.assertIsNone(r['lat'])
        self.assertEqual(r['fase'], 'aprobación inicial')
        self.assertEqual(r['codigo_ine'], '08088')

    def test_approved_section_is_not_an_approval_claim(self):
        r = LaGarrigaAyuntamientoAdapter.parse_inventory(page(
            row('Aprovació inicial de la modificació puntual del Pla General')
            + row('Pla Especial de Protecció del Patrimoni', href='/heritage.pdf'),
            'aprovada_definitivament'), 'aprovada_definitivament')
        self.assertEqual(r[0]['fase'], 'aprobación inicial')
        self.assertIsNone(r[1]['fase'])

    def test_administrative_groups_and_forms_excluded_with_their_documents(self):
        rows = (row('Junta de Compensació UA 27') + row('', href='/bases.pdf')
                + row('Sol·licitud de llicència', href='/form.pdf')
                + row('Notícia municipal', href='/news.pdf')
                + row('Projecte de La Sorrera Bike Park', href='/project.pdf'))
        result = LaGarrigaAyuntamientoAdapter.parse_inventory(page(rows), 'en_tramit')
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['documentos']), 1)

    def test_pagination_login_missing_links_or_orphan_rows_fail(self):
        valid = row('Projecte de reparcel·lació')
        for html in ('<h1>Login</h1>', page(row()),
                     page('<tr><td>Projecte</td><td>x</td><td></td></tr>'),
                     page(valid, extra='<a rel="next" href="?page=2">2</a>'),
                     page(valid, extra='<a href="?p=2">Següent</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                LaGarrigaAyuntamientoAdapter.parse_inventory(html, 'en_tramit')

    def test_stable_ids_and_relative_and_legacy_document_links(self):
        html = page(row('Pla Especial de Protecció del Patrimoni', href='/one.pdf')
                    + row('', 'RPUC', 'http://ptop.gencat.net/rpucportal/?codintExp=227937'))
        a = LaGarrigaAyuntamientoAdapter.parse_inventory(html, 'en_tramit')[0]
        b = LaGarrigaAyuntamientoAdapter.parse_inventory(html.replace('/one.pdf', '/renamed.pdf'), 'en_tramit')[0]
        self.assertEqual(a['id'], b['id'])
        self.assertEqual(a['documentos'][0]['url'], 'https://www.lagarriga.cat/one.pdf')
        self.assertEqual(a['documentos'][1]['url'], 'http://ptop.gencat.net/rpucportal/?codintExp=227937')

    def test_manifest_adapter_and_atomic_failure(self):
        adapter = load_portal_adapter(load_manifest('la-garriga'))
        self.assertIsInstance(adapter, LaGarrigaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'projects.jsonl'
            path.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[page(row('Projecte UA6')), '<h1>Login</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[page(row('Projecte UA6')),
                    page(row('Estudi detall UA3', href='/ua3.pdf'), 'aprovada_definitivament')]):
                report = adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(report['rows'], 2)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 2)


if __name__ == '__main__':
    unittest.main()
