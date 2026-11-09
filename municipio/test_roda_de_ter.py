import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.roda_de_ter import SOURCE, RodaDeTerAyuntamientoAdapter, parse_projects
from municipio.manifest import load_manifest


def table_row(number=1, title=None, filename='plan.pdf'):
    title = title or f'Modificació puntual n. {number} del POUM en un àmbit'
    url = '/media/repository/' + filename
    return f'<tr><td><a href="{url}">{title}</a></td><td>{title}</td><td><a href="{url}">Enllaç</a></td></tr>'


def inventory(rows=None, intro='', extra=''):
    rows = table_row() if rows is None else rows
    return ('<div id="contingut"><section><h1>Modificacions del POUM</h1>'
            f'<article>{intro}</article><table><thead><tr><th>Títol</th><th>Document</th><th>Url</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>{extra}'
            '<div class="info_actualitzacio">25-04-2025 19:39</div></section></div>')


class RodaDeTerTests(unittest.TestCase):
    def test_groups_documents_and_register_reference(self):
        ref = 'https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/283998'
        rows = parse_projects(inventory(table_row() + table_row(filename='annex.pdf'), f'<a href="{ref}">1</a>'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['rpuc_id'], '283998')
        self.assertEqual(rows[0]['id'], 'roda-de-ter-poum-mod-1')
        self.assertTrue(all(d['source_url'] == SOURCE for d in rows[0]['documentos']))

    def test_stage_and_dates_are_not_invented(self):
        rows = parse_projects(inventory(table_row(4, 'Modificació puntual n. 4 del POUM (aprovació inicial)')))
        self.assertEqual(rows[0]['fase'], 'aprobación inicial')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(rows[0][key])
        self.assertIsNone(parse_projects(inventory())[0]['fase'])
        self.assertFalse(rows[0]['publication_ready'])

    def test_rejects_non_instruments_and_empty_inventory(self):
        for rows in ('', table_row(title='Sol·licitud de llicència'), table_row(title='Anunci de licitació'), '<tr><td>broken</td></tr>'):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                parse_projects(inventory(rows))
        with self.assertRaises(ValueError):
            parse_projects('<h1>Login</h1>')

    def test_rejects_pagination(self):
        for extra in ('<a rel="next" href="/next">more</a>', '<a href="?page=2">2</a>',
                      '<a href="/next">Següent</a>', '<div class="pagination">2</div>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_projects(inventory(extra=extra))

    def test_rejects_document_or_schema_drift(self):
        for html in (inventory().replace('/media/repository/', 'https://example.com/'),
                     inventory().replace('<th>Url</th>', '<th>Other</th>'),
                     inventory().replace('plan.pdf', 'form.html')):
            with self.assertRaises(ValueError):
                parse_projects(html)

    def test_rejects_unmatched_and_conflicting_references(self):
        base = 'https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/'
        for intro in (f'<a href="{base}2">2</a>', f'<a href="{base}2">1</a><a href="{base}3">1</a>'):
            with self.assertRaises(ValueError):
                parse_projects(inventory(intro=intro))

    def test_stable_identity_independent_of_row_order_and_document_url(self):
        a = parse_projects(inventory(table_row(2) + table_row(1)))
        b = parse_projects(inventory(table_row(1, filename='new.pdf') + table_row(2)))
        self.assertEqual([r['id'] for r in a], [r['id'] for r in b])
        self.assertEqual(len(a), 2)

    def test_live_interface_and_update_full_snapshot(self):
        class Response:
            url = SOURCE
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size): yield inventory().encode()
        with TemporaryDirectory() as directory, patch('municipio.adapters.roda_de_ter.requests.get', return_value=Response()):
            out = Path(directory) / 'projects.jsonl'
            adapter = RodaDeTerAyuntamientoAdapter('roda-de-ter')
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['rows'], 1)
            original = out.read_bytes()
            adapter.update_proyectos(out, Path(directory) / 'state.json')
            self.assertEqual(out.read_bytes(), original)
            self.assertEqual(json.loads(original)['codigo_ine'], '08183')
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_manifest_contract(self):
        manifest = load_manifest('roda-de-ter')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertEqual(manifest.portal.config['ine_code'], '08183')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
