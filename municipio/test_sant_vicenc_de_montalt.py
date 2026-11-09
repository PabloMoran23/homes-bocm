import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_vicenc_de_montalt import SantVicencDeMontaltAyuntamientoAdapter as Adapter

OVERVIEW = '''<div id="PRESENTACIO"><div class="presentacio">
<p>FASE APROVACIÓ INICIAL POUM</p>
<p>El passat dia 29 de juny de 2026, el Ple en sessió extraordinària va aprovar inicialment el Pla d'Ordenació Urbanística Municipal (POUM) juntament amb l'Estudi Ambiental Estratègic.</p>
<a href="pagina.php?id=24146">consulta la documentació</a>
<a href="pagina.php?id=24145">consulta els anuncis</a>
</div></div>'''
DOCUMENTS = '''<div id="cos"><a href="ARXIUS/2026/POUM/normes.pdf">Normativa</a>
<a href="ARXIUS/2026/POUM/planols.pdf">Plànols</a></div>'''
NOTICES = '''<div id="DOCUMENT"><div class="dinssinopsi"><ul><li>BOPB: 16 de juliol de 2026</li>
<li>DOGC: 28 de juliol de 2026</li></ul></div><div id="cos">
<a href="ARXIUS/2026/anunci.pdf"></a><a href="ARXIUS/2026/anunci.pdf">Anunci</a></div></div>'''


class ParserTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        rows = Adapter.parse_projects(OVERVIEW, DOCUMENTS, NOTICES)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['fecha_acuerdo'], '2026-06-29')
        self.assertEqual(row['fecha_publicacion'], '2026-07-16')
        self.assertEqual(row['publicaciones'][1]['fecha_publicacion'], '2026-07-28')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][-1]['titulo'], 'Anunci')
        self.assertTrue(all(d['source_url'] in row['source_urls'] for d in row['documentos']))
        self.assertIsNone(row['geometry'])
        self.assertIsNone(row['fecha'])
        self.assertFalse(row['publication_ready'])

    def test_fail_closed_for_navigation_form_or_news(self):
        for overview in ('<a>POUM</a>', OVERVIEW.replace('va aprovar inicialment', 'informa sobre')):
            with self.assertRaises(ValueError):
                Adapter.parse_projects(overview, DOCUMENTS, NOTICES)

    def test_no_assumed_publication_date(self):
        with self.assertRaises(ValueError):
            Adapter.parse_projects(OVERVIEW, DOCUMENTS, NOTICES.replace('BOPB:', 'Altres:'))

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            Adapter.parse_projects(OVERVIEW.replace('29 de juny', '31 de juny'), DOCUMENTS, NOTICES)

    def test_missing_documents_and_changed_provenance(self):
        for docs in ('<div id="cos">Només un formulari</div>', DOCUMENTS.replace('ARXIUS/', 'https://example.org/ARXIUS/')):
            with self.assertRaises(ValueError):
                Adapter.parse_projects(OVERVIEW, docs, NOTICES)

    def test_pagination_not_truncated(self):
        for index in range(3):
            pages = [OVERVIEW, DOCUMENTS, NOTICES]
            pages[index] += '<a href="?page=2" rel="next">2</a>'
            with self.assertRaises(ValueError):
                Adapter.parse_projects(*pages)

    def test_backfill_update_and_disabled_licences(self):
        adapter = Adapter('sant-vicenc-de-montalt')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[OVERVIEW, DOCUMENTS, NOTICES] * 2):
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 1)
                before = output.read_text()
                self.assertEqual(adapter.update_proyectos(output, Path(directory) / 'state')['rows'], 1)
                self.assertEqual(output.read_text(), before)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
