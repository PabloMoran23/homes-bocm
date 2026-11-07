"""Offline semantic and completeness checks; fixtures do not require live evidence."""
import base64
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.zafra import SOURCE, ZafraAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def document(name, date='07/09/2026'):
    encoded = base64.b64encode(('planeamiento_escaneado_refundido/212/' + name).encode()).decode()
    return f'<tr><td>{date}</td><td><a href="/SITEX/downloads/archivos/{encoded}">{name}</a></td></tr>'


def fixture(extra=''):
    return '''<h1>Cargando...</h1><div id="divplaneamiento212">
    <h1>Refundido vigente de la figura 'PGOU.R-001' y sus modificaciones<br><span>Zafra</span></h1>
    <table><tr><th>Tenidas en cuenta</th><td><span onclick='addTab("/SITEX/ptofiguras/viewsigcat/37814","Zafra - PGOU.R-001");'>PGOU.R-001</span></td></tr>
    <tr><th>NO tenidas en cuenta</th><td><span onclick='addTab("/SITEX/ptofiguras/viewsigcat/40768","Zafra - PGOU.R-001.M-032");'>PGOU.R-001.M-032</span></td></tr></table>
    <div id="vistadeficherosrefundidos212"><table>''' + document('NormativaRefundida.pdf') + document('CatalogoRefundido.pdf') + extra + '</table></div></div>'


class ZafraTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '06158')
        self.assertEqual(row['provincia'], 'Badajoz')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['fecha_actualizacion'], '2026-09-07')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertEqual(row['figuras_refundidas']['no_incorporadas'][0]['referencia'], 'PGOU.R-001.M-032')
        self.assertFalse(row['publication_ready'])

    def test_all_hidden_documents_retained_and_duplicates_grouped(self):
        extra = '<div style="display:none">' + ''.join(document(f'hoja{i}.webp') for i in range(65)) + '</div>'
        row = parse_inventory(fixture(extra + document('NormativaRefundida.pdf')))[0]
        self.assertEqual(len(row['documentos']), 67)
        self.assertTrue(all(d['url'].startswith('https://sitex.juntaex.es/SITEX/downloads/archivos/') for d in row['documentos']))
        self.assertEqual(row['url'], SOURCE)

    def test_reject_wrong_town_navigation_and_incomplete_inventory(self):
        for html in (fixture().replace('>Zafra<', '>Otro<'), '<a>PGOU de Zafra</a>',
                     fixture().replace(document('CatalogoRefundido.pdf'), '')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_refuse_unhandled_pagination(self):
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_inventory(fixture('<a rel="next" href="?page=2">Siguiente</a>'))

    def test_missing_document_date_is_not_synthesized(self):
        row = parse_inventory(fixture(document('plano.pdf', '')))[0]
        self.assertIsNone(row['documentos'][-1]['fecha_actualizacion'])

    def test_manifest_loads_and_licences_do_not_fetch(self):
        manifest = load_manifest('zafra')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, ZafraAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as tmp, patch('municipio.adapters.zafra.requests.get') as fetch:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
