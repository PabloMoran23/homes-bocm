import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.las_ventas_de_retamosa import (
    SOURCE, LasVentasDeRetamosaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def fixture():
    labels = ['NORMAS SUBSIDIARIAS', 'PLANO NNSS ORIGINAL'] + [
        f'{prefix}REPARCELACION POLIGONO 5 - TOMO {n}'
        for prefix in ('', 'PROYECTO ') for n in (1, 2)]
    labels += ['MODELO SOLICITUD OBRA', 'ORDENANZA EDIFICACION', 'MEMORIAS Y NORMATIVA',
               'Anuncio contratación', 'Noticia deportiva']
    return '<title>Obras y Urbanismo de Las Ventas de Retamosa</title>' + ''.join(
        f'<a href="/wp-content/uploads/2024/04/{label.replace(" ", "-")}.pdf">{label}</a>'
        for label in labels)


class ParserTests(unittest.TestCase):
    def test_grouping_and_exclusions(self):
        html = fixture()
        rows = parse_inventory(html + html)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(row['documentos']) for row in rows], [2, 4])
        self.assertTrue(all(row['codigo_ine'] == '45183' for row in rows))
        self.assertTrue(all(d['inventory_url'] == SOURCE for r in rows for d in r['documentos']))

    def test_dates_and_geometry_never_inferred_from_upload_path(self):
        for row in parse_inventory(fixture()):
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])

    def test_fail_closed(self):
        for html in ('<title>Login</title>', fixture().replace('NORMAS SUBSIDIARIAS', 'Formulario').replace('PLANO NNSS ORIGINAL', 'Trámite'),
                     fixture().replace('/wp-content/uploads/', 'https://example.org/'),
                     fixture() + '<a rel="next" href="?page=2">2</a>'):
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_stable_identity_and_preserve_links(self):
        first = parse_inventory(fixture())
        second = parse_inventory(fixture().replace('2024/04', '2025/05'))
        self.assertEqual([r['id'] for r in first], [r['id'] for r in second])
        self.assertIn('/2025/05/', second[0]['url_documento'])

    def test_snapshot_update_and_disabled_licences(self):
        adapter = LasVentasDeRetamosaAyuntamientoAdapter('las-ventas-de-retamosa')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            response = unittest.mock.MagicMock()
            response.url = SOURCE
            response.iter_content.return_value = [fixture().encode()]
            with patch('municipio.adapters.las_ventas_de_retamosa.requests.get') as get:
                get.return_value.__enter__.return_value = response
                adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 2)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('las-ventas-de-retamosa')
        self.assertEqual(manifest.provincia, 'Toledo')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
