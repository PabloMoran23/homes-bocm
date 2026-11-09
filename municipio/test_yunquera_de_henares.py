"""Offline semantic and traversal tests; fixtures are synthetic, not live evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.yunquera_de_henares import (
    HOST, SOURCE, YunqueraDeHenaresAyuntamientoAdapter, group_projects, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import resolve_portal_adapter_spec

BASE = f'https://{HOST}'
PLAN = BASE + '/transparency/plan/'
PUBLIC = BASE + '/transparency/public/'
DOSSIER = BASE + '/transparency/dossier/'


def doc(number, title):
    return f'<td class="class_name"><a class="gIconLink" href="{BASE}/preview-document/00000000-0000-0000-0000-{number:012d}">{title}</a></td>'


def folder(url, title, count):
    return f'''<td class="class_name"><a class="gIconLink exp" onclick="wicketAjaxGet('{url}')">{title}<span class="linkExtraInfo"> ( {count} )</span></a></td>'''


def page(*cells):
    return '<div id="content"><table class="TransparencyListPanel"><tbody>' + ''.join('<tr>' + cell + '</tr>' for cell in cells) + '</tbody></table></div>'


def pages():
    return {
        SOURCE: page(folder(PLAN, '7.1. PLANEAMIENTO URBANÍSTICO', 1), folder(PUBLIC, '7.6. EXPEDIENTES EN INFORMACIÓN PÚBLICA.', 4)),
        PLAN: page(doc(1, 'MODIF-PUNTUAL-Autonomias-Quevedo 22-sept-17 (Diligenciado para información pública)')),
        PUBLIC: page(folder(DOSSIER, 'Expediente 756/2020: Calificación urbanística placas fotovoltaicas', 2),
                     doc(2, 'INDICE EXPEDIENTE Nº 453/2022'),
                     doc(3, 'EXPEDIENTE Nº 453/2022 (Instalación solar fotovoltaica para autoconsumo)')),
        DOSSIER: page(doc(4, 'PROYECTO_EJECUCIÓN'), doc(5, 'Solicitud licencia urbanística')),
    }


class Response:
    def __init__(self, url, html):
        self.url = url
        self.html = html.encode()
        self.headers = {'Content-Type': 'text/html;charset=utf-8'}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.html


class Session:
    def __init__(self, data):
        self.data = data
        self.headers = {}

    def get(self, url, **kwargs):
        return Response(url, self.data[url])

    def close(self):
        pass


class YunqueraTests(unittest.TestCase):
    def extract(self, data):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'projects.jsonl'
            adapter = YunqueraDeHenaresAyuntamientoAdapter('yunquera-de-henares')
            with patch('municipio.adapters.yunquera_de_henares.requests.Session', return_value=Session(data)):
                report = adapter.backfill_proyectos(out)
            return report, [json.loads(line) for line in out.read_text().splitlines()]

    def test_all_documents_grouped_and_dates_not_inferred(self):
        report, rows = self.extract(pages())
        self.assertEqual((report['rows'], report['documents']), (3, 5))
        self.assertEqual(sorted(len(r['documentos']) for r in rows), [1, 2, 2])
        self.assertEqual({r['expediente'] for r in rows}, {None, '756/2020', '453/2022'})
        for row in rows:
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '19331')
        self.assertEqual(rows[1]['fase'], 'documentación de información pública')

    def test_count_mismatch_rejects_incomplete_or_paginated_inventory(self):
        data = pages()
        data[DOSSIER] = page(doc(4, 'PROYECTO_EJECUCIÓN'))
        with self.assertRaisesRegex(ValueError, 'Incomplete inventory'):
            self.extract(data)

    def test_visible_pager_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Pagination'):
            parse_inventory(pages()[PLAN] + '<a rel="next" href="?page=2">Siguiente</a>', PLAN)

    def test_login_and_navigation_are_not_records(self):
        with self.assertRaisesRegex(ValueError, 'Missing public'):
            parse_inventory('<h1>Identifícate</h1><a>Urbanismo</a>', SOURCE)
        with self.assertRaisesRegex(ValueError, 'no rows'):
            parse_inventory(page(), SOURCE)

    def test_application_alone_does_not_establish_project(self):
        with self.assertRaisesRegex(ValueError, 'physical project'):
            group_projects([{'titulo': 'Expediente 1/2026: solicitud de licencia', 'section': '7.6.',
                             'url': DOSSIER, 'documents': [{'titulo': 'Solicitud licencia', 'url': BASE + '/preview-document/a'}]}])

    def test_external_document_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected source'):
            parse_inventory(page(doc(1, 'Plan').replace(BASE, 'https://example.org')), PLAN)

    def test_stable_ids_and_snapshot_update(self):
        _, first = self.extract(pages())
        _, second = self.extract(pages())
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as directory:
            out, state = Path(directory) / 'out.jsonl', Path(directory) / 'state.json'
            state.write_text('unchanged')
            with patch('municipio.adapters.yunquera_de_henares.requests.Session', return_value=Session(pages())):
                YunqueraDeHenaresAyuntamientoAdapter('yunquera-de-henares').update_proyectos(out, state)
            self.assertEqual(state.read_text(), 'unchanged')
            self.assertEqual(len(out.read_text().splitlines()), 3)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('yunquera-de-henares')
        self.assertEqual(manifest.provincia, 'Guadalajara')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(resolve_portal_adapter_spec(manifest), 'municipio.adapters.yunquera_de_henares:YunqueraDeHenaresAyuntamientoAdapter')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = YunqueraDeHenaresAyuntamientoAdapter('yunquera-de-henares').backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
