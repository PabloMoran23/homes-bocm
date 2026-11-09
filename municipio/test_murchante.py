"""Parser and snapshot tests; synthetic fixtures mirror reviewed Sedipualba markup."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.murchante import (
    SOURCE, MurchanteAyuntamientoAdapter, group_records, parse_documents,
    parse_edict, parse_inventory,
)
from municipio.manifest import load_manifest

TITLE = 'Edicto nueva exposición al público modificación estructurante del Plan General Municipal'


def inventory(extra=''):
    return f'''AYUNTAMIENTO DE MURCHANTE<div id="contenido"><table class="gridview">
    <tr><td><a href="anuncio.aspx?id=123">Abrir</a></td>
    <td>09/11/2026 - 09/12/2026</td><td>{TITLE}</td></tr>
    <tr><td><a href="anuncio.aspx?id=124">Abrir</a></td><td>09/11/2026 - 09/12/2026</td>
    <td>Formulario solicitud licencia de obras</td></tr>
    <tr><td><a href="anuncio.aspx?id=125">Abrir</a></td><td>09/11/2026 - 09/12/2026</td>
    <td>Contratación de obras de alumbrado público</td></tr></table>{extra}</div>'''


def detail():
    return f'''<div id="leer"><h2>{TITLE}</h2>
    <div class="fechas-exposicion">Expuesto actualmente desde el día 09/11/2026</div>
    <div class="adjunto"><div class="adjunto-titulo">{TITLE}</div>
    <a href="documento.aspx?id=456&amp;modo=guardar">Descargar</a></div></div>'''


EDICT = '''Expediente 123456Z
El Pleno del Ayuntamiento de Murchante, en sesión celebrada el día 5 de
noviembre de 2026 aprobó realizar nueva información pública del expediente
de la modificación estructurante del Plan General Municipal de Murchante en
   SELLO
las zonas A y B del SGEQAP del polígono 3 paraje de Campo Bajo.
Se somete el expediente a nueva información pública durante el plazo de un mes.
Murchante, a 9 de noviembre de 2026.'''


class MurchanteParserTests(unittest.TestCase):
    def test_inventory_excludes_forms_and_procurement_and_deduplicates(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['fecha_publicacion'], '2026-11-09')
        self.assertEqual(rows[0]['fecha_fin_exposicion_tablon'], '2026-12-09')
        self.assertEqual(rows[0]['url'], SOURCE + 'anuncio.aspx?id=123')
        self.assertEqual(len(parse_inventory(inventory() + inventory())), 1)

    def test_fail_closed_for_paging_empty_changed_or_foreign_source(self):
        for html in (inventory('<a href="?page=2">2</a>'),
                     inventory('<a href="javascript:__doPostBack(\'ctl\',\'Page$Next\')">Siguiente</a>'),
                     '<html>Unavailable</html>', inventory().replace(TITLE, 'Oferta de empleo'),
                     inventory().replace('href="anuncio.aspx?id=123"', 'href="https://example.org/tablondeanuncios/anuncio.aspx?id=123"')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_detail_retains_document_provenance_and_checks_dates(self):
        notice = parse_inventory(inventory())[0]
        docs = parse_documents(detail(), notice)
        self.assertEqual(docs[0]['url'], SOURCE + 'documento.aspx?id=456&modo=guardar')
        self.assertEqual(docs[0]['source_url'], notice['url'])
        for html in (detail().replace('09/11/2026', '10/11/2026'),
                     detail().replace('class="adjunto"', 'class="missing"'),
                     detail().replace(TITLE, 'Otra noticia')):
            with self.assertRaises(ValueError):
                parse_documents(html, notice)

    def test_edict_distinguishes_agreement_from_publication_and_signature(self):
        result = parse_edict(EDICT)
        self.assertEqual(result['fecha_acuerdo'], '2026-11-05')
        self.assertEqual(result['expediente'], '123456Z')
        self.assertEqual(result['fase'], 'nueva información pública')
        self.assertIn('Campo Bajo', result['titulo'])
        self.assertNotIn('SELLO', result['titulo'])
        self.assertNotIn('fecha_aprob', result)
        for text in ('Solicitud de licencia', EDICT.replace('123456Z', ''),
                     EDICT.replace('aprobó realizar nueva información pública', 'debatió'),
                     EDICT + ' Expediente 654321Z'):
            with self.assertRaises(ValueError):
                parse_edict(text)

    def test_grouping_retains_documents_and_notice_dates(self):
        first = {**parse_edict(EDICT), 'id': 'test', 'url': 'notice1',
                 'fecha_publicacion': '2026-11-09', 'descripcion': 'first',
                 'documentos': [{'url': 'doc1'}], 'avisos': [{'url': 'notice1'}]}
        second = copy.deepcopy(first)
        second.update(url='notice2', fecha_publicacion='2026-11-10',
                      documentos=[{'url': 'doc2'}], avisos=[{'url': 'notice2'}])
        rows = group_records([first, second])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[0]['avisos']), 2)
        self.assertEqual(rows[0]['url'], 'notice2')

    def test_snapshot_contract_and_no_output_on_failure(self):
        adapter = MurchanteAyuntamientoAdapter('murchante')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            fake_process = type('Result', (), {'stdout': EDICT.encode()})()
            with patch.object(adapter, '_fetch', side_effect=[inventory(), detail(), b'%PDF-test']), patch(
                    'municipio.adapters.murchante.subprocess.run', return_value=fake_process):
                result = adapter.backfill_proyectos(output)
            row = json.loads(output.read_text())
            self.assertEqual(result['rows'], 1)
            self.assertEqual(row['codigo_ine'], '31176')
            self.assertEqual(row['fecha_acuerdo'], '2026-11-05')
            self.assertEqual(row['fecha_publicacion'], '2026-11-09')
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['geometry'])
            self.assertIs(row['publication_ready'], False)
            before = output.read_bytes()
            with patch.object(adapter, '_fetch', return_value='<html>Error</html>'), self.assertRaises(ValueError):
                adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(adapter.backfill_licencias(Path(directory) / 'lic.jsonl')['status'], 'disabled')

    def test_manifest(self):
        manifest = load_manifest('murchante')
        self.assertEqual(manifest.nombre, 'Murchante')
        self.assertEqual(manifest.provincia, 'Navarra')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.murchante:MurchanteAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
