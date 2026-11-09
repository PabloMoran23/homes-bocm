import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.magan import ARCHIVE, MaganAyuntamientoAdapter
from municipio.manifest import load_manifest


def inventory():
    return {'features': [{'attributes': {
        'COD_INE': '45088', 'COD_PROV': '45', 'MUNICIPIO': 'Magán',
        'PLAN_': 'NNSS-B', 'NOM_PLAN': 'Normas Subsidiarias tipo b',
        'DISPONIBLE': 'SI', 'DESCARGA': ARCHIVE,
        'FECHA_APRO': 729216000000, 'FECHA_ACTU': 1557878400000,
    }}]}


def archive():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        for name in ['TEXTOS/NORMATIVA.pdf', 'TEXTOS/MODIFICACION PUNTUAL 5.pdf', 'PLANOS/MP5.pdf']:
            z.writestr('45088_MAGAN/' + name, b'%PDF-1.4 fixture')
    return stream.getvalue()


class MaganTests(unittest.TestCase):
    def test_dates_and_identity(self):
        row = MaganAyuntamientoAdapter.parse_inventory(inventory(), 1)[0]
        self.assertEqual(row['fecha_aprob'], '1993-02-09')
        self.assertEqual(row['fecha_actualizacion_catalogo'], '2019-05-15')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        payload = inventory()
        payload['features'][0]['attributes']['FECHA_APRO'] = None
        self.assertIsNone(MaganAyuntamientoAdapter.parse_inventory(payload, 1)[0]['fecha_aprob'])

    def test_reject_wrong_municipality_and_changed_source(self):
        for field, value in [('COD_INE', '35012'), ('COD_PROV', '35'), ('MUNICIPIO', 'Mogán'),
                             ('DESCARGA', 'https://example.org/file.zip'), ('PLAN_', 'SP')]:
            with self.subTest(field=field):
                payload = inventory()
                payload['features'][0]['attributes'][field] = value
                with self.assertRaises(ValueError):
                    MaganAyuntamientoAdapter.parse_inventory(payload, 1)

    def test_incomplete_inventory_fails(self):
        for payload, count in [(inventory(), 2), ({'features': []}, 0),
                               ({**inventory(), 'exceededTransferLimit': True}, 1),
                               ({'error': {'message': 'error'}}, 1),
                               ({'features': inventory()['features'] * 2}, 2)]:
            with self.assertRaises(ValueError):
                MaganAyuntamientoAdapter.parse_inventory(payload, count)

    def test_group_documents_and_refresh(self):
        adapter = MaganAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'projects.jsonl'
            responses = [json.dumps({'count': 1}).encode(), json.dumps(inventory()).encode(), archive()]
            with patch.object(adapter, '_fetch', side_effect=responses):
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(rows[0]['documentos']), 3)
            self.assertTrue(all(d['url'] == ARCHIVE for d in rows[0]['documentos']))
            previous = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=responses[:2] + [b'not a zip']):
                with self.assertRaises(zipfile.BadZipFile):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)

    def test_reject_empty_archive(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w'):
            pass
        with self.assertRaises(ValueError):
            MaganAyuntamientoAdapter.parse_archive(stream.getvalue())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('magan')
        self.assertEqual(manifest.provincia, 'Toledo')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(MaganAyuntamientoAdapter().backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
