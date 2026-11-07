import io
import unittest
import zipfile
from xml.sax.saxutils import escape

from municipio.adapters.cehegin import SOURCE, group_works, inventory_links, parse_workbook
from municipio.manifest import load_manifest, load_yaml


def workbook(sheets, date1904=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><workbookPr date1904="%s"/><sheets>%s</sheets></workbook>' % (int(date1904), ''.join(f'<sheet name="Hoja{i}" r:id="r{i}"/>' for i in range(len(sheets)))))
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships>' + ''.join(f'<Relationship Id="r{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(len(sheets))) + '</Relationships>')
        for i, rows in enumerate(sheets):
            xml = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            for n, row in enumerate(rows, 1):
                xml += f'<row r="{n}">' + ''.join(f'<c r="{chr(65+c)}{n}" t="inlineStr"><is><t>{escape(v)}</t></is></c>' for c, v in enumerate(row)) + '</row>'
            z.writestr(f'xl/worksheets/sheet{i}.xml', xml + '</sheetData></worksheet>')
    return stream.getvalue()


class CeheginTests(unittest.TestCase):
    def test_manifest(self):
        m = load_manifest('cehegin')
        raw = load_yaml(m.path)
        self.assertEqual((m.nombre, m.provincia, raw['codigo_ine']), ('Cehegín', 'Murcia', '30017'))
        self.assertFalse(m.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])

    def test_links_deduplicate_and_exclude_forms(self):
        html = '<h1>Modificación de las obras más importantes</h1><table>' + '<a href="../../../storage/uploads/obras.xlsx">Documento</a>' * 2 + '<a href="licencia.pdf">Solicitud de licencia</a></table>'
        self.assertEqual(list(inventory_links(html)), ['https://transparencia.cehegin.es/storage/uploads/obras.xlsx'])
        for bad in ('<h1>Login</h1>', html + '<a rel="next" href="?page=2">2</a>', html + '<table><a href="https://other.example/works.xlsx">Obras</a></table>'):
            with self.assertRaises(ValueError):
                inventory_links(bad)

    def test_every_sheet_dates_and_grouped_provenance(self):
        header = ['NOMBRE DE LA OBRA', 'FECHA INICIO', 'FECHA FIN']
        data = workbook([[header, ['Urbanización P.A.14', '40067', '41704']], [], [header, ['Obra segunda', '40220', '']]])
        rows = parse_workbook(data, SOURCE + '/one.xlsx')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['fecha_inicio'], '2009-09-11')
        other = parse_workbook(workbook([[header, ['Urbanizacion P.A.14', '40067', '41704']]]), SOURCE + '/two.xlsx')
        grouped = group_works(rows + other)
        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(grouped[0]['documentos']), 2)
        for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, grouped[0])
        self.assertNotIn('fecha_fin', grouped[1])

    def test_duration_is_not_end_date(self):
        rows = parse_workbook(workbook([[['DENOMINACIÓN DE LA OBRA', 'FECHA DE INICIO', 'PLAZO DE EJECUCIÓN'], ['Pabellón de deportes, Fase 1 y Fase 2.', '43581', '8.25 meses']]]), SOURCE)
        self.assertEqual(rows[0]['plazo_ejecucion'], '8.25 meses')
        self.assertNotIn('fecha_fin', rows[0])
        self.assertEqual(rows[0]['documentos'][0]['fila'], 2)

    def test_drift_empty_and_conflicts_fail(self):
        for sheets in ([[]], [[['Título desconocido']]], [[['NOMBRE DE LA OBRA', 'CAMBIO', 'FECHA FIN']]]):
            with self.assertRaises(ValueError):
                parse_workbook(workbook(sheets), SOURCE)
        with self.assertRaises(ValueError):
            group_works([{'titulo': 'Obra', 'fecha_inicio': '2000-01-01', 'documentos': []}, {'titulo': 'Obra', 'fecha_inicio': '2001-01-01', 'documentos': []}])


if __name__ == '__main__':
    unittest.main()
