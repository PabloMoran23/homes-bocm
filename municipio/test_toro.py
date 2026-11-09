"""Self-contained parser/crawler tests; live evidence is deliberately not a fixture."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.toro import (
    BASE, SOURCE, MUNICIPAL_SOURCE, ToroAyuntamientoAdapter,
    group_instruments, parse_files, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(rows, start=1, total=None):
    body = ''
    for ident, title, kind, book in rows:
        body += f'''<tr><td>{book}</td><td>{kind}</td>
        <td><a onclick="doGoBoletin('{ident}', '49219-{book}-20230515-{ident}')">15/05/2023</a></td>
        <td>31/03/2023</td><td>{title}</td><td></td></tr>'''
    end = start + len(rows) - 1
    return f'''Código INE: 49219<table class="cuadroAplicacion">{body}</table>
    Mostrando resultados {start}-{end} de {total or end}'''


class ToroTests(unittest.TestCase):
    def test_dates_and_real_instrument_not_licence(self):
        rows, bounds = parse_inventory(inventory([('299041', 'MODIFICACIÓN DEL PGOU EN LA CALLE REJADORADA N.º 30', 'PGOU', 'PU')]))
        self.assertEqual(bounds, (1, 1, 1))
        row = group_instruments(rows)[0]
        self.assertEqual(row['fecha_publicacion'], '2023-05-15')
        self.assertEqual(row['fecha_acuerdo'], '2023-03-31')
        self.assertNotIn('fecha_aprob', row)
        self.assertNotIn('lat', row)
        self.assertFalse(row['publication_ready'])

    def test_group_correction_and_retain_all_provenance(self):
        rows, _ = parse_inventory(inventory([
            ('299041', 'MODIFICACIÓN DEL PGOU EN LA CALLE REJADORADA N.º 30', 'PGOU', 'PU'),
            ('299383', 'CORRECCIÓN DE ERRORES DE LA MODIFICACIÓN DEL PGOU, EN LA CALLE REJADORADA Nº 30', 'PGOU', 'PU'),
            ('999', 'MODIFICACIÓN DEL PGOU EN CALLE DIFERENTE', 'PGOU', 'PU')]))
        for row in rows:
            row['documentos'] = [{'titulo': row['plau_id'], 'url': BASE + row['plau_id']}]
        groups = group_instruments(rows)
        self.assertEqual(len(groups), 2)
        merged = next(g for g in groups if len(g['publicaciones']) == 2)
        self.assertEqual({d['titulo'] for d in merged['documentos']}, {'299041', '299383'})
        self.assertNotIn('999', {d['titulo'] for d in merged['documentos']})
        changed = copy.deepcopy(rows[0]); changed['fecha_acuerdo'] = '2022-01-01'
        self.assertEqual(len(group_instruments([rows[0], changed])), 2)

    def test_sentences_and_agreements_excluded(self):
        rows, _ = parse_inventory(inventory([
            ('1', 'SENTENCIA DEL RECURSO REFERIDO AL PGOU', 'PGOU', 'PU'),
            ('2', 'CONVENIO URBANÍSTICO', 'CN_UR', 'CU'),
            ('3', 'PROYECTO DE URBANIZACIÓN EL PALO', 'PAU', 'GU')]))
        self.assertEqual([r['titulo'] for r in group_instruments(rows)], ['PROYECTO DE URBANIZACIÓN EL PALO'])

    def test_fail_closed_on_count_identity_or_schema(self):
        html = inventory([('1', 'PLAN PARCIAL EL PALO', 'PP', 'PU')])
        for broken in ['', html.replace('1-1', '1-2'), html.replace('49219-PU', '49001-PU'), html.replace('<td>PU</td>', '')]:
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                parse_inventory(broken)

    def test_files_grouped_not_one_project_per_pdf(self):
        html = '''Toro (Zamora )<table><tr><td>Memoria.pdf</td><td>
        <a href="openFichero.do;jsessionid=temporary?cFicheroId=42">PDF</a></td></tr>
        <tr><td>Plano.pdf</td><td><a href="openFichero.do?cFicheroId=43">PDF</a></td></tr></table>'''
        docs = parse_files(html, BASE + 'ldoc_files.do?cDocId=1')
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]['url'], BASE + 'openFichero.do?cFicheroId=42')
        for broken in [html.replace('Toro', 'Otro'), html + '<a href="?pager.offset=15">Siguiente</a>', 'Toro (Zamora)']:
            with self.assertRaises(ValueError):
                parse_files(broken, BASE)

    def test_crawl_all_pages_and_reject_repeat_without_overwriting(self):
        municipal = f'<a href="{SOURCE}">Archivo de planeamiento</a>'
        first = inventory([('1', 'PLAN PARCIAL UNO', 'PP', 'PU')], total=2)
        second = inventory([('2', 'PLAN PARCIAL DOS', 'PP', 'PU')], start=2, total=2)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            adapter = ToroAyuntamientoAdapter('toro')
            with patch.object(adapter, '_fetch', side_effect=[municipal, first, second]) as fetch:
                report = adapter.backfill_proyectos(output)
                self.assertEqual(report['count'], 2)
                self.assertIn('pager.offset=1', fetch.call_args_list[-1].args[1])
            previous = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[municipal, first, first]):
                with self.assertRaisesRegex(ValueError, 'Pagination'):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)

    def test_manifest_and_licences_disabled(self):
        manifest = load_manifest('toro')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Toro', 'Zamora', '49219'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            report = ToroAyuntamientoAdapter('toro').backfill_licencias(path)
            self.assertTrue(report['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
