"""Offline parser/transport regression tests; live evidence is kept separately."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.el_cuervo_de_sevilla import (
    DOCUMENT_ROOT, IMAGE_ROOT, SOURCE, ElCuervoDeSevillaAyuntamientoAdapter,
    build_record, inventory_url, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def page(*files, links=()):
    body = '<h2>50. Está publicado el Plan General (PGOU)</h2>'
    for section, filename, title in files:
        body += f'<a href="{DOCUMENT_ROOT}{section}/{filename}.pdf">{title}</a>'
    for url in links:
        body += f'<a href="{url}">Siguiente</a>'
    return body


WRITTEN = ('documentacion-escrita', 'Libro1', 'Libro primero: De las normas subsidiarias')
ENVIRONMENT = ('estudio-impacto-ambiental', 'EIA1', 'Parte 1: Capítulos 1 a 3')


class ElCuervoTests(unittest.TestCase):
    def test_parser_excludes_unrelated_and_preserves_provenance(self):
        html = page(WRITTEN, ENVIRONMENT)
        html += f'<a href="{IMAGE_ROOT}planos-ordenacion/plano.gif">Clasificación del suelo</a>'
        html += f'<a href="{IMAGE_ROOT}planos-informacion/info.gif">Información</a>'
        html += '<a href="/solicitud-licencia.pdf">Licencia</a>'
        html += '<a href="https://elsewhere.invalid' + DOCUMENT_ROOT + 'fake.pdf">Proyecto</a>'
        docs, links = parse_page(html, SOURCE)
        self.assertEqual(len(docs), 4)
        self.assertEqual(links, [])
        record = build_record(docs, [SOURCE])
        self.assertEqual(record['codigo_ine'], '41903')
        self.assertEqual(len(record['documentos']), 4)
        self.assertEqual(record['documentos'][0]['source_pages'], [SOURCE])
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(record[key])
        self.assertNotIn('fase', record)
        self.assertFalse(record['publication_ready'])

    def test_pagination_and_grouping(self):
        second = SOURCE + '?pagegalleryfiles-3-1=2'
        third = SOURCE + '?pagegalleryfiles-4-1=2'
        bodies = {
            SOURCE: page(WRITTEN, ENVIRONMENT, links=(second + '#galleryfiles-3-1',)),
            second: page(WRITTEN, ('planos-ordenacion', 'p2', 'Plano 2'), links=(third, SOURCE)),
            third: page(WRITTEN, ('planos-informacion', 'p3', 'Plano 3')),
        }
        def get(url, **kwargs):
            return Mock(url=url, text=bodies[url], raise_for_status=Mock())
        with TemporaryDirectory() as folder, patch('municipio.adapters.el_cuervo_de_sevilla.requests.Session') as session:
            session.return_value.__enter__.return_value.get.side_effect = get
            adapter = ElCuervoDeSevillaAyuntamientoAdapter()
            output = Path(folder) / 'records.jsonl'
            stats = adapter.update_proyectos(output, Path(folder) / 'state.json')
            records = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(stats['documents'], 4)
            self.assertEqual(set(stats['source_urls']), set(bodies))
            repeated = next(d for d in records[0]['documentos'] if d['titulo'].startswith('Libro'))
            self.assertEqual(len(repeated['source_pages']), 3)

    def test_changed_or_empty_source_fails(self):
        for html in ('<h2>Error</h2>', '<h2>50. PGOU</h2><a href="/licencia.pdf">Licencia</a>'):
            with self.assertRaises(ValueError):
                parse_page(html, SOURCE)
        docs, _ = parse_page(page(WRITTEN), SOURCE)
        with self.assertRaises(ValueError):
            build_record(docs, [SOURCE])

    def test_failed_later_page_does_not_write_partial_result(self):
        second = SOURCE + '?pagegalleryfiles-3-1=2'
        response = Mock(url=SOURCE, text=page(WRITTEN, ENVIRONMENT, links=(second,)))
        with TemporaryDirectory() as folder, patch('municipio.adapters.el_cuervo_de_sevilla.requests.Session') as session:
            session.return_value.__enter__.return_value.get.side_effect = [response, RuntimeError('HTTP failure')]
            output = Path(folder) / 'result.jsonl'
            output.write_text('previous snapshot')
            with self.assertRaises(RuntimeError):
                ElCuervoDeSevillaAyuntamientoAdapter().backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_pagination_validation(self):
        self.assertEqual(inventory_url(SOURCE.rstrip('/') + '?pagegalleryfiles-3-1=2#gallery'), SOURCE + '?pagegalleryfiles-3-1=2')
        for url in (SOURCE + '?pagegalleryfiles-3-1=abc', SOURCE + '?pagegallery=2',
                    'https://elsewhere.invalid/?pagegalleryfiles-3-1=2'):
            with self.assertRaises(ValueError):
                inventory_url(url)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('el-cuervo-de-sevilla')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '41903')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as folder:
            output = Path(folder) / 'licencias.jsonl'
            result = ElCuervoDeSevillaAyuntamientoAdapter().backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
