import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.villamanrique_de_la_condesa import (
    DOCUMENT_PREFIX, SOURCE, VillamanriqueDeLaCondesaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def gallery(title, docs):
    return '<section class="gallery link-gallery"><h4 class="gallery-title">' + title + '</h4>' + ''.join(
        f'<h4 class="title-element"><a href="{DOCUMENT_PREFIX}{url}">{label}</a></h4>'
        for url, label in docs) + '</section>'


class InventoryTests(unittest.TestCase):
    def test_groups_documents_and_isolates_instruments(self):
        html = gallery('Proyecto de Actuación - ALMAZARA', [
            ('IND-55-/anuncio.pdf', 'Anuncio admisión a trámite'),
            ('IND-55-/almazara.pdf', 'Proyecto Actuacion ALMAZARA')])
        html += gallery('Proyecto Actuación de Núcleo Avícola parcela 100 polígono 21', [
            ('IND-55-/avicola.pdf', 'Proyecto de Actuación'),
            ('IND-55-/decreto.pdf', 'Resolución admisión a trámite')])
        rows = parse_inventory(html)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertTrue(rows[0]['url'].endswith('/almazara.pdf'))
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertNotIn('fecha_aprob', rows[0])
        self.assertNotIn('fecha_publicacion', rows[0])
        self.assertNotIn('fecha_acuerdo', rows[0])
        self.assertNotIn('lat', rows[0])
        self.assertNotIn('fase', rows[0])
        self.assertEqual(rows[0]['codigo_ine'], '41097')

    def test_excludes_forms_procurement_and_environmental_galleries(self):
        html = ''.join(gallery(title, [('IND-55-/x.pdf', 'Proyecto')]) for title in [
            'Solicitud licencia de obras', 'Licitación de obras', 'Calificación Ambiental - Bar Casa Chica'])
        html += gallery('Proyecto de Actuación - ALOJAMIENTO PARA TEMPOREROS', [
            ('IND-55-/memoria.pdf', 'PAU - LA JUNCOSILA-MEMORIA'),
            ('IND-55-/plano.pdf', ''),
            ('IND-55-/memoria.pdf', 'Duplicado')])
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][1]['titulo'], 'plano.pdf')

    def test_rejects_empty_announcement_only_and_unsafe_documents(self):
        for html in ['', gallery('Proyecto de Actuación - A', [('IND-55-/a.pdf', 'Anuncio')]),
                     '<section class="gallery"><h4 class="gallery-title">Proyecto de Actuación - A</h4>'
                     '<a href="https://example.org/proyecto.pdf">Proyecto</a></section>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_fails_on_pagination(self):
        html = gallery('Proyecto de Actuación - A', [('IND-55-/a.pdf', 'Proyecto')])
        for pager in ['<a rel="next" href="?p=2">2</a>',
                      '<ul class="pagination"><li><a href="?p=2">2</a></li></ul>',
                      '<a href="?page=2">Más</a>']:
            with self.subTest(pager=pager), self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(html + pager)

    def test_duplicate_heading_fails_instead_of_losing_documents(self):
        html = gallery('Proyecto de Actuación - A', [('IND-55-/a.pdf', 'Proyecto')])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            parse_inventory(html * 2)

    def test_manifest_loads_adapter_and_required_safety_settings(self):
        manifest = load_manifest('villamanrique-de-la-condesa')
        self.assertIsInstance(load_portal_adapter(manifest), VillamanriqueDeLaCondesaAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('41097', 'Sevilla'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])

    def test_live_contract_snapshot_and_failure_preserves_previous_output(self):
        adapter = VillamanriqueDeLaCondesaAyuntamientoAdapter('villamanrique-de-la-condesa')
        html = gallery('Proyecto de Actuación - A', [('IND-55-/a.pdf', 'Proyecto')])
        with tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.villamanrique_de_la_condesa.requests.get') as get:
            response = get.return_value
            response.url = SOURCE
            response.headers = {'Content-Type': 'text/html; charset=utf-8'}
            response.text = html
            output = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(output, Path(tmp) / 'state.json')['count'], 1)
            self.assertEqual(json.loads(output.read_text())['titulo'], 'Proyecto de Actuación - A')
            previous = output.read_bytes()
            response.text = '<html>Unavailable</html>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)
            response.url = 'https://example.org/'
            with self.assertRaisesRegex(ValueError, 'redirect'):
                adapter.backfill_proyectos(output)
            self.assertTrue(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['disabled'])
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
