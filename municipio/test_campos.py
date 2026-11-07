"""Offline parser contracts; live evidence is generated separately with the adapter."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.campos import CamposAyuntamientoAdapter, parse_chronology
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(entries):
    return '<div class="informativePage"><div class="markdown"><p>RELACIÓ D’INSTRUMENTS DE PLANEJAMENT APROVATS</p>' + entries + '</div></div>'


class CamposTests(unittest.TestCase):
    def test_dates_documents_grouping_and_exclusions(self):
        rows = parse_chronology(page('''
        <p>1- NORMES SUBSIDIÀRIES DE PLANEJAMENT APROVADES DEFINITIVAMENT EL 26 DE MARÇ DE 1991. PRESCRIPCIONS COMPLIMENTADES EL 7 DE JUNY DE 1991.</p>
        <p>PUBLICACIÓ: BOCAIB NÚM. 59, DE 14.05.1994</p>
        <p><a href="/original.pdf">Normes</a><a href="/original.pdf">Duplicat</a><a href="/annex.pdf">Annex</a></p>
        <p>2- MODIFICACIÓ PUNTUAL APROVADA EL 20 DE FEBRER DE 1998.</p>
        <p>AQUESTA MODIFICACIÓ VA SER ANUL·LADA PEL TRIBUNAL</p>
        <p>3- MODIFICACIONS PUNTUALS RELATIVES A SAU SON DURÍ</p>
        <p>4- MODIFICACIÓ PUNTUAL APROVADA DEFINITIVAMENT EL 23 D’ABRIL DE 2010 I EL 28 DE MAIG DE 2010</p>
        <p>PUBLICACIÓ: BOIB NÚM. 69, DE 6.05.2010 I NÚM. 91, DE 17.06.2010</p>
        <p>5- CONFORMITAT AMB EL TEXT REFÒS APROVAT PER ACORD DE 31 DE GENER DE 2014</p>
        <p>PUBLICACIÓ: BOIB NÚM. 19, DE 6.02.2014</p>
        <p>6- MODIFICACIÓ PUNTUAL APROVADA DEFINITIVAMENT EL 19 DE DESEMBRE DE 2024</p>
        <p>PUBLICACIÓ: BOIB NÚM. 170, DE 28.12.2024</p>'''))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['fechas_acuerdo'], ['1991-03-26', '1991-06-07'])
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertEqual(rows[0]['fecha_publicacion'], '1994-05-14')
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[1]['fechas_publicacion'], ['2010-05-06', '2010-06-17'])
        self.assertIsNone(rows[1]['fecha_publicacion'])
        self.assertEqual(rows[2]['fecha_acuerdo'], '2014-01-31')
        self.assertIsNone(rows[2]['fecha_aprob'])
        self.assertEqual(rows[3]['fecha_aprob'], '2024-12-19')
        self.assertEqual(rows[3]['fecha_publicacion'], '2024-12-28')
        for row in rows:
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['lon'])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '07013')

    def test_fail_closed(self):
        for html in ['<p>Sol·licitud de llicència</p>', page('<p>1- CONTRACTACIÓ D’OBRES</p>'),
                     page('<p>2- NORMES SUBSIDIÀRIES</p>'),
                     page('<p>1- NORMES SUBSIDIÀRIES</p><p>1- NORMES SUBSIDIÀRIES</p>'),
                     page('<p>1- NORMES SUBSIDIÀRIES</p><a rel="next" href="?page=2">2</a>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_chronology(html)

    def test_ids_do_not_depend_on_position(self):
        text = '<p>1- NORMES SUBSIDIÀRIES APROVADES EL 26 DE MARÇ DE 1991</p>'
        shifted = '<p>1- MODIFICACIÓ PUNTUAL APROVADA EL 19 DE DESEMBRE DE 2024</p>' + text.replace('1-', '2-')
        self.assertEqual(parse_chronology(page(text))[0]['id'], parse_chronology(page(shifted))[1]['id'])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('campos')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, CamposAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Illes Balears')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
