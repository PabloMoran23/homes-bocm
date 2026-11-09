"""Parser checks independent of local evidence and the live portal."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.jun import (
    BOARD, PLANNING, HOST, JunAyuntamientoAdapter, parse_board,
    parse_instrument, planning_folders,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def notice(description, code='205/2026', doc='a', date='20/03/2026'):
    return f'''<tr><td class="class_name"><a href="https://{HOST}/preview-document/{doc}">Anuncio</a></td>
    <td class="class_folderCode">{code}</td><td class="class_description">{description}</td>
    <td class="class_dateFrom">{date}</td></tr>'''


def board(*rows):
    return '<table class="AdvertisementBoardListPanel"><tbody>' + ''.join(rows) + '</tbody></table>'


WORK = 'ANUNCIO APROBACIÓN DEFINITIVA DEL PROYECTO “2024/4/PPCGR/1-26 “C.P. GR-3103 DE GRANADA A ALFACAR. MEJORA DE INTERSECCIÓN EN EL P.K. 1+290”'


class JunTests(unittest.TestCase):
    def test_work_semantics_and_date(self):
        row, = parse_board(board(notice(WORK)))
        self.assertIn('GR-3103', row['titulo'])
        self.assertEqual(row['codigo_ine'], '18111')
        self.assertEqual(row['fecha_publicacion'], '2026-03-20')
        self.assertEqual(row['documentos'][0]['inventory_url'], BOARD)
        for forbidden in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(forbidden, row)

    def test_excludes_licence_forms_procurement_and_unrelated_notices(self):
        self.assertEqual([], parse_board(board(*[notice(d) for d in [
            'Solicitud de licencia de obra', 'Licitación pavimentación calle Colonia',
            'BANDO LIMPIEZA DE SOLARES URBANOS 2026',
            'APROBACIÓN DEFINITIVA DEL PRESUPUESTO MUNICIPAL',
            'Anuncio aprobación del programa de empleo joven',
        ]])))

    def test_groups_documents_of_one_project(self):
        rows = parse_board(board(notice(WORK), notice(WORK, doc='b', date='21/03/2026'),
                                 notice(WORK)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][1]['fecha_publicacion'], '2026-03-21')

    def test_pagination_is_not_silently_truncated(self):
        for pager in ['<a href="?page=2" rel="next">Siguiente</a>',
                      '<a href="#" onclick="wicketAjaxGet(2)" title="Go to next page">&gt;</a>',
                      '<div class="pagination"><a href="#">2</a></div>']:
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_board(board(notice(WORK)) + pager)

    def test_structure_change_and_bad_date_fail(self):
        with self.assertRaises(ValueError):
            parse_board('<html>Maintenance</html>')
        with self.assertRaises(ValueError):
            parse_board(board(notice(WORK, date='not a date')))

    def test_planning_folders_exclude_entity_register(self):
        html = '''<table class="TransparencyListPanel">
        <a href="#" onclick="wicketAjaxGet('../../?x=abc')">7.1.2. INNOVACIÓN DEL PGOU UE-2 ( 2 )</a>
        <a href="#" onclick="wicketAjaxGet('../../?x=def')">7.1.1. REGISTRO DE ENTIDADES ( 1 )</a>
        </table>'''
        folder, = planning_folders(html)
        self.assertEqual(folder, ('INNOVACIÓN DEL PGOU UE-2', f'https://{HOST}/?x=abc', 2))

    def test_planning_grouping_count_and_document_isolation(self):
        def html(*docs):
            return '<table class="TransparencyListPanel">' + ''.join(
                f'<a href="/preview-document/{d}">{d}</a>' for d in docs) + '</table>'
        first = parse_instrument(html('DAE', 'borrador'), PLANNING + 'one/', 'Innovación UE-2', 2)
        second = parse_instrument(html('otro'), PLANNING + 'two/', 'Plan especial', 1)
        self.assertEqual(len(first['documentos']), 2)
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotIn('otro', str(first['documentos']))
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            parse_instrument(html('DAE'), PLANNING, 'Innovación', 2)
        with self.assertRaises(ValueError):
            parse_instrument(html(), PLANNING, 'Innovación', 0)
        with self.assertRaises(ValueError):
            parse_instrument(html('https://evil.example/preview-document/x').replace(
                '/preview-document/https://evil.example/', 'https://evil.example/'), PLANNING, 'Innovación', 1)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('jun')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('18111', 'Granada'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), JunAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = JunAyuntamientoAdapter('jun').backfill_licencias(out)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
