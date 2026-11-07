"""Offline parser and adapter contract checks (no dependency on local evidence)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ansoain import (
    AnsoainAyuntamientoAdapter, INVENTORIES, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

PDF = 'https://www.ansoain.es/wp-content/uploads/'


def page(body):
    return '<main><div class="contenido content">' + body + '</div></main>'


def part(number):
    return f'<a href="{PDF}pmus{number}.pdf">Parte {number}</a>'


def section(anchor='nuevo-peau', title='Plan Especial de Actuación Urbana parcela 240'):
    return f'''<div class="bloque"><a class="bloque-tab" href="#{anchor}">{title}</a>
    <div id="{anchor}"><p>Sesión 8 de junio; aportaciones hasta 22 de junio.</p>
    <a href="{PDF}peau.pdf">Plan de participación</a>
    <a href="{PDF}peau.pdf">Descargar de nuevo</a>
    <a href="{PDF}anexo.pdf">Anexo</a></div></div>'''


class ParserTests(unittest.TestCase):
    def test_multipart_grouping_and_exclusion(self):
        html = page('<p>PMUS: Plan Movilidad Urbana Sostenible 2025 ' + part(1) + part(2) +
                    f'</p><p><a href="{PDF}licencia.pdf">Solicitud de licencia de obras</a></p>' +
                    '<p>Plan infraestructura verde de Ansoáin: ' + part(1) + part(2) + '</p>' +
                    f'<p><a href="{PDF}politica.pdf">Plan de igualdad</a></p>')
        rows = parse_inventory(html, INVENTORIES['planes'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['titulo'], 'PMUS: Plan Movilidad Urbana Sostenible 2025')
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[0]['codigo_ine'], '31016')
        self.assertEqual(rows[0]['documentos'][0]['source_url'], INVENTORIES['planes'])
        self.assertFalse(rows[0]['publication_ready'])

    def test_dynamic_peau_and_date_semantics(self):
        html = page(section() + section('otro', 'PEAU modificación de usos') +
                    section('presupuesto', 'Presupuestos participativos 2026'))
        rows = parse_inventory(html, INVENTORIES['participacion'])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)  # repeated download is not an instrument
        self.assertTrue(rows[0]['url'].endswith('#nuevo-peau'))
        self.assertEqual(rows[0]['fase'], 'participacion_previa_segun_inventario')
        for row in rows:
            self.assertFalse({'fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob',
                              'lat', 'lon', 'geometry'} & row.keys())
        repeated = parse_inventory(html, INVENTORIES['participacion'])
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in repeated])

    def test_pagination_and_empty_fail_closed(self):
        for html in [page(''), '<html>Service unavailable</html>',
                     page(section() + '<a href="?page=2">2</a>'),
                     page(section() + '<a rel="next" href="/more/">Más</a>'),
                     page(section() + '<nav class="pagination">2</nav>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, INVENTORIES['participacion'])

    def test_missing_or_untrusted_documents_and_parts(self):
        bad = [page('<p>PMUS ' + part(2) + '</p>'),
               page('<p>PMUS ' + part(1) + part(3) + '</p>'),
               page('<p>Plan infraestructura verde: sin documentos</p>')]
        for html in bad:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, INVENTORIES['planes'])
        for html in [page(section().replace('https://www.ansoain.es', 'https://untrusted.example')),
                     page(section().replace('id="nuevo-peau"', 'id="absent"'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, INVENTORIES['participacion'])

    def test_manifest_loading_and_disabled_licences(self):
        raw = load_yaml(Path('data/municipios/ansoain/manifest.yaml'))
        self.assertEqual(raw['codigo_ine'], '31016')
        self.assertEqual(raw['provincia'], 'Navarra')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        adapter = load_portal_adapter(load_manifest('ansoain'))
        self.assertIsInstance(adapter, AnsoainAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'licencias.jsonl'
            with patch('municipio.adapters.ansoain.requests.get') as get:
                result = adapter.update_licencias(target, Path(directory) / 'state.json')
            get.assert_not_called()
            self.assertTrue(result['disabled'])
            self.assertEqual(target.read_text(), '')

    def test_failed_extraction_preserves_snapshot(self):
        adapter = AnsoainAyuntamientoAdapter('ansoain')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'proyectos.jsonl'
            original = json.dumps({'id': 'prior-snapshot'}) + '\n'
            target.write_text(original)
            with patch.object(adapter, '_fetch', side_effect=ValueError('source failed')):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(target, Path(directory) / 'state.json')
            self.assertEqual(target.read_text(), original)


if __name__ == '__main__':
    unittest.main()
