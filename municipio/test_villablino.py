"""Offline parser and adapter-contract tests; no network/credentials required."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.villablino import VillablinoAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def entry(title='PLAN GENERAL DE ORDENACIÓN URBANA (REVISIÓN)', kind='PGOU', doc='288804',
          publication='02/11/2012', agreement='10/10/2012'):
    link = (f'<a href="/PlanPublica/ldoc_files.do;jsessionid=ephemeral?cDocId={doc}">Files</a>'
            if doc else '<img alt="No hay documentos">')
    return (f'<tr><td>PU</td><td>{kind}</td><td>{publication}</td><td>{agreement}</td>'
            f'<td>{title}</td><td>{link}</td></tr>')


def inventory(*rows):
    return ('<h1>VILLABLINO Código INE: 24202</h1><table class="cuadroAplicacion"><tr>'
            '<th>Libro</th><th>Instrumento</th><th>Fecha de publicación</th>'
            '<th>Fecha de acuerdo</th><th>Título</th><th></th></tr>' + ''.join(rows) + '</table>')


def files(title, count=2):
    return ('<h1>Villablino (León)</h1><p>' + title + '</p><table class="cuadroAplicacion">'
            '<tr><th>Nombre del Fichero</th><th>Fichero</th></tr>' + ''.join(
                f'<tr><td>Plano {i}.pdf</td><td><a href="/PlanPublica/openFichero.do;jsessionid=x?cFicheroId={i}">PDF</a></td></tr>'
                for i in range(count)) + '</table>')


class VillablinoTests(unittest.TestCase):
    def test_dates_and_missing_values(self):
        rows = Adapter.parse_inventory(inventory(entry(), entry('PP SECTOR UPSR-4', 'PP', None, '', '10/12/1989')))
        self.assertEqual(rows[0]['fecha_publicacion'], '2012-11-02')
        self.assertEqual(rows[0]['fecha_acuerdo'], '2012-10-10')
        self.assertNotIn('jsessionid', rows[0]['url'])
        out = Adapter.group_projects(rows)
        self.assertIsNone(out[0]['fecha_aprob'])
        self.assertIsNone(out[0]['fase'])
        self.assertIsNone(out[1]['fecha_publicacion'])
        self.assertIsNone(out[1]['archivo_id'])
        self.assertIsNone(out[1]['geometry'])
        self.assertEqual(out[1]['documentos'], [])
        self.assertEqual(out[1]['id'], Adapter.group_projects(list(reversed(rows)))[0]['id'])

    def test_group_court_document_with_plan_and_keep_dates(self):
        rows = Adapter.parse_inventory(inventory(entry(), entry(
            'SENTENCIA DEL RECURSO Nº 2/2013 REFERIDO A LA ANULACIÓN PARCIAL DEL PGOU. ENTRE LAS CALLES VIDALGUERA Y PERUCHAL',
            doc='292985', publication='27/05/2016', agreement='16/05/2016')))
        for row in rows:
            row['documentos'] = Adapter.parse_files(files(row['titulo']), row['titulo'])
        result = Adapter.group_projects(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['documentos']), 4)
        self.assertEqual(result[0]['fecha_acuerdo'], '2012-10-10')
        self.assertEqual(result[0]['entradas_archivo'][1]['fecha_acuerdo'], '2016-05-16')
        self.assertEqual(result[0]['documentos'][-1]['archivo_id'], '292985')
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            Adapter.group_projects([rows[1]])

    def test_reject_navigation_forms_wrong_municipality_and_changed_schema(self):
        good = inventory(entry())
        for html in ['<a>Licencia de obras</a>', good.replace('24202', '24203'),
                     good.replace('Fecha de acuerdo', 'Fecha de aprobación'),
                     inventory(entry('FORMULARIO LICENCIA', 'LIC')),
                     inventory(entry().replace('02/11/2012', '31/02/2012')),
                     inventory(entry().replace('cDocId=288804', 'cDocId=no'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_reject_pagination_full_page_and_duplicates(self):
        with self.assertRaisesRegex(ValueError, 'pagination'):
            Adapter.parse_inventory(inventory(entry()) + '<a onclick="go(\'pager.offset=15\')">2</a>')
        with self.assertRaisesRegex(ValueError, 'Full archive page'):
            Adapter.parse_inventory(inventory(*(entry(doc=str(i)) for i in range(15))))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            Adapter.parse_inventory(inventory(entry(), entry()))

    def test_files_all_retained_sessionless_and_validated(self):
        docs = Adapter.parse_files(files('PLAN', count=77), 'PLAN')
        self.assertEqual(len(docs), 77)
        self.assertTrue(all('jsessionid' not in d['url'] for d in docs))
        for html in [files('OTHER'), files('PLAN').replace('Villablino', 'Otro'),
                     files('PLAN', count=0), files('PLAN').replace('openFichero', 'unrelated'),
                     files('PLAN') + '<a href="?pager.offset=20">2</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_files(html, 'PLAN')

    def test_manifest_loader_snapshot_update_and_failure_preserves_output(self):
        manifest = load_manifest('villablino')
        self.assertEqual((manifest.nombre, manifest.provincia), ('Villablino', 'León'))
        adapter = load_portal_adapter(manifest)
        html = inventory(entry())
        title = Adapter.parse_inventory(html)[0]['titulo']
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[html, files(title)]):
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            before = output.read_text()
            self.assertEqual(json.loads(before)['codigo_ine'], '24202')
            with patch.object(adapter, '_fetch', return_value='<h1>Login</h1>'), self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(before, output.read_text())
            licences = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(licences)['status'], 'disabled')
            self.assertEqual(licences.read_text(), '')


if __name__ == '__main__':
    unittest.main()
