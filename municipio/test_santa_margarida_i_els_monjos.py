import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_margarida_i_els_monjos import (
    MUNICIPIO, SOURCE, SantaMargaridaIElsMonjosAyuntamientoAdapter,
    dossier_from_html, parse_project,
)

# Minimal schema fixtures, deliberately distinct dates and nested attachments.
HTML = '''<h1><span>Normativa d'urbanisme</span><a><span>?</span></a></h1><p>Consulta el Pla d'Ordenació Urbanísrtica Municipal</p>
<a href="http://ptop.gencat.net/rpucportal/AppJava/cercaExpedient.do?reqCode=veureDocument&amp;codintExp=251954">RPUC</a>'''
DETAIL = {'codintExp': 251954, 'municipi': MUNICIPIO,
          'tipologiaCA': "Pla d'ordenació urbanística municipal ",
          'tema': "Pla d'ordenació urbanística municipal ",
          'dataAprovacio': '2018-05-08', 'dataPublicacio': '2018-06-26',
          'numComplet': '2010 / 040956 / B'}
TREE = [{'label': 'Memòria', 'data': [{'idDocument': 335048, 'nomDocument': 'Memòria.pdf'}],
         'children': [{'label': 'Acord', 'data': [{'idDocument': 335066, 'nomDocument': 'Acord.pdf'}]}]}]


class ParserTests(unittest.TestCase):
    def test_identity_dates_and_grouped_documents(self):
        dossier, link = dossier_from_html(HTML)
        row = parse_project(DETAIL, TREE, dossier, link)
        self.assertEqual(row['fecha_aprob'], '2018-05-08')
        self.assertEqual(row['fecha_publicacion'], '2018-06-26')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['lat'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['categorias'], [['Memòria', 'Acord']])
        self.assertIn('documentId=335066', row['documentos'][1]['url'])

    def test_missing_dates_do_not_use_page_update(self):
        detail = dict(DETAIL, dataAprovacio=None, dataPublicacio=None)
        row = parse_project(detail, TREE, '251954', 'source')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_reject_wrong_municipality_dossier_type_or_empty_tree(self):
        for detail in [dict(DETAIL, municipi='Other'), dict(DETAIL, codintExp=1),
                       dict(DETAIL, tipologiaCA='Formulari')]:
            with self.assertRaises(ValueError):
                parse_project(detail, TREE, '251954', 'source')
        for tree in [[], {'results': TREE, 'next': 'page2'}]:
            with self.assertRaises(ValueError):
                parse_project(DETAIL, tree, '251954', 'source')

    def test_reject_navigation_or_ambiguous_dossiers(self):
        for html in ['<h1>Login</h1>', HTML.replace('Consulta el Pla', 'Other'),
                     HTML + HTML.replace('251954', '123456')]:
            with self.assertRaises(ValueError):
                dossier_from_html(html)

    def test_dedup_retains_category_provenance(self):
        tree = copy.deepcopy(TREE)
        tree.append({'label': 'Altres', 'data': tree[0]['data']})
        row = parse_project(DETAIL, tree, '251954', 'source')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos'][0]['categorias']), 2)

    def test_adapter_refresh_and_disabled_licences(self):
        adapter = SantaMargaridaIElsMonjosAyuntamientoAdapter('santa-margarida-i-els-monjos')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[HTML, json.dumps(DETAIL), json.dumps(TREE)]):
                result = adapter.update_proyectos(path, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(path.read_text().splitlines()), 1)
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
