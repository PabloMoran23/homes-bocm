import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ripoll import HEADERS, RipollAyuntamientoAdapter
from municipio.manifest import load_manifest


def inventory(title='1- Projecte de rehabilitació', dates=('01/02/2025', '03/03/2025', '–'), extra=''):
    return ('<table><thead><tr>' + ''.join('<th>' + x + '</th>' for x in HEADERS)
            + '</tr></thead><tbody><tr><td><a href="/wp-content/uploads/projecte.pdf">'
            + title + '</a>' + extra + '</td>'
            + ''.join('<td>' + x + '</td>' for x in dates) + '</tr></tbody></table>')


class RipollTests(unittest.TestCase):
    def test_dates_and_grouped_documents(self):
        row, = RipollAyuntamientoAdapter.parse_projects(inventory(extra='<a href="/planol.pdf">Plànol</a>'))
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_aprob_inicial'], '2025-02-01')
        self.assertEqual(row['fecha_informacion_publica'], '2025-03-03')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob_definitiva'])
        self.assertIsNone(row['lat'])
        self.assertEqual(row['fase'], 'información pública')

    def test_definitive_and_stable_identity(self):
        a, = RipollAyuntamientoAdapter.parse_projects(inventory())
        b, = RipollAyuntamientoAdapter.parse_projects(inventory(title='22- Projecte de rehabilitació', dates=('01/02/2025', '03/03/2025', '05/04/2025')))
        self.assertEqual(a['id'], b['id'])
        self.assertEqual(b['fecha_aprob'], '2025-04-05')
        self.assertEqual(b['fase'], 'aprobación definitiva')

    def test_reject_changed_or_nonproject_sources(self):
        for html in ['<p>Login</p>', inventory(title='Sol·licitud de llicència'),
                     inventory(dates=('31/02/2025', '–', '–')),
                     inventory() + '<a rel="next" href="/page/2">Next</a>',
                     inventory().replace('projecte.pdf', 'form.html'),
                     inventory().replace('</tbody>', '<tr><td>Unknown</td></tr></tbody>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                RipollAyuntamientoAdapter.parse_projects(html)

    def test_backfill_update_and_manifest(self):
        manifest = load_manifest('ripoll')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        adapter = RipollAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, 'fetch_inventory', return_value=(inventory(), {})):
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 1)
                original = output.read_text()
                adapter.update_proyectos(output, Path(directory) / 'state.json')
                self.assertEqual(output.read_text(), original)
            with patch.object(adapter, 'fetch_inventory', return_value=('<p>Login</p>', {})):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
                self.assertEqual(output.read_text(), original)


if __name__ == '__main__':
    unittest.main()
