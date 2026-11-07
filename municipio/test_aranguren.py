import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.aranguren import ArangurenAyuntamientoAdapter, SOURCE

BON = 'https://bon.navarra.es/es/anuncio/-/texto/2022/223/13'
PDF = 'https://www.navarra.es/appsext/DescargarFichero/default.aspx?CodigoCompleto=Portal@@@epub/BON/L2213506_ARANGUREN_PGM.pdf'
NARRATIVE = ('Mediante Orden Foral 61E/2022 , de 26 de abril, del consejero, '
             'se aprobó definitivamente el expediente del Plan General Municipal de Aranguren. '
             'Anuncio previo: 5 de octubre de 2022. Mutilva, 5 de octubre de 2022.')
INVENTORY = f'''<main><div id="planmunicipal"><p>{NARRATIVE}</p>
<a href="{BON}">Orden Foral</a><a href="{BON}">Anuncio BON</a>
<a href="{PDF}">Plan General Municipal (PDF)</a></div>
<article class="noticia"><a href="/licitacion/">Licita Escuela de Música</a></article>
<a href="/noticias/page/2/" rel="next">Más noticias</a></main>'''
NOTICE = f'''<main><a href="/es/boletin/-/sumario/2022/223">
BOLETÍN Nº 223 - 11 de noviembre de 2022</a><p>{NARRATIVE}</p>
<a href="{PDF}">Plan General Municipal</a></main>'''
NOTICE = NOTICE.replace('2022 ,', '2022,')


class ArangurenTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        row = ArangurenAyuntamientoAdapter.parse_inventory(INVENTORY)
        row = ArangurenAyuntamientoAdapter.corroborate(row, NOTICE)
        self.assertEqual(row['fecha_aprob'], '2022-04-26')
        self.assertEqual(row['fecha_publicacion'], '2022-11-11')
        self.assertIsNone(row['fecha'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '31023')
        self.assertIsNone(row['geometry'])

    def test_missing_or_unrelated_source_fails(self):
        for html in ('<main>Licencia de obras: formulario</main>',
                     INVENTORY.replace('Aranguren', 'Zalla'),
                     INVENTORY.replace(PDF, '/formulario/'),
                     INVENTORY.replace('id="planmunicipal"', 'id="removed"')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                ArangurenAyuntamientoAdapter.parse_inventory(html)

    def test_scoped_pagination_fails(self):
        html = INVENTORY.replace('</div>', '<a rel="next" href="?page=2">Siguiente</a></div>')
        with self.assertRaises(ValueError):
            ArangurenAyuntamientoAdapter.parse_inventory(html)

    def test_contradictory_or_incomplete_bon_fails(self):
        row = ArangurenAyuntamientoAdapter.parse_inventory(INVENTORY)
        for html in (NOTICE.replace('26 de abril', '27 de abril'),
                     NOTICE.replace('Aranguren', 'Zalla'),
                     NOTICE.replace(PDF, '/other.pdf'),
                     NOTICE.replace('BOLETÍN Nº 223', 'No date')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                ArangurenAyuntamientoAdapter.corroborate(copy.deepcopy(row), html)

    def test_snapshot_and_disabled_licences(self):
        adapter = ArangurenAyuntamientoAdapter('aranguren')
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'records.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, NOTICE]) as fetch:
                result = adapter.update_proyectos(path, Path(d) / 'state.json')
                self.assertEqual(result['rows'], 1)
                self.assertEqual(json.loads(path.read_text())['id'], 'aranguren-proy-pgm')
                self.assertEqual([call.args[0] for call in fetch.call_args_list], [SOURCE, BON])
            with patch.object(adapter, '_fetch', side_effect=AssertionError('No licence network access')):
                self.assertEqual(adapter.update_licencias(path, Path(d) / 'state.json')['status'], 'disabled')
                self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
