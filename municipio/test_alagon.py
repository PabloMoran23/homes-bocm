"""Offline parser and traversal checks; no network or evidence fixtures required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.alagon import (
    AlagonAyuntamientoAdapter, SOURCE, ajax_html, make_record, parse_page,
)
from municipio.manifest import load_manifest, load_yaml

BASE = 'https://alagon.sedelectronica.es'


def folder(label, count, action):
    return f'''<a class="exp" onclick="wicketAjaxGet('{action}',null)">{label}<span> ( {count} )</span></a>'''


def doc(name, identifier):
    return f'<a href="{BASE}/preview-document/{identifier}">{name}</a>'


def more():
    return '''<div class="more_results"><button onclick="wicketAjaxGet('/?x=more',null)">Mostrar más</button></div>'''


class AlagonTests(unittest.TestCase):
    def test_grouping_dates_and_identity(self):
        title = 'TEXTO REFUNDIDO PGOU ALAGÓN, aprobado por Acuerdo CPUZ de 13/11/2018'
        docs, folders, pagination = parse_page(doc('Memoria', 'a') * 2 + doc('Planos', 'b'), BASE)
        row = make_record(title, BASE + '/transparency/pgou/', docs)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_acuerdo'], '2018-11-13')
        self.assertNotIn('fecha_publicacion', row)
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('lat', row)
        self.assertEqual(row['codigo_ine'], '50008')
        self.assertEqual(row['id'], 'alagon-plan-pgou')
        self.assertEqual(folders, {})
        self.assertIsNone(pagination)
        initial = make_record('APROBACION INICIAL MODIFICACIÓN AISLADA NÚM. 6 PGOU-ALAGÓN', BASE + '/transparency/ma6/', docs)
        self.assertEqual(initial['fase'], 'aprobacion_inicial')
        self.assertNotIn('fecha_acuerdo', initial)
        with self.assertRaises(ValueError):
            make_record('Solicitud de licencia', BASE, docs)
        with self.assertRaises(ValueError):
            parse_page('<a href="https://other.example/preview-document/x">X</a>', BASE)
        with self.assertRaises(ValueError):
            ajax_html('<ajax-response><redirect>login</redirect></ajax-response>')

    def run_inventory(self, expected=3, stagnant=False):
        title = 'ESTUDIO DE DETALLE PARA EQUIPAMIENTO DOCENTE'
        responses = [
            (SOURCE, f'<a href="{BASE}/transparency/root/">ACCESO AL PLAN GENERAL DE ORDENACIÓN URBANA</a>'),
            (BASE + '/transparency/root/', folder('7.1. PLANEAMIENTO URBANÍSTICO', expected, '/?x=planning')),
            (BASE + '/transparency/planning/', folder(title, expected, '/?x=instrument')),
            (BASE + '/transparency/instrument/', doc('Memoria', 'a') + more()),
            (BASE + '/?x=more', '<ajax-response><component><![CDATA[' + doc('Plano', 'b') + more() + ']]></component></ajax-response>'),
            (BASE + '/?x=more', '<ajax-response><component><![CDATA[' + doc('Plano', 'b' if stagnant else 'c') + ']]></component></ajax-response>'),
        ]
        class Session:
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def get(self, url, **kwargs):
                canonical, body = responses.pop(0)
                class Response:
                    text = body
                    url = canonical
                    def raise_for_status(self):
                        pass
                return Response()
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.alagon.requests.Session', Session):
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('prior-output')
            adapter = AlagonAyuntamientoAdapter('alagon')
            try:
                result = adapter.backfill_proyectos(output)
            except ValueError:
                self.assertEqual(output.read_text(), 'prior-output')
                raise
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertFalse(responses)
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]['documentos']), 3)
            self.assertEqual(result['documents_enumerated'], 3)

    def test_all_pages_including_repeated_wicket_action(self):
        self.run_inventory()

    def test_incomplete_counts_and_stalled_pagination_fail_atomically(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete folder'):
            self.run_inventory(expected=4)
        with self.assertRaisesRegex(ValueError, 'no progress'):
            self.run_inventory(stagnant=True)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('alagon')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Alagón', 'Zaragoza', '50008'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = AlagonAyuntamientoAdapter('alagon').backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
