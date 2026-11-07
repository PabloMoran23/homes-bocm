"""Offline structural fixtures; no network or local evidence dependency."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.la_puebla_del_rio import (
    DOCUMENT_PATH, SOURCE, LaPueblaDelRioAyuntamientoAdapter, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def link(name, title='Memoria'):
    return f'<a href="{DOCUMENT_PATH}{name}.pdf">{title}</a>'


def fixture(page=1, extra=''):
    return f'''<article class="documentacion">
    <h3>50.1. ADAPTACIÓN PARCIAL DEL PLANEAMIENTO</h3>{link('adaptacion')}
    <h3>Memoria y Ordenanzas</h3>{link('ordenanzas')}
    <h3>50.2. NORMAS SUBSIDIARIAS</h3>{link('normas')}
    <h3>50.3. ITACA INVENTARIO TOPONIMICO</h3>{link('ITACA')}
    <h3>50.4 AVANCE PLAN GENERAL PUEBLA DEL RÍO 2022</h3>
    <h3>Información pública del Avance del PGOM y del POU de La Puebla del Río</h3>
    <section class="gallery"><h4 class="gallery-title">AVANCE POU</h4>
    {link('Avance-POU/1-Memoria/0-Resumen-Ejecutivo')}
    {link('Avance-POU/2-Cartografia/mapa-' + str(page))}
    <a class="currentpagelink" href="?pagegalleryfiles-1-2={page}">{page}</a>
    <a class="nextpagelink" href="?pagegalleryfiles-1-2=2#galleryfiles-1-2">2</a>
    </section>
    <section class="gallery"><h4 class="gallery-title">AVANCE PGOM</h4>
    {link('Avance-PGOM/1-Memoria/0-Resumen-ejecutivo')}</section>
    <section class="gallery"><h4 class="gallery-title">PGOM-DOC_PREVIO_APROB_INICIAL</h4>
    {link('MEMORIA-JUSTIFICATIVA')}</section>{extra}</article>'''


class ParserTests(unittest.TestCase):
    def test_instruments_and_versions_are_grouped_without_itaca(self):
        groups, pages = parse_page(fixture(extra='<a href="/licencias">Solicitud de licencia</a>'))
        self.assertEqual(set(groups), {'adaptacion-parcial', 'normas-subsidiarias', 'pou', 'pgom'})
        self.assertEqual(len(groups['adaptacion-parcial']['documentos']), 2)
        self.assertEqual(len(groups['normas-subsidiarias']['documentos']), 1)
        docs = list(groups['pgom']['documentos'].values())
        self.assertEqual({d['version_documental'] for d in docs}, {'avance', 'documento previo a aprobación inicial'})
        self.assertEqual(len(pages), 1)
        self.assertNotIn('ITACA.pdf', json.dumps(groups))

    def test_pagination_must_be_active(self):
        with self.assertRaisesRegex(ValueError, 'not active'):
            parse_page(fixture(), SOURCE + '?pagegalleryfiles-1-2=2')

    def test_missing_inventory_empty_and_unclassified_fail(self):
        for html in ('<html>Error</html>', '<article class="documentacion"></article>',
                     fixture(extra=link('unknown-new-instrument'))):
            with self.subTest(html=html[-100:]), self.assertRaises(ValueError):
                parse_page(html)

    def test_pagination_and_document_host_checks(self):
        html = fixture(extra='<a href="https://example.org/file.pdf">Otro plan</a>')
        groups, _ = parse_page(html)
        self.assertNotIn('example.org', json.dumps(groups))
        with self.assertRaisesRegex(ValueError, 'pagination target'):
            parse_page(fixture(extra='<a href="https://example.org/?pagegalleryfiles-1-2=9">9</a>'))

    @patch('municipio.adapters.la_puebla_del_rio.requests.get')
    def test_full_refresh_follows_pages_and_deduplicates(self, get):
        def response(url, **kwargs):
            class Response:
                text = fixture(2 if '?' in url else 1)
                def raise_for_status(self):
                    pass
            r = Response()
            r.url = url
            return r
        get.side_effect = response
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            adapter = LaPueblaDelRioAyuntamientoAdapter('la-puebla-del-rio')
            result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['count'], 4)
            self.assertEqual(get.call_count, 2)
            pou = next(r for r in rows if r['id'].endswith('-pou'))
            self.assertEqual(len(pou['documentos']), 3)
            for row in rows:
                self.assertFalse(row['publication_ready'])
                self.assertEqual(row['codigo_ine'], '41079')
                for absent in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
                    self.assertNotIn(absent, row)

    @patch('municipio.adapters.la_puebla_del_rio.requests.get')
    def test_failed_pagination_preserves_previous_output(self, get):
        class Response:
            url = SOURCE
            text = fixture()
            def raise_for_status(self):
                pass
        get.side_effect = [Response(), RuntimeError('Network failure')]
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous result\n')
            with self.assertRaises(RuntimeError):
                LaPueblaDelRioAyuntamientoAdapter('la-puebla-del-rio').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous result\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('la-puebla-del-rio')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '41079')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = LaPueblaDelRioAyuntamientoAdapter(manifest.slug).backfill_licencias(out)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
