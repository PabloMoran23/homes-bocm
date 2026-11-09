"""Parser and adapter contract tests; fixtures reflect the official section layout."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.la_rambla import (
    LaRamblaAyuntamientoAdapter, SECTIONS, SOURCE_URL, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def link(title, filename):
    return f'<p><a href="/wp-content/uploads/2019/03/{filename}.pdf">{title}</a></p>'


def fixture():
    contents = [
        link('Solicitud bonificación IBI', 'formulario')
        + link('Plano Urbanístico (Avance)', 'plano')
        + link('Modificaciones en el PGOU «Carrera Baja»', 'carrera')
        + link('Plan Parcial Sector PP-2A «La Redonda – A»', 'redonda')
        + link('ADAPTACIÓN DE LAS NORMAS SUBSIDIARIAS A LA LOUA – Memoria General', 'memoria')
        + link('ADAPTACIÓN DE LAS NORMAS SUBSIDIARIAS A LA LOUA – Certificado aprobación definitiva', 'certificado')
        + link('Aprobación definitiva modificación NN.SS. en calle Guevara, Valenzuela y Las Flores', 'guevara')
        + link('NN.SS. La Rambla', 'nnss')
        + link('MODIFICACIÓN ESTUDIO DE DETALLE UE-7', 'ue7')
        + link('MODIFICACIÓN ESTUDIO DE DETALLE UE-7', 'ue7-anuncio')
        + link('Admisión a trámite Proyecto de Actuación Olivos Lorente', 'olivos')
        + link('Admisión a trámite Proyecto de Actuación Olivos Lorente', 'olivos-acuerdo'),
        link('I.1. Situación encuadre territorial', 'i1'),
        link('O.3. Ordenación Completa Territorio H1', 'o3'),
        link('Memoria Información', 'pgou-memoria'),
    ]
    return ''.join(f'<div><h3>{section}</h3><div class="et_pb_toggle_content">{content}</div></div>'
                   for section, content in zip(SECTIONS, contents))


class LaRamblaTests(unittest.TestCase):
    def test_groups_documents_and_preserves_provenance(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 8)
        by_title = {r['titulo']: r for r in rows}
        self.assertEqual(len(by_title['PGOU']['documentos']), 3)
        self.assertEqual(len(by_title['MODIFICACIÓN ESTUDIO DE DETALLE UE-7']['documentos']), 2)
        self.assertEqual(len(next(r for r in rows if r['titulo'].startswith('ADAPTACIÓN'))['documentos']), 2)
        olivos = next(r for r in rows if 'Olivos' in r['titulo'])
        self.assertEqual(olivos['tipo'], 'proyecto_actuacion')
        self.assertEqual(len(olivos['documentos']), 2)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '14057')
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['geometry_status'], 'unavailable')
            self.assertFalse(any(k.startswith('fecha') or k in {'lat', 'lon', 'geometry', 'fase'} for k in row))
            for doc in row['documentos']:
                self.assertEqual(doc['inventory_url'], SOURCE_URL)
                self.assertNotIn('formulario', doc['url'])
                self.assertNotIn('/plano.pdf', doc['url'])
        self.assertNotIn('olivos', str(by_title['PGOU']['documentos']))

    def test_extraction_is_dynamic_and_deduplicates_documents(self):
        html = fixture()
        first = parse_inventory(html)
        duplicate = link('MODIFICACIÓN ESTUDIO DE DETALLE UE-7', 'ue7')
        second = parse_inventory(html.replace('</div>', duplicate + '</div>', 1))
        self.assertEqual(first, second)
        changed = parse_inventory(html.replace('Carrera Baja', 'Carrera Alta'))
        self.assertTrue(any('Carrera Alta' in r['titulo'] for r in changed))
        self.assertNotEqual(first[0]['id'], changed[0]['id'])

    def test_rejects_empty_changed_paginated_or_external_sources(self):
        for html in ['', '<h1>Documentos</h1>',
                     fixture().replace('Documentación PGOU', 'Otra sección'),
                     fixture() + '<a rel="next" href="/page/2/">2</a>',
                     fixture() + '<div class="pagination">1 2</div>',
                     fixture() + '<a href="?paged=2">2</a>',
                     fixture().replace('/wp-content/uploads/2019/03/carrera.pdf', 'https://example.org/carrera.pdf')]:
            with self.subTest(html=html[-90:]):
                with self.assertRaises(ValueError):
                    parse_inventory(html)

    def test_adapter_writes_only_after_success_and_incremental_refreshes(self):
        response = Mock(url=SOURCE_URL, content=fixture().encode('utf-8'))
        adapter = LaRamblaAyuntamientoAdapter('la-rambla')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch('municipio.adapters.la_rambla.requests.get', return_value=response):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
                self.assertEqual(result['count'], 8)
                self.assertEqual(len([json.loads(x) for x in out.read_text().splitlines()]), 8)
                previous = out.read_bytes()
                response.content = b'<html>maintenance</html>'
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
                self.assertEqual(out.read_bytes(), previous)
            lic = Path(directory) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(lic)['disabled'])
            self.assertEqual(lic.read_text(), '')

    def test_manifest_resolves_and_disables_unsafe_defaults(self):
        manifest = load_manifest('la-rambla')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '14057')
        self.assertEqual(manifest.provincia, 'Córdoba')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertIsInstance(load_portal_adapter(manifest), LaRamblaAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
