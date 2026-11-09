import tempfile
import unittest
from pathlib import Path

from municipio.adapters.monesterio import MonesterioAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest


def fixture(entries, extra=''):
    return ('<div class="contenidop"><h2>Ayuntamiento de Monesterio</h2>'
            '<div id="titulo">NORMATIVA</div>' + entries + extra + '</div>')


def entry(title='Plan General Municipal de Monesterio', path='plan.pdf', date='29/07/2025'):
    return (f'<div>Documento| <strong>Fecha de Alta: </strong>{date}'
            f'<a href="./documentos/{path}">{title}</a>'
            '<span>Descripción: DOE119 Lunes 23 de junio de 2025</span></div>')


class MonesterioTests(unittest.TestCase):
    def test_dates_provenance_and_no_geometry(self):
        row, = parse_inventory(fixture(entry()))
        self.assertEqual(row['codigo_ine'], '06085')
        self.assertEqual(row['documentos'][0]['fecha_alta_portal'], '2025-07-29')
        self.assertIn('23 de junio', row['documentos'][0]['descripcion'])
        for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_group_documents_and_stable_identity(self):
        one, = parse_inventory(fixture(entry()))
        grouped, = parse_inventory(fixture(entry() + entry(path='anexo.pdf') + entry()))
        self.assertEqual(one['id'], grouped['id'])
        self.assertEqual(len(grouped['documentos']), 2)

    def test_separate_modification_and_parent(self):
        rows = parse_inventory(fixture(entry('NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL') + entry('APROBACION MODIFICACION PUNTUAL 11 DE LAS NORMAS SUBSIDIARIAS', 'mod.pdf')))
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_forms_and_navigation_are_not_records(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture(entry('SOLICITUD LICENCIA DE OBRAS')))
        with self.assertRaises(ValueError):
            parse_inventory('<a href="documentos/plan.pdf">Plan General Municipal de Monesterio</a>')

    def test_pagination_fails_explicitly(self):
        for pagination in ['<a rel="next" href="?page=2">2</a>', '<div class="paginacion">2</div>', '<a href="?enlace=normativa&pagina=2">2</a>']:
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                parse_inventory(fixture(entry(), pagination))

    def test_untrusted_document_and_invalid_date(self):
        for html in [fixture(entry().replace('./documentos/', 'https://example.org/documentos/')),
                     fixture(entry(date='32/07/2025'))]:
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_missing_date_stays_unknown(self):
        row, = parse_inventory(fixture(entry(date='').replace('Fecha de Alta:', '')))
        self.assertIsNone(row['documentos'][0]['fecha_alta_portal'])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('monesterio')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            result = MonesterioAyuntamientoAdapter('monesterio').backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
