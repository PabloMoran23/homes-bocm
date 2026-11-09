import io
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.malagon import (
    MalagonAyuntamientoAdapter, parse_archive_directory, parse_projects,
)
from municipio.manifest import load_manifest

ATTRS = {
    'OBJECTID': 1060, 'COD_INE': '13052', 'COD_PROV': '13', 'MUNICIPIO': 'Malagón',
    'PLAN_': 'NNSS-B', 'NOM_PLAN': 'Normas Subsidiarias tipo b',
    'FECHA_APRO': 608428800000,
    'DESCARGA': 'https://ficheroscomunes.castillalamancha.es/planeamiento/CIUDAD_REAL/13052_MALAGON.zip',
}
ROOT = '13052_MALAGON/NNSS_Normas Subsidiarias 1989/'
NAMES = [ROOT + '1_Normativa/TEXTOS_NNSS.pdf', ROOT + '2_Planos/plano.pdf',
         ROOT + '3_Modificaciones Puntuales/2001-10-18 MP-4 CREACION UA NORTE 1/1_Normativa/texto.pdf',
         ROOT + '3_Modificaciones Puntuales/2001-10-18 MP-4 CREACION UA NORTE 1/Acuerdos/2001-12-21 DOCM.pdf',
         ROOT + '3_Modificaciones Puntuales/2002-10-23 MP-5 CREACION SECTOR NORTE 1/2_Planos/plano.JPG']


class MalagonParserTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        rows = parse_projects(ATTRS, NAMES)
        self.assertEqual(len(rows), 3)
        base = next(r for r in rows if r['tipo'] == 'planeamiento_urbanistico')
        self.assertEqual(base['fecha_aprob'], '1989-04-13')
        self.assertEqual(len(base['documentos']), 2)
        mp4 = next(r for r in rows if r['titulo'].startswith('MP-4'))
        self.assertEqual(len(mp4['documentos']), 2)
        self.assertIsNone(mp4['fecha_aprob'])
        self.assertEqual(mp4['fecha_carpeta_sin_semantica'], '2001-10-18')
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fase'])
            self.assertIsNone(row['geometry'])
            self.assertFalse(row['publication_ready'])
            self.assertTrue(all(d['url'] == ATTRS['DESCARGA'] for d in row['documentos']))
        self.assertEqual({r['id'] for r in rows}, {r['id'] for r in parse_projects(ATTRS, list(reversed(NAMES)))})

    def test_reject_wrong_municipality_or_province_and_host(self):
        for key, value in [('COD_INE', '13053'), ('COD_PROV', '28'), ('MUNICIPIO', 'Málaga'), ('DESCARGA', 'https://example.org/file.zip')]:
            attrs = deepcopy(ATTRS)
            attrs[key] = value
            with self.assertRaises(ValueError):
                parse_projects(attrs, NAMES)

    def test_fail_on_empty_or_changed_structure(self):
        for names in [[], ['other/plan.pdf'], [ROOT + 'new-layout/a.pdf'], [NAMES[2]]]:
            with self.assertRaises(ValueError):
                parse_projects(ATTRS, names)

    def test_complete_zip_directory_and_metadata_exclusion(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            for name in NAMES + [ROOT + '1_Normativa/._TEXTOS_NNSS.pdf', ROOT + 'Thumbs.db']:
                z.writestr(name, b'%PDF-1.7 test')
        data = stream.getvalue()
        self.assertEqual(parse_archive_directory(data, 0, len(data)), sorted(NAMES))
        with self.assertRaises(ValueError):
            parse_archive_directory(data[:-2], 0, len(data))
        with self.assertRaises(ValueError):
            parse_archive_directory(data[-22:], len(data) - 22, len(data))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('malagon')
        self.assertEqual(manifest.nombre, 'Malagón')
        self.assertEqual(manifest.provincia, 'Ciudad Real')
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = MalagonAyuntamientoAdapter().backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_truncation_and_missing_ids_preserve_previous_output(self):
        for payload in [{'exceededTransferLimit': True}, {'objectIds': []}, {'error': {'message': 'failure'}}]:
            with TemporaryDirectory() as directory:
                out = Path(directory) / 'proyectos.jsonl'
                out.write_text('previous snapshot')
                with patch('municipio.adapters.malagon.requests.Session') as session:
                    response = session.return_value.__enter__.return_value.get.return_value
                    response.json.return_value = payload
                    with self.assertRaises(ValueError):
                        MalagonAyuntamientoAdapter().backfill_proyectos(out)
                self.assertEqual(out.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
