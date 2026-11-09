"""Offline parser/crawler contract tests; no network needed."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from municipio.adapters.orgiva import (
    OrgivaAyuntamientoAdapter, SOURCE, official_url, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


HOST = 'https://orgiva.sedelectronica.es'
PBOM = HOST + '/transparency/11111111-1111-1111-1111-111111111111/'
CHILD = HOST + '/transparency/22222222-2222-2222-2222-222222222222/'


def document(name, identifier):
    return (f'<a class="gIconLink" href="{HOST}/preview-document/{identifier}" '
            f'title="Descripción del documento">{name}</a>')


def folder(name, count, action):
    return (f'<a class="gIconLink exp" href="#" '
            f'''onclick="wicketAjaxGet('/?x={action}')">{name}<span> ( {count} )</span></a>''')


def listing(content):
    return f'<table class="TransparencyListPanel">{content}</table>'


def more(action):
    return f'''<div class="more_results"><button onclick="wicketAjaxGet('/?x={action}')">Mostrar más</button></div>'''


def xml(content):
    return f'<ajax-response><component id="next"><![CDATA[{content}]]></component></ajax-response>'


class Session:
    def __init__(self, replies):
        self.replies = replies
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, **kwargs):
        if url not in self.replies:
            raise AssertionError(f'Unexpected request: {url}')
        reply = self.replies[url]
        body, headers = reply.pop(0) if isinstance(reply, list) else reply
        return SimpleNamespace(text=body, headers=headers, status_code=200,
                               raise_for_status=lambda: None)


class OrgivaTests(unittest.TestCase):
    def replies(self):
        return {
            SOURCE: (listing(folder('PBOM', 2, 'pbom') + document('Formulario licencia', 'form')) + more('next'), {}),
            HOST + '/?x=next': (xml(document('PLAN DELIMITACIÓN SUELO URBANO ÓRGIVA', 'plan')), {}),
            HOST + '/?x=pbom': (' ', {'Ajax-Location': PBOM}),
            PBOM: (listing(document('Decreto avance', 'decreto') + folder('PLANOS', 1, 'child')), {}),
            HOST + '/?x=child': (' ', {'Ajax-Location': CHILD}),
            CHILD: (listing(document('Plano de ordenación', 'plano')), {}),
        }

    def run_adapter(self, replies, output):
        adapter = OrgivaAyuntamientoAdapter('orgiva')
        with patch('municipio.adapters.orgiva.requests.Session', return_value=Session(replies)):
            return adapter.backfill_proyectos(output)

    def test_grouping_pagination_provenance_and_no_inferred_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            result = self.run_adapter(self.replies(), path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['count'], 2)
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(rows[0]['documentos'][1]['inventory_url'], CHILD)
            self.assertEqual(rows[0]['documentos'][1]['descripcion_fuente'], 'Descripción del documento')
            self.assertEqual(len(rows[1]['documentos']), 1)
            self.assertEqual(rows[1]['documentos'][0]['url'], rows[1]['url'])
            for row in rows:
                self.assertEqual(row['codigo_ine'], '18147')
                self.assertFalse(row['publication_ready'])
                self.assertFalse({'fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob',
                                  'lat', 'lon', 'geometry', 'fase'} & row.keys())
            ids = [row['id'] for row in rows]
            self.run_adapter(self.replies(), path)
            self.assertEqual(ids, [json.loads(x)['id'] for x in path.read_text().splitlines()])

    def test_incomplete_folder_does_not_replace_existing_output(self):
        replies = self.replies()
        replies[CHILD] = (listing(''), {})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'records.jsonl'
            path.write_text('previous result')
            with self.assertRaisesRegex(ValueError, 'count'):
                self.run_adapter(replies, path)
            self.assertEqual(path.read_text(), 'previous result')

    def test_stuck_pagination_fails(self):
        replies = self.replies()
        replies[HOST + '/?x=next'] = (xml(more('next')), {})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'no progress'):
                self.run_adapter(replies, Path(directory) / 'records.jsonl')

    def test_wicket_can_reuse_same_pagination_action(self):
        replies = self.replies()
        replies[HOST + '/?x=next'] = [
            (xml(document('PLAN DELIMITACIÓN SUELO URBANO ÓRGIVA', 'plan') + more('next')), {}),
            (xml('<div style="display:none"></div>'), {}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.run_adapter(replies, Path(directory) / 'out.jsonl')['count'], 2)

    def test_empty_final_pagination_component_is_allowed(self):
        entries, button = parse_page(xml('<div style="display:none"></div>'), ajax=True)
        self.assertEqual(entries, [])
        self.assertIsNone(button)

    def test_missing_table_or_bad_ajax_fails(self):
        for body in ('<h1>Unavailable</h1>', '<table>Wrong table</table>'):
            with self.assertRaises(ValueError):
                parse_page(body)
        with self.assertRaises(ValueError):
            parse_page('<ajax-response><redirect>login</redirect></ajax-response>', ajax=True)

    def test_empty_supported_inventory_fails(self):
        replies = {SOURCE: (listing(document('Modelo licencia de obra', 'form')), {})}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'No supported'):
                self.run_adapter(replies, Path(directory) / 'records.jsonl')

    def test_external_navigation_and_missing_folder_location_fail(self):
        with self.assertRaises(ValueError):
            official_url(SOURCE, 'https://example.com/document')
        replies = self.replies()
        replies[HOST + '/?x=pbom'] = (' ', {})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'Ajax-Location'):
                self.run_adapter(replies, Path(directory) / 'records.jsonl')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('orgiva')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('18147', 'Órgiva', 'Granada'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with self.assertRaises(NotImplementedError):
            OrgivaAyuntamientoAdapter('orgiva').backfill_licencias(Path('/unused'))


if __name__ == '__main__':
    unittest.main()
