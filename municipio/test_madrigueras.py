"""Offline parser and adapter contract tests; no network needed."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.madrigueras import MadriguerasAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml


# Minimal transcription of the municipal structured disclosure, not a fallback.
OPERATION = '''<p>El Programa Operativo Regional FEDER cofinancia las obras realizadas.<br>
OPERACIÓN: MODERNIZACIÓN Y MEJORA DE LAS INFRAESTRUCTURAS DEL COLEGIO DE PRIMARIA SAN JORGE DE MADRIGUERAS (ALBACETE)<br>
CÓDIGO DE LA OPERACIÓN: ES302039/2018/1802/101<br>
COFINANCIACIÓN: El Programa Operativo Regional FEDER 2014-2020 cofinancia esta operación en un 80%.<br>
COSTE TOTAL DE LA OPERACIÓN: 63.974,78 €</p>'''


def block(content, ident='operation'):
    return f'<div class="elementor-accordion-item"><div class="elementor-tab-content" id="{ident}">{content}</div></div>'


class MadriguerasTests(unittest.TestCase):
    def test_real_fields_and_no_inferred_metadata(self):
        rows = parse_inventory(block(OPERATION))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_operacion'], 'ES302039/2018/1802/101')
        self.assertEqual(row['coste_total_operacion_eur'], '63.974,78')
        self.assertEqual(row['codigo_ine'], '02045')
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['documentos'][0]['url'], SOURCE + '#operation')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)

    def test_excludes_unrelated_documents_and_forms(self):
        other = block('<p>Modelo solicitud licencia obras. Aprobado 30 de abril de 2021.</p><a href="ordenanza.pdf">Ordenanza</a>', 'other')
        rows = parse_inventory(other + block(OPERATION))
        self.assertEqual(len(rows), 1)
        self.assertFalse(any('ordenanza.pdf' in doc['url'] for doc in rows[0]['documentos']))
        with self.assertRaises(ValueError):
            parse_inventory(other)

    def test_document_grouping_and_stable_identity(self):
        first = block(OPERATION + '<a href="/memoria.pdf">Memoria</a>', 'one')
        second = block(OPERATION + '<a href="/planos.pdf">Planos</a>', 'two')
        rows = parse_inventory(first + second)
        self.assertEqual(len(rows), 1)
        urls = {d['url'] for d in rows[0]['documentos']}
        self.assertIn('https://madrigueras.es/memoria.pdf', urls)
        self.assertIn('https://madrigueras.es/planos.pdf', urls)
        self.assertEqual(rows[0]['id'], parse_inventory(second)[0]['id'])

    def test_conflicting_duplicate_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(block(OPERATION) + block(OPERATION.replace('63.974,78', '10.000,00')))

    def test_missing_or_malformed_source_fails(self):
        for html in ('<html>Unavailable</html>', block(OPERATION.replace('CÓDIGO DE LA OPERACIÓN:', 'Código:')),
                     block(OPERATION.replace('ES302039/2018/1802/101', '?'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_is_not_silently_truncated(self):
        for nav in ('<a rel="next" href="/anuncios/page/2/">2</a>',
                    '<a href="?page=2">Siguiente</a>',
                    '<div class="pagination"><a href="?page=2">2</a></div>'):
            with self.subTest(nav=nav), self.assertRaises(ValueError):
                parse_inventory(block(OPERATION) + nav)

    def test_nonphysical_and_other_municipalities_excluded(self):
        for text in (OPERATION.replace('MADRIGUERAS', 'OTRO MUNICIPIO'),
                     OPERATION.replace('INFRAESTRUCTURAS', 'SERVICIOS'),
                     OPERATION.replace('obras realizadas', 'servicios realizados')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_inventory(block(text))

    def test_manifest_and_adapter_refresh(self):
        manifest = load_manifest('madrigueras')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '02045')
        self.assertEqual(manifest.provincia, 'Albacete')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        response = Mock(text=block(OPERATION), url=SOURCE, headers={'Content-Type': 'text/html'})
        adapter = MadriguerasAyuntamientoAdapter('madrigueras')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'records.jsonl'
            with patch('municipio.adapters.madrigueras.requests.get', return_value=response):
                self.assertEqual(adapter.update_proyectos(out, Path(directory) / 'state.json')['count'], 1)
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '02045')
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')
            out.write_text('previous\n')
            response.text = '<html>Error</html>'
            with patch('municipio.adapters.madrigueras.requests.get', return_value=response), self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')


if __name__ == '__main__':
    unittest.main()
