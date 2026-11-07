"""Offline parser regressions; live captures are kept separately in evidence/."""
import tempfile
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

from municipio.adapters.sant_joan_de_vilatorrada import SantJoanDeVilatorradaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

# Deliberately small synthetic markup models the municipal inventory structure.
FIXTURE = '''<div id="content-core"><p>El Pla d'Ordenació Urbanística de Sant Joan de Vilatorrada es va aprovar definitivament el dia 11 de juny de 2003. Fins a data d'avui s'han aprovat les següents modificacions:</p>
<ol>
<li>Modificació puntual del POUM PA-01, aprovada definitivament el 20/10/2005.</li>
<li>Modificació de la delimitació i la modalitat d’actuació del PA-09.</li>
<li>Pla Especial urbanístic de catàleg de masies, cases rurals i altres edificacions existents en SNU, aprovat el 19/09/2018.</li>
<li>Modificació puntual del POUM PA-02, aprovada el 03/03/2016.</li>
</ol>
<a href="https://seu-e.cat/documents/3224802/normes">Normes urbanístiques del POUM</a>
<a href="https://seu-e.cat/documents/3224802/mapa">Qualificació del sòl</a>
<a href="https://seu-e.cat/documents/3224802/masies">Pla especial de masies. Fitxes</a>
<a href="https://seu-e.cat/documents/3224802/masies">Pla especial de masies. Fitxes</a>
<a href="/tramits/llicencia">Sol·licitud de llicència</a>
<time datetime="2026-10-01">Page update</time></div>'''


class PlanningTests(unittest.TestCase):
    def test_instruments_dates_and_grouping(self):
        rows = Adapter.parse_projects(FIXTURE)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]['fecha_aprob'], '2003-06-11')
        self.assertEqual(rows[1]['fecha_aprob'], '2005-10-20')
        self.assertEqual(rows[1]['fase'], 'aprobación definitiva')
        self.assertIsNone(rows[2]['fecha_aprob'])
        self.assertIsNone(rows[2]['fase'])
        self.assertEqual(rows[3]['fecha_aprob'], '2018-09-19')
        self.assertEqual(rows[3]['fase'], 'aprobación')
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[3]['documentos']), 1)
        for r in rows:
            self.assertIsNone(r['fecha_publicacion'])
            self.assertIsNone(r['fecha_acuerdo'])
            self.assertIsNone(r['geometry'])
            self.assertIsNone(r['lat'])
            self.assertEqual(r['codigo_ine'], '08218')
        self.assertEqual(rows[4]['titulo'], 'Modificació puntual del POUM PA-02')

    def test_stable_identity_when_reordered_or_approval_changes(self):
        rows = Adapter.parse_projects(FIXTURE)
        changed = Adapter.parse_projects(FIXTURE.replace('20/10/2005', '21/10/2005'))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in changed])
        soup = BeautifulSoup(FIXTURE, 'html.parser')
        items = list(soup.ol.find_all('li', recursive=False))
        for item in reversed(items):
            soup.ol.append(item.extract())
        reordered = Adapter.parse_projects(str(soup))
        self.assertEqual({r['titulo']: r['id'] for r in rows},
                         {r['titulo']: r['id'] for r in reordered})

    def test_fail_closed_on_markup_or_inventory_changes(self):
        for html in ('<h1>Login</h1>', '<div id="content-core">Llicència urbanística</div>',
                     FIXTURE.replace('<ol>', '<ul>').replace('</ol>', '</ul>'),
                     FIXTURE.replace('</ol>', '<li>Anunci de contractació</li></ol>'),
                     FIXTURE.replace('</div>', '<a rel="next" href="?page=2">Next</a></div>'),
                     FIXTURE.replace('20/10/2005', '31/02/2005'),
                     FIXTURE.replace('20/10/2005', '20/10/2005 i 21/10/2005'),
                     FIXTURE.replace('Pla especial de masies. Fitxes', 'Unknown document')):
            with self.subTest(html=html[-100:]), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_disabled_licences_and_manifest_resolution(self):
        m = load_manifest('sant-joan-de-vilatorrada')
        adapter = load_portal_adapter(m)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(m.licencias.enabled)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(p)['status'], 'disabled')
            self.assertFalse(p.exists())


if __name__ == '__main__':
    unittest.main()
