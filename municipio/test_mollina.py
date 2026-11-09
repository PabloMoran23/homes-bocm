"""Offline parser and completeness checks for the Mollina PBOM adapter."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.mollina import (
    DOCUMENTS, MollinaAyuntamientoAdapter, municipality_pages, parse_projects,
)
from municipio.manifest import load_manifest, load_yaml

HTML = '''<html><head><title>MOLLINA - PBOM</title><base href="/pbom/"></head>
<body><h1 class="titulo-pbom">PBOM</h1><p>Ayuntamiento de MOLLINA</p>
<section id="informacion"><div class="texto-una-columna">PBOM de Mollina en elaboración.
Normas Subsidiarias de 1999 y adaptación parcial aprobada en 2009.</div></section>
<section class="fase-actual"><strong>FASE 1. PARTICIPACIÓN CIUDADANA</strong>
<blockquote class="descripcion-tramitacion">Se inicia la elaboración del plan.</blockquote></section>
<a href="docs/29072/participacion/plan.pdf">PLAN DE PARTICIPACIÓN PBOM</a>
<a href="docs/29072/participacion/plan.pdf">Documento duplicado</a>
<a href="docs/29072/participacion/encuesta.pdf">ENCUESTA DE PARTICIPACIÓN</a>
<a href="php/documentos/documentos.php?cod_mun=29072">ACCESO A DOCUMENTOS</a>
<div id="faq">Fase 7: Aprobación definitiva. Ejemplo 01/01/2025</div>
<footer>© 2025 Diputación de Málaga</footer></body></html>'''
DOCS = '''<head><base href="/pbom/"></head>
<h2 class="titulo-documentos-municipio">Documentos del PBOM de MOLLINA</h2>
<ul id="fases-tab"><button data-bs-target="#fase-1">Fase 1</button>
<button data-bs-target="#fase-2">Fase 2</button></ul>
<div id="faseTabsContent"><div class="tab-pane active" id="fase-1">
<h3>AVANCE</h3>Esta fase aún no dispone de documentos.</div>
<div class="tab-pane" id="fase-2"><h3>APROBACIÓN INICIAL</h3>
Esta fase aún no dispone de documentos.</div></div>'''


class MollinaTests(unittest.TestCase):
    def test_one_instrument_groups_docs_and_preserves_current_phase(self):
        rows = parse_projects(HTML, DOCS)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '29072')
        self.assertEqual(row['fase'], 'FASE 1. PARTICIPACIÓN CIUDADANA')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], 'https://www.idemap.es/pbom/docs/29072/participacion/plan.pdf')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_hidden_document_tabs_are_also_collected(self):
        docs = DOCS.replace('Esta fase aún no dispone de documentos.</div></div>',
                            '<a href="docs/29072/av/final.pdf">Memoria</a></div></div>')
        row = parse_projects(HTML, docs)[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][-1]['source_url'], DOCUMENTS)
        self.assertEqual(row['documentos'][-1]['seccion'], 'APROBACIÓN INICIAL')

    def test_navigation_forms_and_wrong_municipality_fail(self):
        for html in ('<a>PBOM</a>', HTML.replace('MOLLINA', 'CARTAJIMA'),
                     HTML.replace('PLAN DE PARTICIPACIÓN PBOM', 'Formulario de licencia')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html, DOCS)

    def test_missing_or_incomplete_document_inventory_fails(self):
        for docs in ('Login', DOCS.replace('id="fase-2"', 'id="missing"'),
                     DOCS.replace('Esta fase aún no dispone de documentos.', 'Cargando...')):
            with self.subTest(docs=docs), self.assertRaises(ValueError):
                parse_projects(HTML, docs)

    def test_html_pagination_and_foreign_documents_fail(self):
        for html in (HTML + '<a rel="next">Siguiente</a>',
                     HTML.replace('docs/29072/', 'docs/29025/'),
                     HTML.replace('docs/29072/', 'https://unofficial.example/docs/29072/')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html, DOCS)

    def test_municipality_inventory_follows_all_pages(self):
        pages = []
        def fetch(page):
            pages.append(page)
            return {'total': 2, 'page': page, 'limit': 1, 'municipios': [
                {'cod_mun': '29025', 'nombre': 'CARTAJIMA'} if page == 1 else
                {'cod_mun': '29072', 'nombre': 'MOLLINA'}]}
        self.assertEqual(len(municipality_pages(fetch)), 2)
        self.assertEqual(pages, [1, 2])

    def test_incomplete_repeated_and_changed_inventory_pages_fail(self):
        def fetch(page, mode):
            return {'total': 2 if page == 1 or mode != 'changed' else 3,
                    'page': 1 if mode == 'repeated' else page, 'limit': 1,
                    'municipios': [] if mode == 'missing' else [{'cod_mun': '29072', 'nombre': 'MOLLINA'}]}
        for mode in ('missing', 'repeated', 'changed', 'duplicate'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                municipality_pages(lambda page: fetch(page, mode))

    def test_licences_disabled_and_update_refreshes_snapshot(self):
        adapter = MollinaAyuntamientoAdapter('mollina')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')
            with patch.object(adapter, 'backfill_proyectos', return_value={'count': 1}) as refresh:
                self.assertEqual(adapter.update_proyectos(path, Path(tmp) / 'state.json'), {'count': 1})
                refresh.assert_called_once_with(path)

    def test_manifest_contract(self):
        manifest = load_manifest('mollina')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('29072', 'Mollina', 'Málaga'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
