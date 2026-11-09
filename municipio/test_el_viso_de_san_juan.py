"""Offline parser and contract tests. Live extraction is a separate audit."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.el_viso_de_san_juan import (
    SOURCE, ElVisoDeSanJuanAyuntamientoAdapter, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def fixture(extra=''):
    return '''<div id="wpb-content-root"><h2>PLANOS: Clasificación y Calificación</h2>
    <a href="/pdf/mapa.pdf">Plano 1</a>
    <a href="/pdf/estructural.pdf">Ordenación Estructural<br>Plano 1</a>
    <a href="/pdf/agua.pdf">RED DE AGUA</a>
    <a href="/pdf/normas.pdf">Plan de Ordenación Municipal El Viso de San Juan: NORMAS URBANÍSTICAS</a>
    <a href="/pdf/fichas.pdf">Plan de Ordenación Municipal El Viso de San Juan: FICHAS RESUMEN DE ÁMBITOS URBANÍSTICOS</a>
    ''' + extra + '</div>'


class ParserTests(unittest.TestCase):
    def test_groups_documents_without_inventing_metadata(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '45199')
        self.assertEqual(len(row['documentos']), 5)
        self.assertEqual({d['source_url'] for d in row['documentos']}, {SOURCE})
        self.assertIn('https://elvisodesanjuan.org/pdf/fichas.pdf', [d['url'] for d in row['documentos']])
        for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_duplicate_links_do_not_duplicate_documents(self):
        self.assertEqual(len(parse_inventory(fixture('<a href="/pdf/mapa.pdf">Plano 1</a>'))[0]['documentos']), 5)

    def test_rejects_empty_navigation_and_forms(self):
        for html in ['', '<nav>Plan de Ordenación Municipal El Viso de San Juan</nav>',
                     '<div id="wpb-content-root"><a href="/pdf/licencia.pdf">Solicitud de licencia</a></div>',
                     fixture().replace('NORMAS URBANÍSTICAS', 'Solicitud de licencia')]:
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_does_not_silently_truncate_pagination_or_unknown_documents(self):
        for extra in ['<a rel="next" href="/otra/">Siguiente</a>', '<div class="pagination"></div>',
                      '<a href="?paged=2">2</a>', '<a href="/pdf/nuevo.pdf">Otro plan</a>',
                      '<a href="https://example.org/pdf/mapa.pdf">Plano 2</a>']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_inventory(fixture(extra))

    def test_rejects_other_municipality_and_redirect(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture().replace('El Viso de San Juan', 'El Viso'))
        with self.assertRaises(ValueError):
            parse_inventory(fixture(), 'https://elvisodesanjuan.org/')

    def test_manifest_and_live_method_contract(self):
        manifest = load_manifest('el-viso-de-san-juan')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('45199', 'Toledo'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, ElVisoDeSanJuanAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch('municipio.adapters.el_viso_de_san_juan.requests.Session') as session:
                response = session.return_value.__enter__.return_value.get.return_value
                response.headers = {'Content-Type': 'text/html'}
                response.text, response.url = fixture(), SOURCE
                report = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(report['count'], 1)
            self.assertEqual(json.loads(output.read_text())['id'], 'el-viso-de-san-juan-pom')
            adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
