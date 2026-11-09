"""Offline contract tests; fixtures model the reviewed public board structure."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cascante import CascanteAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest, load_yaml

BASE = 'https://cascante.sedelectronica.es'
DOC1 = BASE + '/preview-document/5a7863c8-664b-4f96-bcaa-b9099bf7f3d6'
DOC2 = BASE + '/preview-document/b01a6744-2b4e-4c99-94b9-6bd568a94faf'
TITLE = 'APROBACION INICIAL DE MODIFICACION DE LA EUR-15 DEL PLAN GENERAL DE CASCANTE'


def notice(title=TITLE, ref='1033/2026', url=DOC1, date='15/10/2026', procedure='Planeamiento General'):
    cells = {'name': '<a href="' + url + '">Anuncio BON</a>', 'folderCode': ref,
             'folderName': procedure, 'description': title, 'dateFrom': date}
    return '<tr>' + ''.join('<td class="class_' + key + '">' + value + '</td>' for key, value in cells.items()) + '</tr>'


def board(*rows):
    return '<table class="AdvertisementBoardListPanel"><thead><tr><th>Fecha de Publicación</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'


class CascanteTests(unittest.TestCase):
    def test_identity_and_date_semantics(self):
        rows = CascanteAyuntamientoAdapter.parse_inventory(board(notice()))
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '31068')
        self.assertEqual(row['expediente'], '1033/2026')
        self.assertEqual(row['fecha_publicacion'], '2026-10-15')
        self.assertEqual(row['fase'], 'aprobación inicial')
        for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])

    def test_groups_documents_and_keeps_individual_dates(self):
        html = board(notice(), notice(), notice(url=DOC2, date='16/10/2026'))
        rows = CascanteAyuntamientoAdapter.parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][1]['fecha_publicacion'], '2026-10-16')
        self.assertEqual(rows[0]['fecha_publicacion'], '2026-10-15')

    def test_excludes_forms_procurement_and_nonphysical_projects(self):
        html = board(notice(), notice(title='Solicitud de licencia de obras'),
                     notice(title='Licitación del proyecto de reparcelación'),
                     notice(title='Información pública del proyecto de ponencia de valoración', procedure='Procedimiento Genérico'),
                     notice(title='EMPLEO SOCIAL PROTEGIDO', procedure='Procedimiento Genérico'))
        self.assertEqual(len(CascanteAyuntamientoAdapter.parse_inventory(html)[0]['documentos']), 1)

    def test_separate_instruments_and_mixed_stages(self):
        second = 'APROBACION INICIAL DEL PROYECTO DE REPARCELACIÓN DEL SECTOR 1.1 DEL AR-1'
        rows = CascanteAyuntamientoAdapter.parse_inventory(board(notice(), notice(title=second, ref='952/2026', url=DOC2, procedure='Actuaciones Urbanísticas')))
        self.assertEqual(len(rows), 2)
        row = CascanteAyuntamientoAdapter.parse_inventory(board(notice(), notice(title=TITLE.replace('INICIAL', 'DEFINITIVA'), url=DOC2)))[0]
        self.assertIsNone(row['fase'])

    def test_rejects_new_pagination_and_broken_sources(self):
        for control in ('<a href="?page=2" rel="next">2</a>',
                        '<a onclick="wicketAjaxGet()">Siguiente</a>',
                        '<div class="pagination"><a href="?page=2">2</a></div>'):
            with self.subTest(control=control), self.assertRaisesRegex(ValueError, 'pagination'):
                CascanteAyuntamientoAdapter.parse_inventory(board(notice()) + control)
        for html in ('<html>Login</html>', board(), board(notice(ref='')), board(notice(date='imprecisa')), board(notice(url='https://example.org/preview-document/x'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                CascanteAyuntamientoAdapter.parse_inventory(html)
        for html in ('Login', '<iframe src="https://example.org/x.pdf"></iframe>'):
            with self.assertRaises(ValueError):
                CascanteAyuntamientoAdapter.parse_preview(html, DOC1)

    def test_live_method_verifies_pdf_and_writes_atomically(self):
        class Response:
            def __init__(self, url, body):
                self.url, self.content = url, body
                self.text = body.decode()
            def raise_for_status(self):
                pass
        class Session:
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def get(self, url, **kwargs):
                if url == SOURCE:
                    body = board(notice()).encode()
                elif url == DOC1:
                    body = b'<iframe src="/preview/pdf/session.pdf"></iframe>'
                else:
                    body = b'%PDF-1.7\nfixture'
                return Response(url, body)
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.cascante.requests.Session', Session):
            adapter = CascanteAyuntamientoAdapter('cascante')
            path = Path(directory) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(path)
            self.assertEqual(result['rows'], 1)
            row = json.loads(path.read_text())
            self.assertEqual(len(row['documentos'][0]['sha256']), 64)
            old = path.read_bytes()
            with patch.object(adapter, 'parse_preview', side_effect=ValueError('broken document')):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(path.read_bytes(), old)
            lic = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(lic)['status'], 'disabled')
            self.assertEqual(lic.read_bytes(), b'')

    def test_manifest(self):
        manifest = load_manifest('cascante')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '31068')
        self.assertEqual(manifest.provincia, 'Navarra')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.cascante:CascanteAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
