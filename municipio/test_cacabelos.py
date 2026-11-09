"""Offline parser and snapshot safety tests; fixtures mirror reviewed PLAU HTML."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cacabelos import (
    ARCHIVE, MUNICIPAL_SOURCE, SOURCE, CacabelosAyuntamientoAdapter as Adapter,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def inventory_row(doc_id, title, publication='17/05/2001', agreement='29/09/2000', book='PU'):
    return f'''<tr><td>{book}</td><td>NS</td><td>{publication}</td><td>{agreement}</td>
    <td>{title}</td><td><a href="/PlanPublica/ldoc_files.do;jsessionid=temporary?cDocId={doc_id}">files</a></td></tr>'''


def inventory(rows=None):
    if rows is None:
        rows = (inventory_row('280775', 'NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL') +
                inventory_row('283374', 'MODIFICACIÓN DE NN.SS. ANTIGUA BODEGA CARPAL', '31/07/2006', '30/06/2006'))
    return f'''<h1>CACABELOS</h1><h2>Código INE: <span>24030</span> (0019.7 km2)</h2>
    <table class="cuadroAplicacion"><tr><th>Libro</th><th>Instrumento</th>
    <th>Fecha de publicación</th><th>Fecha de acuerdo</th><th>Título</th><th></th></tr>{rows}</table>'''


def documents(title, ids=('83320', '83321')):
    rows = ''.join(f'''<tr><td>documento-{i}.pdf</td><td><a
    href="/PlanPublica/openFichero.do;jsessionid=temporary?cFicheroId={i}"><img alt="Ver documento"></a></td></tr>''' for i in ids)
    return f'''<div>Cacabelos (León )</div><h1>{title}</h1>
    <table class="cuadroAplicacion"><tr><th>Nombre del Fichero</th><th>Fichero</th></tr>{rows}</table>'''


class CacabelosTests(unittest.TestCase):
    def test_manifest_and_dynamic_loader(self):
        manifest = load_manifest('cacabelos')
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('24030', 'León'))
        for section, key in [('licencias', 'enabled'), ('schedule', 'enabled'), ('geocode', 'jitter_missing')]:
            self.assertIs(raw[section][key], False)

    def test_real_instruments_dates_identity_and_no_inferred_metadata(self):
        rows = Adapter.parse_inventory(inventory())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['id'], 'cacabelos-plau-280775')
        self.assertEqual(rows[0]['fecha_publicacion'], '2001-05-17')
        self.assertEqual(rows[0]['fecha_acuerdo'], '2000-09-29')
        self.assertEqual(rows[1]['fecha_acuerdo'], '2006-06-30')
        for row in rows:
            self.assertNotIn(';jsessionid', row['url'])
            for field in ['fecha', 'fecha_aprob', 'geometry', 'lat', 'lon']:
                self.assertIsNone(row[field])
            self.assertNotIn('fase', row)
            self.assertFalse(row['publication_ready'])

    def test_group_documents_without_cross_instrument_leakage(self):
        a, b = Adapter.parse_inventory(inventory())
        adocs = Adapter.parse_documents(documents(a['titulo']), a)
        bdocs = Adapter.parse_documents(documents(b['titulo'], ('99000',)), b)
        self.assertEqual(len(adocs), 2)
        self.assertEqual(len(bdocs), 1)
        self.assertTrue(all(d['url_procedencia'] == a['url'] for d in adocs))
        self.assertTrue(all(';jsessionid' not in d['url'] for d in adocs + bdocs))
        with self.assertRaises(ValueError):
            Adapter.parse_documents(documents(a['titulo']), b)

    def test_reject_wrong_municipality_empty_and_schema_changes(self):
        for html in [inventory().replace('24030', '24031'), inventory().replace('CACABELOS', 'OTRO'),
                     inventory(''), inventory().replace('Fecha de acuerdo', 'Fecha')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_exclude_other_books_and_reject_unreviewed_titles(self):
        row = inventory_row('1', 'Solicitud de licencia', book='UE')
        self.assertEqual(len(Adapter.parse_inventory(inventory(row + inventory_row('2', 'PLAN PARCIAL INDUSTRIAL')))), 1)
        for title in ['Solicitud de licencia', 'Anuncio de licitación', 'Fiestas locales']:
            with self.subTest(title=title), self.assertRaises(ValueError):
                Adapter.parse_inventory(inventory(inventory_row('1', title)))

    def test_pagination_never_silently_truncated(self):
        variants = [inventory() + '<a onclick="go(\'pager.offset=15\')">2</a>',
                    inventory() + '<a href="?page=2" rel="next">→</a>',
                    inventory() + '<a href="?page=2">Siguiente</a>',
                    inventory(''.join(inventory_row(str(i), 'PLAN PARCIAL INDUSTRIAL') for i in range(15)))]
        for html in variants:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_missing_dates_are_null_invalid_dates_fail(self):
        row = Adapter.parse_inventory(inventory(inventory_row('1', 'PLAN PARCIAL INDUSTRIAL', '', '')))[0]
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_publicacion'])
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(inventory(inventory_row('1', 'PLAN PARCIAL INDUSTRIAL', '31/02/2001')))

    def test_documents_fail_on_empty_wrong_municipality_pagination_or_foreign_url(self):
        row = Adapter.parse_inventory(inventory())[0]
        good = documents(row['titulo'])
        for html in [documents(row['titulo'], ()), good.replace('Cacabelos', 'Otra villa'),
                     good + '<a href="?pager.offset=15">2</a>',
                     good.replace('/PlanPublica/openFichero.do', 'https://example.com/openFichero.do')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_documents(html, row)

    def test_failed_fetch_preserves_snapshot(self):
        municipal = f'<main><a href="{SOURCE}">Normas urbanísticas</a></main>'
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            adapter = Adapter('cacabelos')
            with patch.object(adapter, '_fetch', side_effect=[municipal, inventory(), RuntimeError('network failure')]):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')

    def test_live_path_writes_grouped_snapshot_and_disabled_licences(self):
        municipal = f'<main><a href="{SOURCE}">Normas urbanísticas</a></main>'
        rows = Adapter.parse_inventory(inventory())
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            adapter = Adapter('cacabelos')
            with patch.object(adapter, '_fetch', side_effect=[municipal, inventory()] + [documents(r['titulo']) for r in rows]):
                result = adapter.update_proyectos(out, Path(directory) / 'state.json')
            written = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual([len(r['documentos']) for r in written], [2, 2])
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
