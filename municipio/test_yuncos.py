"""Parser and traversal regression tests; no network needed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

from municipio.adapters.yuncos import (
    ROOT, YuncosAyuntamientoAdapter, entries, group_documents,
)
from municipio.manifest import load_manifest, load_yaml

BASE = 'https://yuncos.sedelectronica.es'


def doc(identifier, title):
    return f'<tr><td class="class_name"><a class="gIconLink" href="{BASE}/preview-document/{identifier}">{escape(title)}</a></td></tr>'


def folder(title, count, target):
    return f'''<tr><td class="class_name"><a class="gIconLink exp" onclick="wicketAjaxGet('{target}',null)">{title}<span> ( {count} )</span></a></td></tr>'''


def more(target):
    return f'''<div class="more_results"><button onclick="wicketAjaxGet('{target}',null)">Mostrar más</button></div>'''


def xml(content):
    return '<?xml version="1.0"?><ajax-response><component><![CDATA[' + content + ']]></component></ajax-response>'


class Response:
    def __init__(self, url, text):
        self.url, self.text, self.content = url, text, text.encode()
        self.status_code, self.is_redirect = 200, False

    def raise_for_status(self):
        pass


class YuncosTests(unittest.TestCase):
    def test_xml_components_and_relative_pagination(self):
        text = xml(doc('nnss', '01 NNSS Yuncos Texto Refundido-Mayo 2012') + more('?x=more'))
        docs, folders, next_url = entries(text, BASE + '/?x=first')
        self.assertEqual(docs[0]['titulo'], '01 NNSS Yuncos Texto Refundido-Mayo 2012')
        self.assertEqual(next_url, BASE + '/?x=more')
        self.assertEqual(folders, [])

    def test_non_inventory_forms_and_navigation_are_ignored(self):
        docs, folders, next_url = entries('<a class="gIconLink" href="/login"></a><a href="/Solicitud-Obra-Mayor.pdf">Solicitud</a>', ROOT)
        self.assertEqual((docs, folders, next_url), ([], [], None))

    def test_untrusted_folder_destination_rejected(self):
        with self.assertRaises(ValueError):
            entries(folder('PLANOS', 1, 'https://example.org/'), ROOT)

    def test_group_annexes_sector_maps_and_unknown_documents(self):
        names = [('1', '01 NNSS Yuncos Texto Refundido-Mayo 2012', ''),
                 ('2', 'NNSS Yuncos Anexo definición de conceptos', ''),
                 ('3', 'Plan Parcial de Ordenación Sector 26 - Memoria', ''),
                 ('4', 'Plano de zonificación', 'PLANOS/Planos de Ordenación del P.P. Sector 26'),
                 ('5', 'NORMATIVA S-5', '')]
        rows, excluded = group_documents([{'url': BASE + '/preview-document/' + i, 'titulo': t, 'carpeta': p} for i, t, p in names])
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
        self.assertEqual(excluded[0]['titulo'], 'NORMATIVA S-5')
        for row in rows:
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '45205')

    def run_fake(self, advertised=3, cycle=False):
        routes = {
            ROOT: 'PLANEAMIENTO ' + folder('NORMAS', advertised, '/?x=normas'),
            BASE + '/?x=normas': '<table>' + doc('1', '01 NNSS Yuncos Texto Refundido-Mayo 2012') + '</table>' + more('/?x=more'),
            BASE + '/?x=more': xml(doc('2', 'NNSS Yuncos Anexo I') + folder('Anexos', 1, '/?x=child') + (more('/?x=more') if cycle else '')),
            BASE + '/?x=child': doc('3', 'NNSS Yuncos Anexo II'),
        }
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.yuncos.requests.Session') as session:
            session.return_value.__enter__.return_value.get.side_effect = lambda url, **kw: Response(url, routes[url])
            output = Path(tmp) / 'out.jsonl'
            output.write_text('existing snapshot')
            try:
                report = YuncosAyuntamientoAdapter().backfill_proyectos(output)
            except ValueError:
                self.assertEqual(output.read_text(), 'existing snapshot')
                raise
            row = json.loads(output.read_text())
            self.assertEqual(len(row['documentos']), 3)
            return report

    def test_nested_and_paginated_inventory_is_complete(self):
        self.assertEqual(self.run_fake()['inventory_documents'], 3)

    def test_count_mismatch_does_not_write_partial_snapshot(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete inventory'):
            self.run_fake(advertised=4)

    def test_pagination_cycle_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Pagination cycle'):
            self.run_fake(cycle=True)

    def test_empty_page_cannot_become_placeholder(self):
        with self.assertRaises(ValueError):
            group_documents([])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('yuncos')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('45205', 'Yuncos', 'Toledo'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            report = YuncosAyuntamientoAdapter().backfill_licencias(path)
            self.assertEqual(report['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
