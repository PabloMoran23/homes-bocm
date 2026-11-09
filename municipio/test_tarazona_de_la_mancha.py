import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.tarazona_de_la_mancha import (
    SOURCE, TarazonaDeLaManchaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def page(*titles):
    links = ''.join(f'<ul><li>{heading}</li></ul><p><a href="http://tarazonadelamancha.es/wp-content/uploads/{filename}.pdf">{label}</a></p>'
                    for heading, label, filename in titles)
    return '<main><h1>Normativa Municipal</h1>' + links + '</main>'


class InventoryTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        html = page(
            ('Plano informativo 1998', 'Revisión NNSS_Modif. Puntual año 1998_Plano 0.4', '1998a'),
            ('Plano informativo 1998', 'Revisión NNSS_Modif. Puntual año 1998_Plano 0.5', '1998b'),
            ('1999', 'Revisión Normas Subsidiarias de Planeamiento. Modificación Puntual año 1999', '1999'),
            ('Capítulo III', 'Revisión Normas Subsidiarias de Planeamiento. Volumen IV. Capítulo III', 'III'),
            ('Capítulo VIII Parte III', 'Revisión Normas Subsidiarias de Planeamiento. Volumen IV. Capítulo III', 'III'),
        )
        rows = parse_inventory(html)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1, 1])
        self.assertEqual(len(rows[2]['documentos'][0]['rotulos_inventario']), 2)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '02073')
            for key in ['fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase']:
                self.assertIsNone(row[key])
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in parse_inventory(html)])

    def test_forms_and_news_are_not_records(self):
        with self.assertRaises(ValueError):
            parse_inventory(page(('Solicitud', 'Solicitud licencia de obra', 'solicitud')))

    def test_reject_changed_inventory(self):
        for html in ['<html>Error</html>', '<main><h1>Normativa Municipal</h1><a rel="next">2</a></main>',
                     '<main><h1>Normativa Municipal</h1><a href="?paged=2">2</a></main>',
                     page(('Plan', 'Revisión nuevo instrumento desconocido', 'unknown'))]:
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_foreign_document_rejected(self):
        html = page(('1999', 'Revisión NNSS Modif. 1999', '1999'))
        with self.assertRaises(ValueError):
            parse_inventory(html.replace('http://tarazonadelamancha.es', 'https://other.example'))

    def test_manifest_and_live_method_with_fixture(self):
        manifest = load_manifest('tarazona-de-la-mancha')
        self.assertEqual(manifest.provincia, 'Albacete')
        self.assertFalse(manifest.licencias.enabled)
        adapter = TarazonaDeLaManchaAyuntamientoAdapter(manifest.slug)
        response = Mock(url=SOURCE, text=page(('1999', 'Revisión NNSS Modif. 1999', '1999')))
        with tempfile.TemporaryDirectory() as directory, patch(
            'municipio.adapters.tarazona_de_la_mancha.requests.get', return_value=response
        ):
            path = Path(directory) / 'proyectos.jsonl'
            result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(path.read_text())['codigo_ine'], '02073')
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
