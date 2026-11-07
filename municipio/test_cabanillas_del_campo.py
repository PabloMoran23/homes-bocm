"""Offline parser and adapter contract tests; no requests to municipal sites."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cabanillas_del_campo import (
    CabanillasDelCampoAyuntamientoAdapter as Adapter, POM, TRANSPARENCY,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

POM_HTML = '''<h1>Plan de Ordenación Municipal</h1>
<section id="modulo-pom"><a href="/wp-content/uploads/2020/09/plan.pdf">Plano</a>
<a href="/wp-content/uploads/2020/09/plan.pdf">Duplicado</a></section>
<section id="modulo-enlace-archivos"><a href="/wp-content/uploads/2020/08/memoria.pdf">Memoria POM 2010</a></section>
<a href="/licencia.pdf">Solicitud de licencia</a>'''
SEDE_HTML = '''<div id="content"><h1>7.1. PLANEAMIENTO Y NORMATIVA URBANÍSTICOS</h1>
<a href="/preview-document/correction">Anuncio de corrección de errores del Texto Refundido de las Normas Urbanísticas del POM. Publicación BOP Nº191 de 07 de octubre de 2026.</a>
<a href="/preview-document/approval">Anuncio de aprobación del Texto Refundido de las Normas Urbanísticas del POM - Noviembre 2025 - Publicación BOP 245 de 23-12-2025</a>
<a href="/preview-document/docm">Anuncio de aprobación del Texto Refundido de las Normas Urbanísticas del POM - Publicación DOCM nº 37 de 24-02-2026</a>
<a href="#" onclick="wicketAjaxGet('session-url')">Planes de desarrollo (10)</a></div>'''


class CabanillasTests(unittest.TestCase):
    def test_grouping_provenance_and_dates(self):
        rows = Adapter.parse_projects(POM_HTML, SEDE_HTML)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '19058')
        self.assertEqual(len(row['documentos']), 5)
        self.assertEqual([d['fecha_publicacion'] for d in row['documentos']],
                         [None, None, '2026-10-07', '2025-12-23', '2026-02-24'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['coverage'], 'partial')
        self.assertEqual({d['source_url'] for d in row['documentos']}, {POM, TRANSPARENCY})
        self.assertFalse(any('licencia' in d['url'] for d in row['documentos']))

    def test_empty_changed_or_paginated_inventory_fails(self):
        for pom, sede in [('', SEDE_HTML), (POM_HTML, ''),
                          ('<h1>Plan de Ordenación Municipal</h1>', SEDE_HTML),
                          (POM_HTML, SEDE_HTML.replace('/preview-document/', '/other/')),
                          (POM_HTML + '<a href="?page=2" rel="next">2</a>', SEDE_HTML),
                          (POM_HTML, SEDE_HTML + '<a href="?page=2">Siguiente</a>'),
                          (POM_HTML, SEDE_HTML + '<div class="pagination">1 2</div>'),
                          (POM_HTML, SEDE_HTML.replace('Texto Refundido', 'Otro instrumento'))]:
            with self.subTest(pom=pom, sede=sede), self.assertRaises(ValueError):
                Adapter.parse_projects(pom, sede)

    def test_refresh_contract_and_failure_preserves_output(self):
        adapter = Adapter('cabanillas-del-campo')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[POM_HTML, SEDE_HTML]):
                self.assertEqual(adapter.update_proyectos(path, Path(directory) / 'state.json')['rows'], 1)
            before = path.read_text()
            self.assertEqual(json.loads(before)['id'], 'cabanillas-del-campo-pom')
            with patch.object(adapter, '_fetch', return_value=''), self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), before)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_manifest_loads(self):
        manifest = load_manifest('cabanillas-del-campo')
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '19058')
        self.assertEqual(raw['provincia'], 'Guadalajara')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])


if __name__ == '__main__':
    unittest.main()
