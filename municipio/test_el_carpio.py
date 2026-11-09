"""Parser checks with small representative municipal markup; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.el_carpio import ElCarpioAyuntamientoAdapter, SOURCE_URL, parse_inventory
from municipio.manifest import load_manifest, load_yaml


ENV = '<a href="/wp-content/uploads/2014/09/environment.pdf">Estudio de Impacto Ambiental Estratégico del Plan General de Ordenación Urbana de El Carpio (BOJA nº 41 de 02-03-2020</a>'
ANN = '<a href="/wp-content/uploads/2014/09/notice.pdf">Anuncio BOJA PGOU 27-1-2020</a>'


def page(body):
    return '<div class="entry-content">' + body + '</div>'


class ElCarpioTests(unittest.TestCase):
    def test_one_instrument_retains_two_documents(self):
        rows = parse_inventory(page(ENV + ANN + ANN))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '14018')
        self.assertEqual(row['provincia'], 'Córdoba')
        self.assertEqual(row['titulo'], 'Plan General de Ordenación Urbana de El Carpio')
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE_URL)
        self.assertTrue(row['documentos'][1]['url'].endswith('/notice.pdf'))
        self.assertEqual(row['geometry_status'], 'unavailable')
        self.assertFalse(row['publication_ready'])
        for field in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, row)

    def test_excludes_forms_procurement_generic_and_unrelated(self):
        extras = '''<a href="https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf">Plan General de Ordenación Urbana (PGOU)</a>
        <a href="/wp-content/uploads/2020/01/form.pdf">Solicitud de licencia urbanística PGOU</a>
        <a href="/wp-content/uploads/2020/01/tender.pdf">Licitación Estudio Ambiental Plan General de Ordenación Urbana de El Carpio</a>
        <a href="/wp-content/uploads/2020/01/mod.pdf">Modificación Estudio Ambiental Plan General de Ordenación Urbana de El Carpio</a>
        <a href="/wp-content/uploads/2020/01/other.pdf">Plan de Emergencia Municipal</a>'''
        self.assertEqual(len(parse_inventory(page(ENV + extras))[0]['documentos']), 1)
        with self.assertRaises(ValueError):
            parse_inventory(page(extras))

    def test_external_document_is_not_evidence(self):
        with self.assertRaises(ValueError):
            parse_inventory(page(ENV.replace('/wp-content/', 'https://example.org/wp-content/')))

    def test_empty_or_changed_content_fails(self):
        for html in ('', '<html>Access denied</html>', page(''), page(ANN)):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_is_not_silently_truncated(self):
        for pagination in ('<a rel="next" href="?page=2">→</a>', '<div class="page-links">2</div>', '<a href="?page=2">Siguiente</a>'):
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                parse_inventory(page(ENV + pagination))

    def test_manifest_and_live_adapter_contract(self):
        manifest = load_manifest('el-carpio')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '14018')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        response = Mock(text=page(ENV + ANN), url=SOURCE_URL)
        with tempfile.TemporaryDirectory() as d, patch('municipio.adapters.el_carpio.requests.get', return_value=response):
            adapter = ElCarpioAyuntamientoAdapter('el-carpio')
            out = Path(d) / 'proyectos.jsonl'
            report = adapter.backfill_proyectos(out)
            self.assertEqual(report['count'], 1)
            self.assertEqual(len(json.loads(out.read_text())['documentos']), 2)
            adapter.update_proyectos(out, Path(d) / 'state.json')
            self.assertEqual(len(out.read_text().splitlines()), 1)
            adapter.backfill_licencias(Path(d) / 'licencias.jsonl')
            self.assertEqual((Path(d) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
