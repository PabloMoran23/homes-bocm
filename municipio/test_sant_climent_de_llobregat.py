import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.sant_climent_de_llobregat import (
    SOURCE, SantClimentDeLlobregatAyuntamientoAdapter, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def page(extra='', date='03/03/2022'):
    return f'''<div id="readspeakerPage"><h1>Planejament en tràmit</h1>
    <div class="dinamic"><div class="subtitle" id="marcador1">MPGM al carrer Padró</div>
    <div class="ddbbtext"><p>Aprovació Inicial de la MPGM.</p>
    <a href="/media/repository/ajuntament/Urbanisme/Padro/plan.pdf">MPGM al carrer Padró</a>
    <a href="/media/repository/ajuntament/Urbanisme/Padro/annex.pdf">Annexos</a>
    <a href="/media/repository/ajuntament/Urbanisme/Padro/cert.pdf">Certificat d'Acord del Ple</a>
    <a href="/media/repository/ajuntament/Urbanisme/Padro/dogc.pdf">Publicació DOGC 8618 de {date}.</a>
    </div>{extra}</div><p>Darrera actualització: 02.06.2026</p></div>'''


class InventoryTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        rows = parse_inventory(page())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 4)
        self.assertEqual(row['fecha_publicacion'], '2022-03-03')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha'])
        self.assertEqual(row['codigo_ine'], '08204')
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])

    def test_unrelated_blocks_not_inherited_from_previous_heading(self):
        extra = '''<div class="ddbbtext">Suspensió de llicències
        <a href="/media/repository/ajuntament/Urbanisme/suspensio/cert.pdf">Certificat</a></div>
        <div class="subtitle">PDUM</div><div class="ddbbtext">
        <a href="https://urbanisme.amb.cat/">aquí</a></div>'''
        self.assertEqual(len(parse_inventory(page(extra))), 1)

    def test_no_guessed_dates_or_filename_dates(self):
        row = parse_inventory(page(date='data no indicada'))[0]
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_publicacion_fuente'])

    def test_stable_identity_and_document_deduplication(self):
        original = parse_inventory(page())[0]
        html = page().replace('</p>', '</p><a href="/media/repository/ajuntament/Urbanisme/Padro/annex.pdf">Annex repetit</a>')
        row = parse_inventory(html)[0]
        self.assertEqual(original['id'], row['id'])
        self.assertEqual(len(row['documentos']), 4)

    def test_reject_empty_navigation_changed_stage_and_pagination(self):
        for html in ['<h1>Login</h1>', page().replace('MPGM al carrer Padró</a>', 'Formulari</a>'),
                     page().replace('Aprovació Inicial', 'Documentació'),
                     page('<a href="?page=2" rel="next">2</a>'),
                     page('<div class="pagination"><a href="?page=2">2</a></div>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_adapter_snapshot(self):
        manifest = load_manifest('sant-climent-de-llobregat')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08204')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, SantClimentDeLlobregatAyuntamientoAdapter)
        response = Mock(url=SOURCE, text=page(), content=page().encode())
        with tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.sant_climent_de_llobregat.requests.get', return_value=response):
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '08204')


if __name__ == '__main__':
    unittest.main()
