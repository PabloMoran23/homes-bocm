import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.montalban_de_cordoba import (
    SOURCE, MontalbanDeCordobaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def link(title, file):
    return f'<a href="/wp-content/uploads/2018/10/{file}.pdf">{title}</a>'


def section(title, content):
    return f'<div><h3>{title}</h3></div><div class="carpetas_doc">{content}</div>'


class InventoryTests(unittest.TestCase):
    def test_group_project_parts_and_keep_documents(self):
        html = section('Proyectos',
                       link('PFEA 2018. Urbanización Calle Empedrada 2ª Fase Segunda Parte Planos', 'plans') +
                       link('PFEA 2018. Urbanización Calle Empedrada 2ª Fase Primera Parte', 'memory') +
                       link('PFEA 2018. Camino Senda Gitanos 3ª Fase', 'road'))
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '14040')
            self.assertFalse(row['publication_ready'])
            self.assertFalse(set(row) & {'fecha', 'fecha_aprob', 'fecha_acuerdo',
                                          'fecha_publicacion', 'lat', 'lon', 'fase'})

    def test_separate_innovation_and_deduplicate_fragmented_anchor(self):
        html = section('Normas subsidiarias', link('Normas subsidiarias de planeamiento', 'norms') +
                       link('Plano Estructura general', 'map') +
                       link('Innovación-modificación puntual del PGOU', 'innovation'))
        html += section('Plan parcial huertos del infante',
                        link('Ordenanzas P.P.', 'infante') + link('Huertos Infante', 'infante') +
                        link('Plano Ordenacion', 'infante-map'))
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2, 2])
        self.assertEqual(rows[2]['documentos'][0]['etiquetas'], ['Ordenanzas P.P.', 'Huertos Infante'])
        self.assertTrue(all('infante' not in d['url'] for d in rows[1]['documentos']))

    def test_exclude_base_maps_and_forms(self):
        html = section('Infraestructuras', link('Abastecimiento agua', 'water'))
        html += '<a href="form.pdf">Solicitud de licencia de obras</a>'
        with self.assertRaises(ValueError):
            parse_inventory(html)

    def test_fail_closed_on_empty_pagination_and_foreign_document(self):
        valid = section('Plan parcial los Lucas', link('Ordenanzas P.P. Los Lucas', 'lucas'))
        for html in ['', valid + '<a rel="next" href="?paged=2">Más</a>',
                     valid + '<div class="page-links"><a href="/2/">2</a></div>',
                     section('Nuevo bloque', link('Solicitud', 'form')),
                     valid.replace('/wp-content/uploads/', 'https://example.org/')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_live_method_write(self):
        manifest_path = Path(__file__).resolve().parents[1] / 'data/municipios/montalban-de-cordoba/manifest.yaml'
        raw = load_yaml(manifest_path)
        self.assertEqual(raw['codigo_ine'], '14040')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        manifest = load_manifest(manifest_path)
        adapter = MontalbanDeCordobaAyuntamientoAdapter(manifest.slug)
        response = Mock(url=SOURCE, text=section('Plan parcial los Lucas', link('Ordenanzas', 'lucas')))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch('municipio.adapters.montalban_de_cordoba.requests.get', return_value=response):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(out.read_text())['municipio'], 'Montalbán de Córdoba')
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
