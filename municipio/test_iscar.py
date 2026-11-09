import copy
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.iscar import (
    INVENTORY_URL, IscarAyuntamientoAdapter, canonical_url,
    group_instruments, parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


TITLE = 'MODIFICACIÓN 1-2025 DE LAS NUM, REFERIDO A VARIAS MODIFICACIONES.'


def inventory(title=TITLE, identity='47075', publication='13/03/2026', agreement='25/02/2026'):
    return f'''<p>ÍSCAR Código INE: {identity}</p><table class="cuadroAplicacion">
    <tr><th>Libro</th></tr><tr><td>PU</td><td>NUM</td><td>{publication}</td>
    <td>{agreement}</td><td>{title}</td><td><a href="/PlanPublica/ldoc_files.do;jsessionid=TEMP?cDocId=301421">Ficheros</a></td></tr></table>'''


def documents(file_id='168176', title='DOC. TECNICO APROBADO DEF_stamped.pdf'):
    return f'''<p>Íscar (Valladolid )</p><table><tr><td>{title}</td><td>
    <a href="/PlanPublica/openFichero.do;jsessionid=TEMP?cFicheroId={file_id}">PDF</a>
    </td></tr></table>'''


class IscarParserTests(unittest.TestCase):
    def test_real_structure_and_date_semantics(self):
        row, = parse_inventory(inventory())
        self.assertEqual(row['titulo'], TITLE)
        self.assertEqual(row['fecha_publicacion'], '2026-03-13')
        self.assertEqual(row['fecha_acuerdo'], '2026-02-25')
        self.assertEqual(row['source_id'], '301421')
        self.assertNotIn('jsessionid', row['url'])
        self.assertNotIn('fecha_aprob', row)

    def test_reject_wrong_municipality_empty_and_invalid_dates(self):
        for html in [inventory(identity='47076'), '<html>Service unavailable</html>',
                     inventory(publication='31/02/2026'), '<p>Código INE: 47075</p>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_never_silently_truncated(self):
        for control in ['<a rel="next" href="?page=2">Next</a>',
                        '''<a href="javascript:" onclick="doResults('results','?pager.offset=15')">2</a>''']:
            with self.assertRaises(ValueError):
                parse_inventory(inventory() + control)
        row = inventory().split('<tr><th>Libro</th></tr>')[1].split('</table>')[0]
        with self.assertRaises(ValueError):
            parse_inventory('<p>Código INE: 47075</p><table class="cuadroAplicacion">' + row * 15 + '</table>')

    def test_document_links_titles_and_origin(self):
        doc, = parse_documents(documents())
        self.assertEqual(doc['titulo'], 'DOC. TECNICO APROBADO DEF_stamped.pdf')
        self.assertTrue(doc['url'].endswith('?cFicheroId=168176'))
        for html in ['<p>Íscar (Valladolid )</p>', documents().replace('Íscar', 'Otro')]:
            with self.assertRaises(ValueError):
                parse_documents(html)
        with self.assertRaises(ValueError):
            canonical_url('https://example.org/PlanPublica/openFichero.do?cFicheroId=1')

    def test_group_archival_duplicates_and_keep_documents_isolated(self):
        one, = parse_inventory(inventory())
        one.update(boletin_url='https://bocyl.jcyl.es/one.pdf', documentos=parse_documents(documents()))
        duplicate = copy.deepcopy(one)
        duplicate.update(source_id='301422', titulo='Otro título del mismo instrumento',
                         documentos=parse_documents(documents('168175', 'DOC. AMBIENTAL.pdf')))
        other = copy.deepcopy(one)
        other.update(source_id='282916', boletin_url='https://bocyl.jcyl.es/two.pdf',
                     documentos=parse_documents(documents('222', 'PLANO.pdf')))
        rows = group_instruments([one, duplicate, other])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['entradas_fuente']), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertNotIn('222', str(rows[0]['documentos']))
        self.assertEqual(group_instruments([duplicate, one])[0]['id'], rows[0]['id'])
        self.assertFalse(rows[0]['publication_ready'])
        for field in ['lat', 'lon', 'geometry', 'fecha_aprob', 'fase']:
            self.assertNotIn(field, rows[0])

    def test_daily_bulletin_index_is_not_an_instrument_identity(self):
        one, = parse_inventory(inventory())
        one.update(boletin_url='https://bocyl.jcyl.es/boletin.do?fechaBoletin=24/10/2008',
                   documentos=parse_documents(documents()))
        other = copy.deepcopy(one)
        other['source_id'] = '284372'
        self.assertEqual(len(group_instruments([one, other])), 2)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('iscar')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('47075', 'Íscar', 'Valladolid'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = IscarAyuntamientoAdapter('iscar').backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
