import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.los_corrales import (
    BASE, DETAIL, PBOM, SOURCES, LosCorralesAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def document(section, filename, title=None):
    return (f'<a href="/export/sites/loscorrales/es/transparencia/.galleries/'
            f'IND-{section}-/{filename}">{title or filename}</a>')


class LosCorralesTests(unittest.TestCase):
    def test_pbom_grouping_and_isolation(self):
        html = document('50', 'PGOU-PUBLICACION-EN-BOJA-N-79-DE-25-DE-ABRIL-DE-2014.pdf')
        html += ''.join(document('50', name) for name in sorted(PBOM))
        rows = parse_inventory(html, SOURCES['50'], '50')
        self.assertEqual([len(r['documentos']) for r in rows], [1, 8])
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '41037')
            self.assertFalse(row['publication_ready'])
            for field in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase']:
                self.assertNotIn(field, row)

    def test_detail_grouping_and_exclusions(self):
        html = ''.join(document('55', name) for name in sorted(DETAIL))
        html += document('55', 'Informe-innecesariedad-de-tramitacion-de-Avance-de-Planeamiento.pdf')
        html += document('55', 'CO0525FCC_ESTUDIO_DE_DETALLE_F.pdf')
        rows = parse_inventory(html, SOURCES['55'], '55')
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 4)
        self.assertIn('Sosa', rows[0]['titulo'])

    def test_modification_and_peri_separate(self):
        html = document('53', 'PERI-SUNC-1-LOS-CORRALES.PDF')
        html += document('53', 'MP1-PGOU-LOS-CORRALES/DEFINITIVO-MP-1-PGOU-LOS-CORRALES_F.pdf')
        rows = parse_inventory(html, SOURCES['53'], '53')
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(len(r['documentos']) == 1 for r in rows))

    def test_missing_unknown_and_pagination_fail(self):
        valid = document('62', 'Proyecto-Alumbrado-Publico-Los-Corrales_sign_document.pdf')
        for html in ['', '<h1>Login</h1>', document('62', 'modelo-licencia.pdf'),
                     valid + '<ul class="pagination"><li>2</li></ul>',
                     valid + '<a href="?page=2" rel="next">Más</a>',
                     valid + '<a href="?page=2">Siguiente</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCES['62'], '62')

    def test_document_origin(self):
        html = document('62', 'Proyecto-Alumbrado-Publico-Los-Corrales_sign_document.pdf')
        html = html.replace('href="/', 'href="https://example.org/')
        with self.assertRaises(ValueError):
            parse_inventory(html, SOURCES['62'], '62')

    def test_licences_disabled_and_no_network(self):
        with tempfile.TemporaryDirectory() as folder, patch('requests.Session.get') as get:
            path = Path(folder) / 'licencias.jsonl'
            report = LosCorralesAyuntamientoAdapter('los-corrales').backfill_licencias(path)
            self.assertTrue(report['disabled'])
            self.assertEqual(path.read_text(), '')
            get.assert_not_called()

    def test_manifest_and_registry(self):
        manifest = load_manifest('los-corrales')
        self.assertIsInstance(load_portal_adapter(manifest), LosCorralesAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Sevilla')

    def test_failed_fetch_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as folder, patch('requests.Session.get', side_effect=RuntimeError('offline')):
            path = Path(folder) / 'proyectos.jsonl'
            path.write_text('existing\n')
            with self.assertRaises(RuntimeError):
                LosCorralesAyuntamientoAdapter('los-corrales').backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'existing\n')


if __name__ == '__main__':
    unittest.main()
