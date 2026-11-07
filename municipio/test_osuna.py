"""Offline contract, grouping and pagination regression tests for Osuna."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.osuna import (
    SOURCE, OsunaAyuntamientoAdapter, group_documents, page_url, parse_page,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml

PREFIX = '/export/sites/osuna/es/transparencia/.galleries/IND-53-/'


def fixture(docs, pages=()):
    links = ''.join(f'<a href="{PREFIX}{name}.pdf">{title}</a>' for name, title in docs)
    pagination = ''.join(f'<a href="{page_url(n)}#galleryfiles-1-1">{n}</a>' for n in pages)
    return ('<article class="sg-indicador-trans"><div id="galleryfiles-1-1">'
            + links + pagination + '</div></article>')


class Response:
    def __init__(self, html, url):
        self.text, self.url = html, url

    def raise_for_status(self):
        pass


class OsunaTests(unittest.TestCase):
    def test_group_and_distinguish_instruments(self):
        html = fixture([
            ('a', 'Proyecto Delimitacion PMS Alcazaba fdo'),
            ('b', 'Certificado acuerdo Pleno 28_09_2026.- Aprob. defin. proyecto ampliación Alcazaba'),
            ('c', 'AVANCE ESTUDIO ORDENACIÓN P.I.-7 LAS VEGAS'),
            ('d', '1 INSTRUMENTO PLANEAMIENTO MODIF. NNSS AMPLIACION PI-7'),
            ('e', 'Proyecto Delimitación PMS Ampliación Ermita Santa Ana'),
            ('f', 'MODIFICACION NNSS Ermita Santa Ana'),
            ('g', 'REGISTRO PLANEAMIENTO enero2016'),
            ('h', '3 EAE Innovación Osuna_Anexos inc_MODIF. NN.SS. AMPLIACION PI-7_compressed'),
            ('i', 'ACUERDO PLENO APROBACION INICIAL'),
        ])
        docs, _ = parse_page(html, SOURCE)
        rows, skipped = group_documents(docs + docs)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(rows[0]['documentos']), 2)
        pi7 = next(r for r in rows if r['id'] == 'osuna-plan-nnss-ampliacion-pi7')
        self.assertEqual(len(pi7['documentos']), 2)
        pms = next(r for r in rows if r['id'] == 'osuna-plan-pms-ermita-santa-ana')
        self.assertEqual(len(pms['documentos']), 2)
        self.assertEqual(len(skipped), 2)
        self.assertEqual(rows[0]['codigo_ine'], '41068')
        for row in rows:
            self.assertFalse(row['publication_ready'])
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                self.assertNotIn(key, row)

    def test_no_placeholder(self):
        for html in ('<h1>PGOU</h1>', fixture([])):
            with self.assertRaises(ValueError):
                parse_page(html, SOURCE)
        for title in ('Modelo de solicitud de licencia', 'Solicitud Alcazaba', 'Licitación EDAR Puerto Encina'):
            with self.assertRaises(ValueError):
                group_documents([{'titulo': title, 'url': 'https://example.org/form.pdf'}])

    def test_pagination_and_host_validation(self):
        html = fixture([('a', 'NNSS Ampliación Hospital AI Memoria')], (1, 2, 8))
        _, pages = parse_page(html, SOURCE)
        self.assertEqual(pages, {1, 2, 8})
        with self.assertRaises(ValueError):
            parse_page(html.replace('pagegalleryfiles-1-1=8', 'pagegalleryfiles-9-9=8'), SOURCE)
        html = html.replace(PREFIX + 'a.pdf', 'https://evil.example/a.pdf')
        with self.assertRaises(ValueError):
            parse_page(html, SOURCE)

    def test_live_algorithm_follows_range_and_groups_across_pages(self):
        pages = {
            1: fixture([('a', 'NNSS Ampliación Hospital AI Memoria')], (1, 3)),
            2: fixture([('b', 'NNSS Ampliación Hospital AI Planos 1')], (1, 3)),
            3: fixture([('c', 'AVANCE ESTUDIO ORDENACIÓN P.I.-7 LAS VEGAS')], (1, 3)),
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            with patch('municipio.adapters.osuna.requests.Session') as session:
                session.return_value.__enter__.return_value.get.side_effect = [
                    Response(pages[n], page_url(n)) for n in (1, 2, 3)]
                adapter = OsunaAyuntamientoAdapter('osuna')
                report = adapter.backfill_proyectos(out)
            self.assertEqual(report['source_urls'], [page_url(n) for n in (1, 2, 3)])
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(rows[0]['documentos']), 2)

    def test_repeated_pagination_fails_without_overwriting(self):
        html = fixture([('a', 'NNSS Ampliación Hospital AI Memoria')], (1, 2))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'rows.jsonl'
            out.write_text('previous snapshot')
            with patch('municipio.adapters.osuna.requests.Session') as session:
                session.return_value.__enter__.return_value.get.side_effect = [
                    Response(html, page_url(n)) for n in (1, 2)]
                with self.assertRaises(ValueError):
                    OsunaAyuntamientoAdapter('osuna').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('osuna')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('41068', 'Osuna', 'Sevilla'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, OsunaAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
