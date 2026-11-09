import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.carranque import CarranqueAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def section(name, links, extra=''):
    return '<div class="w3eden"><h3>' + name + '</h3>' + ''.join(
        '<div class="link-template-widget"><div class="media-body"><a href="/portal/download/'
        + slug + '/">' + title + '</a></div></div>' for slug, title in links) + extra + '</div>'


def fixture():
    return section('Normas Subsidiarias', [
        ('nnss-completo', 'NNSS – Completo'), ('nnss-anexos', 'NNSS – Anexos'),
        ('ordenanza-1a', 'Ordenanza 1ª'), ('licencia', 'Solicitud de licencia'),
        ('licitacion', 'Anuncio de contratación')]) + section('Planos', [
            ('p01', 'P01 – Clasificación y Calificación de Suelo'),
            ('ortofoto', 'Ortofoto Carranque')], '<ul class="pagination"></ul>')


class CarranqueTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        rows = parse_inventory(fixture() + '<a href="/portal/download/news/">Obras</a>')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '45038')
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual({d['seccion'] for d in row['documentos']}, {'Planos', 'Normas Subsidiarias'})
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])

    def test_fail_closed(self):
        for html in ('', '<h3>Normas Subsidiarias</h3>', fixture().replace('NNSS – Completo', 'Formulario')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_not_truncated(self):
        html = fixture().replace('<ul class="pagination"></ul>', '<ul class="pagination"><li><a href="?page=2">2</a></li></ul>')
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_inventory(html)

    def test_reject_foreign_documents(self):
        with self.assertRaisesRegex(ValueError, 'provenance'):
            parse_inventory(fixture().replace('/portal/download/nnss-completo/', 'https://example.org/portal/download/nnss-completo/'))

    def test_deduplicate(self):
        html = fixture().replace('</h3>', '</h3><div class="link-template-widget"><div class="media-body"><a href="/portal/download/nnss-anexos/">NNSS – Anexos</a></div></div>', 1)
        self.assertEqual(len(parse_inventory(html)[0]['documentos']), 4)

    def test_adapter_and_refresh(self):
        response = Mock(url=SOURCE, text=fixture(), headers={'Content-Type': 'text/html'})
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.carranque.requests.get', return_value=response):
            adapter = CarranqueAyuntamientoAdapter('carranque')
            out, state = Path(tmp) / 'projects.jsonl', Path(tmp) / 'state.json'
            self.assertEqual(adapter.backfill_proyectos(out)['count'], 1)
            first = out.read_text()
            self.assertEqual(adapter.update_proyectos(out, state)['count'], 1)
            self.assertEqual(first, out.read_text())
            self.assertEqual(len(json.loads(first)['documentos']), 4)
            self.assertFalse(state.exists())
            self.assertTrue(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['disabled'])

    def test_manifest(self):
        manifest = load_manifest('carranque')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '45038')
        self.assertEqual(manifest.provincia, 'Toledo')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
