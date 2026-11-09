"""Offline parser/adapter regression tests; no network or local evidence needed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cazalla_de_la_sierra import (
    CazallaDeLaSierraAyuntamientoAdapter, PBOM_URL, PGOU_URL,
    parse_pgou, parse_pbom, pbom_document_url,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

DOC_URL = 'https://www.cazalladelasierra.es/pbom-documentos/'
PGOU = '''<div class="contentblock1"><div class="galleries">
<section class="gallery"><h4 class="gallery-title">ADAPTACIÓN PARCIAL A LA LOUA DE LAS NNSS MUNICIPALES</h4>
<a href="/export/sites/cazalla/es/transparencia/.galleries/IMG-50-/Memoria.pdf">Memoria</a></section>
<section class="gallery"><h4 class="gallery-title">PLANOS</h4>
<a href="/export/sites/cazalla/es/transparencia/.galleries/IMG-50-/Plano.pdf">Plano</a>
<a href="/export/sites/cazalla/es/transparencia/.galleries/IMG-50-/Plano.pdf">Plano repetido</a>
<a href="https://example.org/fake.pdf">Ajeno</a></section></div></div>'''
PBOM = '''<main id="main">PBOM Cazalla de la Sierra. Estamos en la FASE 3
<time>2024-11-10</time><a href="/pbom-documentos/#fase2">DOCUMENTACIÓN</a>
<a href="/noticia/">Noticia</a></main>'''
DOCS = '''<main id="main"><div class="vc_tta-panel"><h4 class="vc_tta-panel-title">FASE 2</h4>
<a href="/wp-content/uploads/info.pdf">MEDIO FISICO 1</a>
<a href="/wp-content/uploads/info.pdf">MEDIO FISICO 2</a></div>
<div class="vc_tta-panel"><h4 class="vc_tta-panel-title">FASE 3</h4>
<a href="https://cazalladelasierra.es/wp-content/uploads/avance.pdf">Avance</a>
<a href="https://docs.google.com/forms/example">Encuesta</a>
<a href="/modelo-licencia/">Solicitud</a></div></main>'''


class ParserTests(unittest.TestCase):
    def test_grouping_provenance_and_semantics(self):
        pgou = parse_pgou(PGOU)
        pbom = parse_pbom(PBOM, DOCS, DOC_URL)
        self.assertEqual(len(pgou['documentos']), 2)
        self.assertEqual(len(pbom['documentos']), 2)
        self.assertEqual(len(pbom['documentos'][0]['referencias']), 2)
        self.assertEqual(pbom['documentos'][1]['referencias'][0]['seccion'], 'FASE 3')
        self.assertEqual(pbom['documentos'][1]['inventory_url'], DOC_URL)
        self.assertEqual(pbom['fase'], 'Estamos en la FASE 3')
        self.assertEqual(pbom_document_url(PBOM), DOC_URL)
        for row in (pgou, pbom):
            self.assertEqual(row['codigo_ine'], '41032')
            self.assertFalse(row['publication_ready'])
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon'):
                self.assertNotIn(field, row)

    def test_empty_wrong_page_and_pagination_fail(self):
        for html in ('', PGOU.replace('ADAPTACIÓN PARCIAL', 'MODELO LICENCIA'),
                     PGOU + '<a rel="next" href="?page=2">2</a>',
                     PGOU + '<nav class="pagination"><a href="?page=2">2</a></nav>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_pgou(html)
        with self.assertRaises(ValueError):
            parse_pbom(PBOM, '<main id="main">sin documentos</main>', DOC_URL)
        with self.assertRaises(ValueError):
            pbom_document_url('<main id="main"><a href="https://example.org/pbom-documentos/">DOCS</a></main>')

    def test_snapshot_update_and_failure_preserves_output(self):
        adapter = CazallaDeLaSierraAyuntamientoAdapter('cazalla-de-la-sierra')
        pages = {PGOU_URL: PGOU, PBOM_URL: PBOM, DOC_URL: DOCS}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda u: pages[u]):
                result = adapter.backfill_proyectos(out)
                self.assertEqual(result['count'], 2)
                initial = out.read_text()
                adapter.update_proyectos(out, Path(directory) / 'state.json')
                self.assertEqual(out.read_text(), initial)
                pages[DOC_URL] = ''
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
                self.assertEqual(out.read_text(), initial)
            self.assertEqual(len([json.loads(line) for line in initial.splitlines()]), 2)

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('cazalla-de-la-sierra')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '41032')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, CazallaDeLaSierraAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
