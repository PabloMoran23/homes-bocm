import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.olias_del_rey import (
    OliasDelReyAyuntamientoAdapter, SOURCE, TITLE, parse_inventory,
)
from municipio.manifest import load_manifest


def package():
    labels = ['Definiciones normas subsidiarias', 'Revisión normas subsidiarias-fichas urbanísticas',
              'Revisión normas subsidiarias memoria', 'Revisión normas subsidiarias-normas urbanísticas',
              'Plano Olías del Rey']
    return '<div><h4>' + TITLE + '</h4><ol>' + ''.join(
        f'<li><a href="/wp-content/uploads/2022/05/{i}.{ext}">{label}</a></li>'
        for i, (label, ext) in enumerate(zip(labels, ['pdf'] * 4 + ['jpg']))
    ) + '</ol></div>'


class InventoryTests(unittest.TestCase):
    def test_one_instrument_and_all_documents_despite_responsive_duplicates(self):
        html = package() * 2 + '<a href="/form.pdf">Modelo 311</a><h4>Noticias</h4>'
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 5)
        self.assertEqual(rows[0]['codigo_ine'], '45122')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(rows[0][field])
        self.assertFalse(rows[0]['publication_ready'])

    def test_rejects_form_and_navigation_only(self):
        for html in ('<a>Normas subsidiarias</a>', '<a href="modelo.pdf">Modelo 311</a>', '<h4>' + TITLE + '</h4>'):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_missing_component_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(package().replace('memoria', 'otro'))

    def test_pagination_fails_instead_of_truncating(self):
        with self.assertRaises(ValueError):
            parse_inventory(package() + '<a rel="next" href="?page=2">Next</a>')

    def test_external_document_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(package().replace('/wp-content/uploads/2022/05/0.pdf', 'https://other.example/0.pdf'))

    def test_conflicting_copies_fail(self):
        with self.assertRaises(ValueError):
            parse_inventory(package() + package().replace('/0.pdf', '/different.pdf'))

    def test_new_document_retained_and_stable_identity(self):
        original = parse_inventory(package())[0]
        expanded = parse_inventory(package().replace('</ol>', '<li><a href="/wp-content/uploads/new.pdf">Anexo</a></li></ol>'))[0]
        self.assertEqual(original['id'], expanded['id'])
        self.assertEqual(len(expanded['documentos']), 6)

    def test_manifest_adapter_refresh_and_disabled_licences(self):
        manifest = load_manifest('olias-del-rey')
        self.assertFalse(manifest.licencias.enabled)
        adapter = OliasDelReyAyuntamientoAdapter(manifest.slug)
        response = Mock(url=SOURCE, text=package())
        with tempfile.TemporaryDirectory() as directory, patch(
                'municipio.adapters.olias_del_rey.requests.get', return_value=response):
            out = Path(directory) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(out, Path(directory) / 'state.json')['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['municipio'], 'Olías del Rey')
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')
