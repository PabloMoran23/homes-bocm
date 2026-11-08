"""Offline parser and traversal regressions; no external services."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cisterniga import (
    SOURCE, CisternigaAyuntamientoAdapter, group_records, parse_detail,
    parse_inventory, selected,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(title, path='/doc/urbanismo/plan', next_page=None):
    pager = (f'<nav class="pager"><li class="pager__item--next"><a href="?page={next_page}">Next</a></li></nav>'
             if next_page is not None else '')
    return f'<main><article class="node--type-documents"><h2><a href="{path}">{title}</a></h2></article>{pager}</main>'


def detail(title, filename='plan.pdf', body=''):
    return (f'<main><h1>{title}</h1><div id="block-mipueblo-content">'
            f'<div class="field--name-body">{body}</div>'
            '<div class="field--name-field-date-range"><time datetime="2024-02-21T12:00:00Z">21 de Febrero de 2024</time></div>'
            f'<div class="field--name-field-attached-files"><a href="/sites/default/files/documents/{filename}">{filename}</a></div>'
            '</div></main>')


class CisternigaTests(unittest.TestCase):
    def test_selection_excludes_forms_and_applications(self):
        for title in ['08 - Licencia Obra Mayor', 'Solicitud licencia ambiental',
                      'Información pública relativa a la solicitud de autorización de uso excepcional',
                      'Información pública relativa al expediente 1778/2025 incoación declaración de ruina ordinaria',
                      'Anuncio de licitación', 'Fiestas patronales']:
            self.assertFalse(selected(title), title)
        self.assertTrue(selected('Proyecto Normalización de fincas relativo a la finca registral 775'))
        self.assertTrue(selected('Aprobación inicial del Proyecto de Actuación del Sector 10'))

    def test_grouping_and_document_isolation(self):
        titles = ['Documentos Modificación Puntual Nº1 - Plan Parcial Sector 10_ Parte 2',
                  'Documentos Modificación Puntual Nº1 - Plan Parcial Sector 10_ Parte 1',
                  'APROBACIÓN DEFINITIVA PLAN PARCIAL SECTOR 13 DEL SUD DEL PGOU DE LA CISTÉRNIGA.-',
                  'APROBACIÓN DEFINITIVA PLAN PARCIAL SECTOR 13 DEL SUD DEL PGOU DE LA CISTÉRNIGA',
                  'Proyecto de Actuación del Sector 10']
        details = [parse_detail(detail(t, f'{i}.pdf'), f'https://www.lacisterniga.es/doc/{i}', t)
                   for i, t in enumerate(titles)]
        rows = group_records(details)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1])
        self.assertEqual([len(r['fichas']) for r in rows], [2, 2, 1])
        self.assertEqual(len({r['id'] for r in rows}), 3)
        for row in rows:
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['lat'])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['fichas'][0]['source_date_values'], ['2024-02-21T12:00:00Z'])

    def test_empty_or_changed_source_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<main>Empty</main>', SOURCE)
        with self.assertRaises(ValueError):
            parse_detail(detail('Other plan'), SOURCE, 'Expected plan')
        with self.assertRaises(ValueError):
            parse_detail('<main><h1>Plan</h1><div id="block-mipueblo-content"></div></main>', SOURCE, 'Plan')
        with self.assertRaises(ValueError):
            group_records([])
        with self.assertRaises(ValueError):
            parse_inventory(inventory('Proyecto', 'https://example.org/doc/x'), SOURCE)
        with self.assertRaises(ValueError):
            parse_inventory(inventory('Proyecto', next_page=2), SOURCE)

    def test_all_pages_traversed_before_writing(self):
        adapter = CisternigaAyuntamientoAdapter('cisterniga')
        title = 'Proyecto Normalización de fincas relativo a la finca registral 775'
        pages = [inventory('08 - Licencia Obra Mayor', next_page=1),
                 inventory('Solicitud', next_page=2), inventory(title), detail(title)]
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages) as fetch:
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['inventory_pages'], 3)
            self.assertEqual(result['count'], 1)
            self.assertEqual(fetch.call_count, 4)
            self.assertEqual(json.loads(output.read_text())['codigo_ine'], '47052')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=RuntimeError('HTTP failure')):
            output = Path(tmp) / 'proyectos.jsonl'
            with self.assertRaises(RuntimeError):
                adapter.backfill_proyectos(output)
            self.assertFalse(output.exists())

    def test_manifest_contract(self):
        manifest = load_manifest('cisterniga')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('47052', 'Valladolid'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with self.assertRaises(RuntimeError):
            CisternigaAyuntamientoAdapter('cisterniga').backfill_licencias(Path('/tmp/unused-cisterniga'))


if __name__ == '__main__':
    unittest.main()
