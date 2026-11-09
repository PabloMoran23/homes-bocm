"""Offline parser and adapter contract tests; no live fixtures required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.paradas import (
    ParadasAyuntamientoAdapter, SOURCE_URL, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def block(title, name, section='DOCUMENTO TÉCNICO'):
    return (f'<div class="contentblock"><h3>{title}</h3>'
            f'<h4 class="gallery-title">{section}</h4><h4><a href="/export/sites/'
            f'paradas/es/transparencia/.galleries/IND-53-/{name}.pdf">{name}</a></h4></div>')


def page(*blocks):
    return '<article class="sg-indicador-trans">' + ''.join(blocks) + '</article>'


class ParadasTests(unittest.TestCase):
    def test_group_documents_and_duplicate_instrument(self):
        a = 'MODIFICACIÓN NÚMERO 3 DEL PLAN PARCIAL P.I.1 LOS ALBEROS'
        b = 'MODIFICACIÓN NUMERO 3 DEL PLAN PARCIAL P.I.1. LOS ALBEROS'
        rows = parse_inventory(page(block(a, 'memoria'), block(b, 'acuerdo'),
                                    block('MODIFICACIÓN NUMERO 2 DEL PLAN PARCIAL', 'memoria')))
        self.assertEqual(len(rows), 2)
        self.assertEqual([d['titulo'] for d in rows[0]['documentos']], ['memoria', 'acuerdo'])
        self.assertEqual(len(rows[0]['titulos_fuente']), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[0]['id'], parse_inventory(page(block(b, 'acuerdo')))[0]['id'])

    def test_excludes_forms_news_and_procurement(self):
        rows = parse_inventory(page(block('ESTUDIO DE DETALLE EN CALLE RAFAEL ALBERTI', 'estudio'),
                                    block('Modelo de licencia de obras', 'modelo'),
                                    block('Licitación de obras', 'licitacion'),
                                    block('Noticias municipales', 'noticia')))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '41071')
        self.assertEqual(row['provincia'], 'Sevilla')
        self.assertFalse(row['publication_ready'])
        for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion',
                      'lat', 'lon', 'fase'):
            self.assertNotIn(field, row)
        self.assertEqual(row['documentos'][0]['source_url'], SOURCE_URL)

    def test_fail_closed(self):
        valid = block('ESTUDIO DE DETALLE PÍO XII', 'estudio')
        for html in ('<html>error</html>', page(), page(block('Modelo de licencia', 'modelo')),
                     page(valid + '<a rel="next" href="?page=2">2</a>'),
                     page(valid + '<div class="pagination"><a href="?p=2">2</a></div>'),
                     page(valid.replace('/export/sites/paradas/', 'https://example.org/'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_live_fetch_contract_and_snapshot(self):
        adapter = ParadasAyuntamientoAdapter('paradas')
        response = Mock(url=SOURCE_URL, text=page(block('ESTUDIO DE DETALLE PÍO XII', 'estudio')))
        with tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.paradas.requests.get', return_value=response) as get:
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(output.read_text())['municipio'], 'Paradas')
            self.assertEqual(get.call_args.args[0], SOURCE_URL)
            response.raise_for_status.assert_called_once()
            response.text = '<html>broken</html>'
            before = output.read_bytes()
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), before)
            self.assertTrue(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['disabled'])

    def test_manifest(self):
        manifest = load_manifest('paradas')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '41071')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter,
                         'municipio.adapters.paradas:ParadasAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
