from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.quart import SOURCE, HEADERS, QuartAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def row(title="PLA D'ORDENACIÓ URBANISTICA MUNICIPAL (POUM)", doc='plan', date='25-11-2022', info=''):
    return (f'<tr><td>{title}</td><td>{date}</td>'
            '<td><a href="https://dogc.gencat.cat/ca/document-del-dogc/?documentId=943323">DOGC</a></td>'
            f'<td><a href="/documents/{doc}">Memòria</a><a href="/documents/{doc}-annex">Annex</a></td>'
            f'<td>{info}</td>')  # intentionally unclosed, like the live inventory


def page(rows):
    return ('<table id="inventory"><thead><tr>' + ''.join(f'<th>{h}</th>' for h in HEADERS)
            + '</tr></thead><tbody>' + rows + '</tbody></table>')


class QuartTests(unittest.TestCase):
    def test_grouping_dates_and_exclusions(self):
        records = parse_inventory(page(row() + row("Estudi d'ordenació de la mobilitat al municipi de Quart 2022",
            'mobility', '14-11-2022', 'Aprovació definitiva en novembre de 2022.')
            + row('Sol·licitud de llicència') + row('INVENTARI CAMINS PUBLICS')
            + row("Catàleg d'arbres d'interès local") + row('Anunci de licitació')))
        self.assertEqual(len(records), 2)
        self.assertEqual(len(records[0]['documentos']), 3)
        self.assertEqual(records[0]['fecha_publicacion'], '2022-11-25')
        self.assertIsNone(records[0]['fase'])
        self.assertEqual(records[1]['fase'], 'aprobación definitiva')
        for record in records:
            for field in ('fecha_aprob', 'fecha_acuerdo', 'fecha', 'lat', 'lon', 'geometry'):
                self.assertIsNone(record[field])

    def test_missing_dates_and_stable_identity(self):
        first = parse_inventory(page(row(date='')))[0]
        second = parse_inventory(page(row(date='01-01-2024')))[0]
        self.assertIsNone(first['fecha_publicacion'])
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(len(parse_inventory(page(row() + row()))), 1)

    def test_all_embedded_rows(self):
        self.assertEqual(len(parse_inventory(page(''.join(row(doc=str(i)) for i in range(25))))), 25)

    def test_fail_closed(self):
        for html in ('<form>Login</form>', page(row('Sol·licitud de llicència')),
                     page(row()).replace('25-11-2022', '31-02-2022'),
                     page(row()).replace('/documents/plan', 'https://untrusted.example/plan'),
                     page(row()) + '<a rel="next" href="?page=2">Next</a>',
                     page(row()) + '<script>$("#inventory").DataTable({serverSide:true});</script>',
                     page(row()) + '<script>$("#inventory").DataTable({ajax:"/rows"});</script>',
                     page(row()).replace('<a href="/documents/', '<span data-url="/documents/')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_snapshot_update(self):
        manifest = load_manifest('quart')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, QuartAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        response = Mock(url=SOURCE, text=page(row()))
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.quart.requests.get', return_value=response):
            output = Path(tmp) / 'projects.jsonl'
            state = Path(tmp) / 'state.json'
            result = adapter.update_proyectos(output, state)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(output.read_text().splitlines()), 1)
            self.assertFalse(state.exists())
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['rows'], 0)


if __name__ == '__main__':
    unittest.main()
