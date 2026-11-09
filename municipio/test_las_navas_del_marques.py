"""Parser and complete-snapshot checks without network dependencies."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.las_navas_del_marques import (
    ROOT, SOURCE, LasNavasDelMarquesAyuntamientoAdapter, clean_url,
    parse_files, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def row(doc_id='10', title='NORMAS URBANÍSTICAS MUNICIPALES', publication='07/07/2003',
        agreement='30/04/2003', book='PU', files=True):
    link = f'<a href="ldoc_files.do;jsessionid=temporary?cDocId={doc_id}">Files</a>' if files else ''
    return (f'<tr><td>{book}</td><td>NUM</td><td><a onclick="doGoBoletin(\'{doc_id}\', \'ref\')">'
            f'{publication}</a></td><td>{agreement}</td><td>{title}</td><td>{link}</td></tr>')


def page(rows, start=1, end=1, total=1, next_offset=None):
    pager = '' if next_offset is None else (
        '<a onclick="doResults(\'results\',unescape(\'searchVPubDocMuniPlau.do?'
        f'pager.offset={next_offset}%26municipio=168%26provincia=05%26bInfoPublica=N\'))">Next</a>')
    return ('Código INE: 05168 NAVAS DEL MARQUÉS (LAS)<table><tr>'
            '<th>Libro</th><th>Instrumento</th><th>Fecha de publicación</th>'
            '<th>Fecha de acuerdo</th><th>Título</th><th></th></tr>' + ''.join(rows) + '</table>'
            f'Mostrando resultados {start}-{end} de {total}' + pager)


FILES = '''Listado de ficheros<table>
<tr><td>memoria.pdf</td><td><a href="openFichero.do?cFicheroId=1">PDF</a></td></tr>
<tr><td>planos.pdf</td><td><a href="openFichero.do?cFicheroId=2">PDF</a></td></tr></table>'''
NEXT = ROOT + 'searchVPubDocMuniPlau.do?pager.offset=1&municipio=168&provincia=05&bInfoPublica=N'


class PlanningTests(unittest.TestCase):
    def test_dates_and_missing_date(self):
        rows, summary, links = parse_inventory(page([row(publication='')]))
        self.assertEqual(summary, (1, 1, 1))
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertEqual(rows[0]['fecha_acuerdo'], '2003-04-30')
        self.assertEqual(links, [])
        rows, _, _ = parse_inventory(page([row()]))
        self.assertEqual(rows[0]['fecha_publicacion'], '2003-07-07')
        self.assertNotIn('fecha_aprob', rows[0])

    def test_pagination_and_incomplete_page(self):
        _, _, links = parse_inventory(page([row()], total=2, next_offset=1))
        self.assertEqual(links, [NEXT])
        sorted_page = page([row()], total=2, next_offset=1).replace('<th>Libro</th>',
            '<th><a onclick="doResults(\'results\',unescape(\'searchVPubDocMuniPlau.do?pager.offset=0&pager.sortindex=1\'))">Libro</a></th>')
        self.assertEqual(parse_inventory(sorted_page)[2], [NEXT])
        with self.assertRaises(ValueError):
            parse_inventory(page([row()], end=2, total=2))
        with self.assertRaises(ValueError):
            parse_inventory('<h1>Licencia de Obra Mayor</h1>Formulario de solicitud')
        with self.assertRaises(ValueError):
            parse_inventory(page([row(publication='31/02/2026')]))

    def test_file_group_and_url_validation(self):
        files = parse_files(FILES)
        self.assertEqual([f['nombre'] for f in files], ['memoria.pdf', 'planos.pdf'])
        self.assertEqual(clean_url('ldoc_files.do;jsessionid=abc?cDocId=10'), ROOT + 'ldoc_files.do?cDocId=10')
        with self.assertRaises(ValueError):
            clean_url('https://example.org/PlanPublica/ldoc_files.do')
        with self.assertRaises(ValueError):
            parse_files(FILES + 'Mostrando resultados 1-2 de 5')

    def run_snapshot(self, responses):
        adapter = LasNavasDelMarquesAyuntamientoAdapter('las-navas-del-marques')
        def fetch(_session, url):
            return responses[url]
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=fetch):
            out = Path(tmp) / 'records.jsonl'
            result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            records = [json.loads(line) for line in out.read_text().splitlines()]
        return result, records

    def test_complete_snapshot_groups_and_excludes_non_projects(self):
        responses = {
            SOURCE: page([row()], total=3, next_offset=1),
            NEXT: page([row('11', 'CONVENIO URBANÍSTICO', book='CU', files=False),
                        row('12', 'SENTENCIA DEL RECURSO', files=False)], 2, 3, 3),
            ROOT + 'ldoc_files.do?cDocId=10': FILES,
        }
        result, records = self.run_snapshot(responses)
        self.assertEqual(result['inventory_rows'], 3)
        self.assertEqual(result['excluded_rows'], 2)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]['documentos']), 2)
        self.assertEqual(records[0]['codigo_ine'], '05168')
        self.assertIsNone(records[0]['lat'])
        self.assertFalse(records[0]['publication_ready'])
        self.assertNotIn('fase', records[0])

    def test_missing_pagination_and_duplicate_ids_fail(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete archive inventory'):
            self.run_snapshot({SOURCE: page([row()], total=2)})
        with self.assertRaisesRegex(ValueError, 'Incomplete archive inventory'):
            self.run_snapshot({SOURCE: page([row(), row()], 1, 2, 2)})
        with self.assertRaisesRegex(ValueError, 'Wrong archive municipality'):
            self.run_snapshot({SOURCE: page([row()]).replace('05168', '05169')})

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('las-navas-del-marques')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '05168')
        self.assertEqual(manifest.provincia, 'Ávila')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = LasNavasDelMarquesAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
