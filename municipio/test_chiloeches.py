import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.chiloeches import ChiloechesAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest


def inventory(extra='', base=True):
    return ('<section><h3>POM</h3>' +
            ('<a href="/wp-content/uploads/MEMORIA.pdf">Memoria</a>' if base else '') +
            '<h4>MODIFICACION PUNTUAL Nº 5</h4>'
            '<a href="/wp-content/uploads/mp5.pdf">MEMORIA</a>'
            '<a href="/wp-content/uploads/mp5.pdf">Modificación 5</a>'
            '<h4>PLANOS INFORMACIÓN</h4>'
            '<a href="/wp-content/uploads/plano.pdf">Plano</a>' + extra + '</section>')


class ChiloechesTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        rows = Adapter.parse_inventory(inventory())
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertEqual(rows[1]['documentos'][0]['titulos_en_indice'], ['MEMORIA', 'Modificación 5'])
        self.assertEqual(rows[1]['documentos'][0]['url_indice'], SOURCE)
        self.assertEqual(rows[0]['codigo_ine'], '19105')
        for row in rows:
            for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'geometry', 'lat', 'lon'):
                self.assertIsNone(row[key])
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in Adapter.parse_inventory(inventory())])

    def test_pagination_rejected(self):
        for link in ('<a href="/urbanismo/page/2/">2</a>', '<a href="?paged=2">2</a>', '<a rel="next" href="/more">Más</a>'):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(inventory() + link)

    def test_changed_or_empty_inventory_rejected(self):
        for html in ('<h1>URBANISMO</h1>', inventory('<h4>OTRO PLAN</h4>'),
                     inventory().replace('<a href="/wp-content/uploads/mp5.pdf">MEMORIA</a>', '').replace('<a href="/wp-content/uploads/mp5.pdf">Modificación 5</a>', '')):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_forms_excluded_and_untrusted_pdf_rejected(self):
        rows = Adapter.parse_inventory(inventory('<a href="/solicitud/">Solicitud licencia</a>'))
        self.assertEqual(sum(len(r['documentos']) for r in rows), 3)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(inventory('<a href="https://example.org/file.pdf">Doc</a>'))

    def test_snapshot_and_disabled_licences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rows.jsonl'
            adapter = Adapter('chiloeches')
            with patch('municipio.adapters.chiloeches.requests.get', return_value=Mock(text=inventory(), url=SOURCE)):
                self.assertEqual(adapter.update_proyectos(path, Path(directory) / 'state')['rows'], 2)
            self.assertEqual(len(path.read_text().splitlines()), 2)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('chiloeches')
        self.assertEqual(manifest.provincia, 'Guadalajara')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.chiloeches:ChiloechesAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
