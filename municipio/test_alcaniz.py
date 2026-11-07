"""Offline parser regression tests; fixtures model the reviewed municipal markup."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.alcaniz import AlcanizAyuntamientoAdapter as Adapter


PLANNING = '''<div class="article"><h1>Plan General de Ordenación Urbana</h1>
<h2>Documentación escrita</h2><a href="https://h.alcaniz.es/memoria.pdf">Memoria descriptiva</a>
<h2>Documentación gráfica - planos</h2><a href="/planos">Alineaciones</a>
<h2>Publicación normas urbanísticas</h2><a href="/bop2013.pdf">BOP Teruel 18 junio de 2013</a>
<h2>Modificaciones aprobadas</h2><ol>
<li><a href="/mod4.pdf">Modificación 4</a>
<a href="/bop2021.pdf">BOP Teruel 27 de diciembre de 2021</a>
<a href="/anexo.pdf">Anexo Art. 135</a></li></ol></div>'''
WORKS = '''<h1>Urbanismo</h1><div class="fw_light m_bottom_12">
<p>Puede acceder a toda la información sobre el plan general: <a href="/plan">planeamiento</a></p>
<p>Proyecto básico y de ejecución de la Remodelación del Parque Urbano de la Avenida de Aragón en Alcañiz; descarga PDF del Proyecto en:
<a href="https://www.dropbox.com/scl/fi/real/2024_03_04.pdf?rlkey=public&amp;dl=0">descarga</a></p>
<p>Solicitud de licencia <a href="/impreso.pdf">formulario</a></p></div>'''


class AlcanizTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        plan, amendment = Adapter.parse_planning(PLANNING)
        self.assertEqual(len(plan['documentos']), 3)
        self.assertEqual(len(amendment['documentos']), 3)
        self.assertEqual(amendment['fecha_publicacion'], '2021-12-27')
        self.assertEqual(plan['fecha_publicacion'], '2013-06-18')
        for row in [plan, amendment]:
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['geometry'])

    def test_works_are_projects_without_fabricated_dates(self):
        rows = Adapter.parse_works(WORKS)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['fase'])
        self.assertIsNone(rows[0]['lat'])
        self.assertIn('rlkey=public&dl=0', rows[0]['documentos'][0]['url'])

    def test_duplicate_work_paragraphs_group_documents(self):
        paragraph = '<p>Proyecto' + WORKS.split('<p>Proyecto')[1].split('</p>')[0] + '</p>'
        doubled = WORKS.replace('</div>', paragraph + '</div>')
        self.assertEqual(len(Adapter.parse_works(doubled)), 1)
        self.assertEqual(len(Adapter.parse_works(doubled)[0]['documentos']), 1)

    def test_pagination_rejected(self):
        for parser, html in [(Adapter.parse_planning, PLANNING), (Adapter.parse_works, WORKS)]:
            with self.subTest(parser=parser.__name__), self.assertRaises(ValueError):
                parser(html + '<a rel="next" href="?page=2">Siguiente</a>')

    def test_changed_or_empty_inventory_rejected(self):
        for parser in [Adapter.parse_planning, Adapter.parse_works]:
            with self.assertRaises(ValueError):
                parser('<h1>Login</h1><a href="/mod.pdf">Modificación 1</a>')
        with self.assertRaises(ValueError):
            Adapter.parse_works(WORKS.replace('Proyecto básico y de ejecución', 'Anuncio de licitación'))

    def test_missing_publication_not_guessed(self):
        with self.assertRaises(ValueError):
            Adapter.parse_planning(PLANNING.replace('BOP Teruel 27 de diciembre de 2021', 'Documento'))

    def test_failed_live_refresh_preserves_existing_output(self):
        adapter = Adapter('alcaniz')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            with patch('municipio.adapters.alcaniz.requests.get', side_effect=ValueError('network failure')):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(out.read_text(), 'previous snapshot\n')


if __name__ == '__main__':
    unittest.main()
