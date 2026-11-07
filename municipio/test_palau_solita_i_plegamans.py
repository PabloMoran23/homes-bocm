"""Offline parser contracts; synthetic markup, never production records."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.palau_solita_i_plegamans import (
    PalauSolitaIPlegamansAyuntamientoAdapter as Adapter, SOURCE, DERIVED_SOURCE,
)

POUM = '''<h1>POUM, aprovat de forma definitiva</h1>
<div class="element"><p>El POUM ha entrat en vigor en haver-se publicat al DOGC el 30 d'octubre del 2015.</p>
<p>Abans s'havia aprovat de forma definitiva el 23 d'abril del 2015, després de l'aprovació provisional del 26 de març del 2015.</p>
<a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/233866">POUM vigent</a></div>
<div class="element"><h2>Modificacions del POUM</h2><ul>
<li><span>Modificació puntual prova</span><ul>
<li><a href="/files/technical.pdf">Memòria</a></li>
<li><a href="/files/notice.pdf">Documentació plànols</a></li>
<li><a href="/files/notice.pdf">Anunci AD DOGC 17102023</a></li>
</ul></li></ul></div>'''
DERIVED = '''<div class="element"><p>PLANS DERIVATS</p>
<p>PMU 07 Camí Reial</p><p><a href="/files/pmu.pdf">Memòria i plànols</a></p>
<p>Aprov.def Plè Municipal 29/09/2022</p>
<p>SUD 05 Consulta</p><p><a href="/files/consult.pdf">Consulta prèvia</a></p></div>
<div class="element"><p>PROJECTES D'URBANITZACIÓ</p>
<p>PU del PMU 07 Camí Reial</p><p><a href="/files/pu.pdf">Memòria</a></p>
<p>PU del PMU 07 Camí Reial - MEMORIA I PLÀNOLS</p></div>
<div class="element"><p>PROJECTES DE REPARCEL·LACIÓ</p>
<p>PR PMU 07 Camí Reial</p><p><a href="/files/pr.pdf">Memòria</a></p></div>'''


class ParserTests(unittest.TestCase):
    def test_dates_have_distinct_semantics_and_documents_grouped(self):
        base, modification = Adapter.parse_projects(POUM)
        self.assertEqual(base['fecha_publicacion'], '2015-10-30')
        self.assertEqual(base['fecha_aprob'], '2015-04-23')
        self.assertIsNone(base['fecha'])
        self.assertEqual(modification['fecha_publicacion'], '2023-10-17')
        self.assertIsNone(modification['fecha_aprob'])
        self.assertIsNone(modification['fase'])
        self.assertEqual(len(modification['documentos']), 2)
        self.assertEqual(len(modification['documentos'][1]['titulos']), 2)

    def test_missing_dates_not_filled_from_filenames(self):
        html = POUM.replace('30 d\'octubre del 2015', 'data no indicada').replace("23 d'abril del 2015", 'data no indicada').replace('Anunci AD DOGC 17102023', 'Anunci').replace('notice.pdf', 'notice-20231017.pdf')
        for row in Adapter.parse_projects(html):
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['geometry'])

    def test_navigation_login_and_missing_inventory_rejected(self):
        for html in ['<a href="/ca/poum">POUM</a>', '<h1>Login</h1>', POUM.replace('Modificacions del POUM', 'Other')]:
            with self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_unknown_inventory_group_and_pagination_rejected(self):
        for html in [POUM.replace('</ul></div>', '<li>Unexpected record</li></ul></div>'), POUM + '<a rel="next" href="?page=2">Next</a>']:
            with self.assertRaises(ValueError):
                Adapter.parse_projects(html)
        with self.assertRaises(ValueError):
            Adapter.parse_derived(DERIVED + '<div class="pagination">2</div>')

    def test_derived_documents_and_separate_instruments_same_area(self):
        rows = Adapter.parse_derived(DERIVED)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r['id'] for r in rows}), 3)
        self.assertEqual(rows[0]['fecha_acuerdo'], '2022-09-29')
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertTrue(all(r['url'] == DERIVED_SOURCE for r in rows))
        self.assertTrue(all(d['source_url'] == DERIVED_SOURCE for r in rows for d in r['documentos']))
        self.assertIn('MEMORIA I PLÀNOLS', rows[1]['descripcion'])

    def test_missing_derived_section_and_orphan_documents_rejected(self):
        for html in [DERIVED.replace('PLANS DERIVATS', 'Other'), DERIVED.replace('<p>PMU 07 Camí Reial</p>', '')]:
            with self.assertRaises(ValueError):
                Adapter.parse_derived(html)

    def test_update_refreshes_both_inventories_and_is_stable(self):
        adapter = Adapter('palau-solita-i-plegamans')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda url: POUM if url == SOURCE else DERIVED):
                first = adapter.backfill_proyectos(output)
                content = output.read_text()
                second = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(first['rows'], 5)
            self.assertEqual(first, second)
            self.assertEqual(content, output.read_text())
            self.assertEqual(len([json.loads(line) for line in content.splitlines()]), 5)

    def test_disabled_licences(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = Adapter('palau-solita-i-plegamans').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
