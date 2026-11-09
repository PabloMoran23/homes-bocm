"""Offline board parser regression tests; fixtures are synthetic, not evidence."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.fuentes_de_ebro import FuentesDeEbroAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def notice(description, expediente='10/2026', day='09/10/2026', identifier='a'):
    fields = {'name': f'<a href="/preview-document/{identifier * 8}-1111-1111-1111-111111111111">Documento</a>',
              'folderCode': expediente, 'folderName': 'Contrataciones',
              'description': description, 'dateFrom': day}
    return '<tr>' + ''.join(f'<td class="class_{k}">{v}</td>' for k, v in fields.items()) + '</tr>'


def board(*rows):
    return '<table class="AdvertisementBoardListPanel"><tbody>' + ''.join(rows) + '</tbody></table>'


class ParserTests(unittest.TestCase):
    def test_group_documents_keep_publications_not_approvals(self):
        description = 'APROBACIÓN INICIAL PROYECTO DE OBRAS DE RED DE PLUVIALES'
        rows = Adapter.parse_inventory(board(notice(description), notice(description),
            notice(description, day='12/10/2026', identifier='b')))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fecha_publicacion'], '2026-10-09')
        self.assertEqual(row['documentos'][1]['fecha_publicacion'], '2026-10-12')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['geometry'])
        self.assertEqual(row['tipo'], 'obra_publica')
        self.assertEqual(row['codigo_ine'], '50115')

    def test_exclusions_and_planning(self):
        rows = Adapter.parse_inventory(board(
            notice('ANUNCIO DE APROBACION INICIAL. ESTUDIO DE DETALLE EN CALLE DE PRUEBA'),
            notice('Formulario solicitud de licencia de obras', '20/2026'),
            notice('Licitación proyecto de obras', '21/2026'),
            notice('ANUNCIO DE EMPLEO PUBLICO', '22/2026'),
            notice('APROBACION INICIAL LICITACION PROYECTO DE OBRAS', '23/2026')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['tipo'], 'planeamiento_urbanistico')

    def test_fail_closed_on_pagination_schema_or_invalid_date(self):
        valid = board(notice('APROBACION INICIAL PLAN ESPECIAL'))
        for html in (valid + '<a href="?page=2">Siguiente</a>',
                     valid + '<div class="pagination"><a href="?page=2">2</a></div>',
                     valid + '<a onclick="loadPage()" title="Next">→</a>',
                     '<html>Unavailable</html>', board(notice('Empleo público')),
                     valid.replace('09/10/2026', '31/02/2026'),
                     valid.replace('class_folderCode', 'unknown'),
                     valid.replace('/preview-document/', 'https://example.org/preview-document/')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        self.assertEqual(len(Adapter.parse_inventory(valid + '<button disabled>Siguiente</button>')), 1)

    def test_manifest_resolves_and_licences_disabled(self):
        manifest = load_manifest('fuentes-de-ebro')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            with patch('requests.Session.get', side_effect=AssertionError('No licence network request')):
                self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
