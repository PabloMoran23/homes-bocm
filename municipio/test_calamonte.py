"""Offline, reduced fixtures model the verified inventory and swapped PDF labels."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.calamonte import (
    API, SOURCE, CalamonteAyuntamientoAdapter, enrich_pgm,
    parse_inventory, parse_modification, text_date,
)
from municipio.manifest import load_manifest, load_yaml

INVENTORY = '''
<h3>NORMAS SUBSIDIARIAS</h3><ul>
<li><h3><a href="https://drive.google.com/file/d/public-plan/view">Plan General Municipal Aprobado por CUOTEX el 25/5/2023 y publicado en el DOE con fecha de 13/3/2024</a></h3></li>
<li>Planos<ul><li><a href="/NNSS/Termino.pdf">Término Municipal</a></li>
<li><a href="/NNSS/UA11.pdf">UA-11</a></li></ul></li>
<li><a href="/NNSS/Ordenanzas.pdf">Ordenanzas (2015_06_23)</a></li></ul>
<h3>PLAN PARCIAL DEHESA DEL REY</h3><ul>
<li>Planos<ul><li><a href="/PlanParcial/1.pdf">Plano 1</a></li>
<li><a href="/PlanParcial/2.pdf">Plano 2</a></li></ul></li>
<li><a href="/PlanParcial/ordenanzas.pdf">Ordenanzas PP U.E. AR-01 DE NNSS CALAMONTE</a></li>
<li><a href="/swapped-pp.pdf">Aprobación definitiva de la modificación puntual n.º 1/2014 de las NNSS de Planeamiento Municipal de Calamonte.</a></li>
<li><a href="/swapped-nnss.pdf">Aprobación definitiva de la modificación puntual del Plan Parcial de los Sectores SUP-I1 y SUP-I2 de Calamonte</a></li></ul>
<h3>MODELOS DE LICENCIA URBANÍSTICA</h3><ul>
<li><a href="/solicitud.pdf">MODELO 1.1 SOLICITUD LICENCIA DE OBRAS</a></li></ul>
'''
PDF_PP = '''NÚMERO 70 Jueves, 15 de abril de 2010 9349
RESOLUCIÓN de 25 de junio de 2009, por la que se aprueba definitivamente
la modificación puntual del Plan Parcial de los Sectores SUP-I1 y SUP-I2 de Calamonte.
(2010060841) La Comisión de Urbanismo y Ordenación del Territorio'''
PDF_NNSS = '''NÚMERO 55 Viernes, 20 de marzo de 2015 8547
RESOLUCIÓN de 29 de enero de 2015, por la que se aprueba definitivamente
la modificación puntual n.º 1/2014 de las Normas Subsidiarias de Calamonte.
(2015060595) La Comisión de Urbanismo y Ordenación del Territorio'''
DOE_FIXTURE = '''<p>Acuerdo de 25 de mayo de 2023, de aprobación definitiva parcial del Plan General Municipal de Calamonte.</p>
<p>Fecha Publicación: miércoles, 13 de marzo de 2024 Apartado: III</p>
<p>Dejar en suspenso la ordenación de la UA-9 y terrenos colindantes en UA-1.</p>'''


class CalamonteTests(unittest.TestCase):
    def test_group_documents_and_exclude_forms(self):
        rows, modifications = parse_inventory(INVENTORY)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 3, 3])
        self.assertEqual(len(modifications), 2)
        self.assertNotIn('solicitud.pdf', json.dumps(rows))
        self.assertNotIn('/NNSS/', json.dumps(rows[0]))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '06025')
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertFalse(row['publication_ready'])
        self.assertEqual(rows, parse_inventory(INVENTORY)[0])

    def test_swapped_modifications_follow_pdf_identity(self):
        _, docs = parse_inventory(INVENTORY)
        pp = parse_modification(PDF_PP, docs[0])
        nnss = parse_modification(PDF_NNSS, docs[1])
        self.assertIn('SUP-I1', pp['titulo'])
        self.assertIn('1/2014', nnss['titulo'])
        self.assertEqual(pp['fecha_acuerdo'], '2009-06-25')
        self.assertEqual(pp['fecha_publicacion'], '2010-04-15')
        self.assertEqual(nnss['fecha_acuerdo'], '2015-01-29')
        self.assertEqual(nnss['fecha_publicacion'], '2015-03-20')
        self.assertTrue(pp['source_label_mismatch'])
        self.assertTrue(nnss['source_label_mismatch'])
        corrected = dict(docs[1], titulo_enlace='Modificación puntual n.º 1/2014')
        self.assertFalse(parse_modification(PDF_NNSS, corrected)['source_label_mismatch'])
        self.assertEqual(nnss['id'], parse_modification(PDF_NNSS, corrected)['id'])

    def test_partial_approval_dates(self):
        row = parse_inventory(INVENTORY)[0][0]
        enrich_pgm(row, DOE_FIXTURE)
        self.assertEqual(row['fase'], 'aprobación definitiva parcial')
        self.assertEqual(row['fecha_acuerdo'], '2023-05-25')
        self.assertEqual(row['fecha_publicacion'], '2024-03-13')
        self.assertIn('UA-9', row['limitaciones'])
        self.assertEqual(len(row['documentos']), 2)

    def test_fail_closed_on_source_changes(self):
        for html in ('', '<h3>MODELOS</h3>', INVENTORY + '<a rel="next" href="?page=2">Next</a>',
                     INVENTORY.replace('<h3>PLAN PARCIAL DEHESA DEL REY</h3>', '<h3>Removed</h3>'),
                     INVENTORY.replace('/NNSS/Termino.pdf', 'https://example.net/unknown.pdf')):
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_modification('application form', {'url': SOURCE, 'titulo_enlace': 'licencia'})
        with self.assertRaises(ValueError):
            enrich_pgm(parse_inventory(INVENTORY)[0][0], 'Approval unverified')
        with self.assertRaises(ValueError):
            text_date('31 de febrero de 2024')

    def test_api_pagination_is_not_truncated(self):
        class Response:
            headers = {'X-WP-TotalPages': '2', 'X-WP-Total': '11'}
            url = API
            content = b'[]'
            def raise_for_status(self):
                pass
            def json(self):
                return [{'slug': 'oficina-tecnica', 'link': SOURCE, 'content': {'rendered': INVENTORY}}]
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.calamonte.requests.Session.get', return_value=Response()):
            out = Path(tmp) / 'projects.jsonl'
            with self.assertRaises(ValueError):
                CalamonteAyuntamientoAdapter().backfill_proyectos(out)
            self.assertFalse(out.exists())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('calamonte')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '06025')
        self.assertEqual(manifest.provincia, 'Badajoz')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(CalamonteAyuntamientoAdapter().backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
