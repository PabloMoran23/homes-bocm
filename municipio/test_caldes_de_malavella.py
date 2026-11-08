import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.caldes_de_malavella import (
    CaldesDeMalavellaAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

HTML = '''<div itemprop="articleBody"><h3>Accés al planejament vigent</h3><ul>
<li><a href="http://ptop.gencat.cat/rpucportal/AppJava/cercaExpedient.do?codintExp=254386&amp;reqCode=veureDocument">POUM</a></li>
<li><a href="http://ptop.gencat.cat/rpucportal/AppJava/cercaExpedient.do?codintExp=270446">Modificació puntual del POUM</a></li>
<li><a href="http://ptop.gencat.cat/rpucportal/AppJava/cercaExpedient.do?codintExp=254386&amp;reqCode=veure">Registre de planejament urbanístic de Catalunya/Caldes de Malavella</a></li>
<li><a href="/images/Normativa_POUM.pdf">Normativa POUM</a></li>
<li><a href="/images/TUC.pdf">Trama Urbana Consolidada</a></li>
</ul></div>'''
TEXT = '''1/165 Diari Oficial de la Generalitat de Catalunya Núm. 6549 - 28.1.2014
EDICTE de 21 de gener de 2014
La Comissió Territorial d'Urbanisme de Girona, en la sessió de 9 d’octubre de 2013,
va adoptar l'acord següent:
Exp.: 2010 / 042682 / G
Pla d'ordenació urbanística municipal, al terme municipal de Caldes de Malavella
-1 Aprovar definitivament el Pla d'ordenació urbanística municipal
\fAnnex: en la sessió de 1 d’abril de 2020'''


class ParserTests(unittest.TestCase):
    def test_document_grouping(self):
        inventory = parse_inventory(HTML)
        self.assertEqual(inventory['rpuc_id'], '254386')
        self.assertEqual(len(inventory['documentos']), 3)
        self.assertFalse(any('270446' in d['url'] or 'TUC' in d['url'] for d in inventory['documentos']))

    def test_dates_provenance_and_no_coordinates(self):
        row = parse_project(parse_inventory(HTML), TEXT)
        self.assertEqual(row['fecha_publicacion'], '2014-01-28')
        self.assertEqual(row['fecha_acuerdo'], '2013-10-09')
        self.assertEqual(row['fecha_aprob'], '2013-10-09')
        self.assertIsNone(row['fecha'])
        self.assertEqual(row['expediente'], '2010 / 042682 / G')
        self.assertIsNone(row['lat'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['date_provenance']['fecha_acuerdo'], row['url_documento'])

    def test_identity_stable_across_link_order(self):
        inv = parse_inventory(HTML)
        other = copy.deepcopy(inv)
        other['documentos'].reverse()
        self.assertEqual(parse_project(inv, TEXT)['id'], parse_project(other, TEXT)['id'])

    def test_rejects_navigation_login_forms_and_pagination(self):
        for html in ('<a>POUM</a>', '<h1>Identifica’t</h1>', HTML.replace('Normativa POUM', 'Sol·licitud de llicència'),
                     HTML.replace('</div>', '<div class="pagination"><a rel="next">2</a></div></div>'),
                     HTML.replace('ptop.gencat.cat', 'example.org')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_rejects_missing_approval_wrong_municipality_or_missing_dates(self):
        inv = parse_inventory(HTML)
        for text in ('Sol·licitud de llicència', TEXT.replace('Caldes de Malavella', 'Girona'),
                     TEXT.replace('Aprovar definitivament', 'Informació pública'),
                     TEXT.replace('28.1.2014', 'data desconeguda'), TEXT.replace('9 d’octubre de 2013', 'data desconeguda')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_project(inv, text)

    def test_failed_source_preserves_previous_snapshot(self):
        adapter = CaldesDeMalavellaAyuntamientoAdapter('caldes-de-malavella')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            path.write_text('previous snapshot\n')
            with patch.object(adapter, '_fetch', side_effect=[HTML.encode(), b'<html>login</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('caldes-de-malavella')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertEqual(manifest.portal.config['ine_code'], '17033')
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
