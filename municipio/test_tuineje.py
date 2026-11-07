"""Offline parser regression tests; no source captures required to run."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.tuineje import (
    BASE, CATEGORIES, INVENTORY, TuinejeAyuntamientoAdapter,
    parse_detail, parse_inventory, parse_listing,
)
from municipio.manifest import load_manifest


def listing(total=1, municipality='TUINEJE'):
    return f'''<div id="migas">Municipio : {municipality}</div>
    <table id="row"><tfoot><tr><td>Total de Expedientes:</td><td>{total}</td></tr></tfoot>
    <tbody><tr><td><a href="expedienteUrbanistico.jsp?numexp=2005%2f0033">2005/0033</a></td>
    <td>PP</td><td>M</td><td>MODIFICACIÓN PUNTUAL DEL PLAN PARCIAL VALLE DEL ACEITUN, TUINEJE</td>
    <td>10/10/2005</td><td>20/12/2005</td><td></td><td></td><td>L</td></tr></tbody></table>'''


def detail():
    return '''<div id="migas">Municipio: TUINEJE Expediente: 2005/0033</div>
    <textarea name="asunto">MODIFICACIÓN PUNTUAL DEL PLAN PARCIAL VALLE DEL ACEITUN, TUINEJE</textarea>
    <textarea name="comentario">LA FECHA SEÑALADA CORRESPONDE A CUANDO EL EXPEDIENTE FUE ASUMIDO POR LA COTMAC. EL 14-11-2005 FUE APROBADO DEFINITIVAMENTE POR EL AYUNTAMIENTO DE TUINEJE.</textarea>
    <p>Memorias (1 documento) Normativas (0 documentos) Planos (1 documento) Anexos (0 documentos) Catálogos (0 documentos)</p>
    <table><tr><td><a href="javascript:showPdf('22101')">Memoria</a></td><td>74</td><td>14/11/2005</td></tr>
    <tr><td><a href="javascript:showPdf('22102')">Plano - ANULADO</a></td><td>--</td><td>14/11/2005</td></tr></table>'''


class TuinejeTests(unittest.TestCase):
    def row(self):
        return parse_listing(listing(), BASE + CATEGORIES[1], 1)[0]

    def test_group_documents_and_date_provenance(self):
        row = parse_detail(detail(), self.row())
        self.assertEqual(row['fecha_aprobacion_catalogo'], '2005-10-10')
        self.assertEqual(row['fecha_aprob'], '2005-11-14')
        self.assertEqual(row['fecha_publicacion'], '2005-12-20')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['titulo'], 'Plano - ANULADO')
        self.assertEqual(row['documentos'][0]['url'], url_doc('22101'))
        self.assertEqual(row['documentos'][0]['source_url'], row['url'])
        self.assertFalse(row['publication_ready'])
        for key in ('lat', 'lon', 'geometry', 'fase', 'fecha_acuerdo'):
            self.assertNotIn(key, row)

    def test_qualified_date_without_explicit_approval_stays_unknown(self):
        html = detail().replace('EL 14-11-2005 FUE APROBADO DEFINITIVAMENTE', 'SE DESCONOCE LA APROBACIÓN')
        self.assertIsNone(parse_detail(html, self.row())['fecha_aprob'])

    def test_no_document_leakage_between_dossiers(self):
        first = parse_detail(detail(), self.row())
        second_row = {**self.row(), 'expediente': '2000/0001', 'titulo': 'OTRO PLAN'}
        html = detail().replace('2005/0033', '2000/0001').replace(self.row()['titulo'], 'OTRO PLAN').replace('22101', '99101').replace('22102', '99102')
        second = parse_detail(html, second_row)
        self.assertTrue({d['id'] for d in first['documentos']}.isdisjoint(d['id'] for d in second['documentos']))

    def test_incomplete_pagination_and_count_changes_fail(self):
        with self.assertRaises(ValueError):
            parse_listing(listing(total=2), BASE + CATEGORIES[1], 2)
        with self.assertRaises(ValueError):
            parse_listing(listing(), BASE + CATEGORIES[1], 2)
        with self.assertRaises(ValueError):
            parse_detail(detail().replace('Planos (1 documento)', 'Planos (20 documentos)'), self.row())

    def test_wrong_municipality_error_and_forms_rejected(self):
        for html in ('<h1>Error de aplicación</h1>', '<a href="licencia.pdf">Solicitud licencia obras</a>', listing(municipality='OTRO')):
            with self.assertRaises(ValueError):
                parse_listing(html, BASE + CATEGORIES[1], 1)
        with self.assertRaises(ValueError):
            parse_detail(detail().replace('Expediente: 2005/0033', 'Expediente: 2000/0001'), self.row())

    def test_inventory_requires_both_category_counts(self):
        html = '<div id="migas">Municipio: TUINEJE</div>' + ''.join(
            f'<a href="{c}">Planeamiento ({i})</a>' for c, i in zip(CATEGORIES, (14, 1)))
        self.assertEqual(sum(parse_inventory(html).values()), 15)
        with self.assertRaises(ValueError):
            parse_inventory(html.replace('(14)', ''))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('tuineje')
        self.assertEqual(manifest.provincia, 'Las Palmas')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = TuinejeAyuntamientoAdapter().backfill_licencias(out)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')

    def test_update_refreshes_whole_snapshot(self):
        adapter = TuinejeAyuntamientoAdapter()
        with patch.object(adapter, 'backfill_proyectos', return_value={'count': 15}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('out'), Path('state')), {'count': 15})
            backfill.assert_called_once_with(Path('out'))


def url_doc(identifier):
    return BASE.replace('/consulta/', '/otros/') + 'ShowPdfServlet?iddoc=' + identifier


if __name__ == '__main__':
    unittest.main()
