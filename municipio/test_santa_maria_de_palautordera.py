import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_maria_de_palautordera import (
    PLANNING, WORKS, SantaMariaDePalautorderaAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest


PLAN = '''<main id="main-content"><h1>POUM: Pla d'Ordenació Urbanística Municipal</h1>
<div class="ddbbtext"><p>El Text refós del Pla d'Ordenació Urbanística Municipal de Santa Maria de Palautordera
va ser aprovat definitivament per la Comissió Territorial d'Urbanisme en data 22 de setembre de 2011,
i publicat al Diari Oficial de la Generalitat de Catalunya (DOGC) el 15 de desembre de 2011.</p></div>
<div class="ddbbtext"><ul><li>2022-Modificació puntual del POUM a
<a href="/media/repository/normativa/pla.pdf">can Saleta</a>
<a href="/media/repository/normativa/annex.pdf">Annex</a></li>
<li>2012-Pla especial <a href="https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/262161">Can Lluís</a></li>
</ul></div><section id="page-documents"><a href="/media/repository/POUM.pdf">POUM</a>
<a href="/media/repository/Normes.pdf">Normes urbanístiques</a></section></main>'''
WORK = '''<main id="main-content"><h1>Obra municipal ordinària</h1><section id="page-documents">
<a href="/media/repository/OBRA_MUNICIPAL_ORDINaRIA/Projecte_aprovat_inicialment.pdf">
Aprovació incial del projecte d'estabilització del marge esquerre Torrent del Reguissol al C/ Nou núm. 30-46
<span>(313.9MB)</span></a></section></main>'''


class ParserTests(unittest.TestCase):
    def test_dates_documents_and_identity(self):
        rows = Adapter.parse_planning(PLAN)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['fecha_aprob'], '2011-09-22')
        self.assertEqual(rows[0]['fecha_publicacion'], '2011-12-15')
        self.assertIsNone(rows[0]['fecha_acuerdo'])
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertEqual(rows[1]['anio_referencia_fuente'], 2022)
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertIsNone(rows[1]['fase'])
        self.assertEqual(rows[2]['rpuc_id'], '262161')
        for row in rows:
            self.assertIsNone(row['lat'])
            self.assertFalse(row['publication_ready'])
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in Adapter.parse_planning(PLAN)])

    def test_missing_publication_does_not_reuse_approval(self):
        html = PLAN.replace(',\ni publicat al Diari Oficial de la Generalitat de Catalunya (DOGC) el 15 de desembre de 2011.', '.')
        row = Adapter.parse_planning(html)[0]
        self.assertEqual(row['fecha_aprob'], '2011-09-22')
        self.assertIsNone(row['fecha_publicacion'])

    def test_document_links_deduplicated(self):
        html = PLAN.replace('<a href="/media/repository/Normes.pdf">', '<a href="/media/repository/POUM.pdf">')
        self.assertEqual(len(Adapter.parse_planning(html)[0]['documentos']), 1)

    def test_rejects_shells_forms_and_changed_inventory(self):
        for html in ('<h1>Login</h1>', '<h1>Llicència d’obra major</h1>',
                     PLAN.replace('2022-Modificació puntual del POUM', '2022-Licitació'),
                     PLAN.replace('id="page-documents"', 'id="missing"')):
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                Adapter.parse_planning(html)

    def test_pagination_cannot_be_silently_lost(self):
        for extra in ('<nav class="pagination">2</nav>', '<a href="?page=2" rel="next">2</a>',
                      '<a href="?page=2">Següent</a>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Adapter.parse_planning(PLAN.replace('</main>', extra + '</main>'))

    def test_work_is_project_with_unknown_dates(self):
        row = Adapter.parse_works(WORK)[0]
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertNotIn('313.9MB', row['titulo'])
        with self.assertRaises(ValueError):
            Adapter.parse_works(WORK.replace('Aprovació incial del projecte', 'Anunci de licitació'))

    def test_snapshot_and_failure_preserve_previous_output(self):
        adapter = Adapter('santa-maria-de-palautordera')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[PLAN, WORK]):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 4)
            content = out.read_text()
            self.assertEqual(len([json.loads(x) for x in content.splitlines()]), 4)
            with patch.object(adapter, '_fetch', side_effect=[PLAN, '<h1>Login</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), content)
            self.assertEqual(adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest_adapter(self):
        manifest = load_manifest('santa-maria-de-palautordera')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)
        self.assertTrue(manifest.portal.adapter.endswith(':SantaMariaDePalautorderaAyuntamientoAdapter'))
        self.assertEqual(manifest.portal.config['ine_code'], '08259')


if __name__ == '__main__':
    unittest.main()
