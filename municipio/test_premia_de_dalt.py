import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.premia_de_dalt import PremiaDeDaltAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest


def doc(name='memoria.pdf', label='Memòria'):
    return f'<li><p><a href="{SOURCE}/pla-test/{name}">{label}</a></p></li>'


def panel(key='pla-test', title='Pla especial (29/08/2007)', content=None):
    return (f'<li><div class="panel-heading"><p><a href="#{key}">{title}'
            '<span>(2)</span><i></i></a></p></div>'
            f'<ul id="{key}">{content if content is not None else doc() + doc("planols.pdf", "Plànols")}</ul></li>')


def page(content):
    return f'<section id="content-core"><ul id="accordionFolderList">{content}</ul></section>'


class PremiaDeDaltTests(unittest.TestCase):
    def test_groups_documents_and_preserves_untyped_dates(self):
        rows, excluded = Adapter.parse_inventory(page(panel(content=doc(label='Acord CTUB 15.03.2018') + doc('planols.pdf'))))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['titulo'], 'Pla especial (29/08/2007)')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '08230')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[field])
        self.assertIn('15.03.2018', row['documentos'][0]['titulo'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(excluded, [])

    def test_nested_approval_documents_stay_one_instrument(self):
        nested = '<li><p><a href="#approval">Aprovació definitiva</a></p><ul id="approval">' + doc('normes.pdf') + '</ul></li>'
        rows, _ = Adapter.parse_inventory(page(panel(content=doc() + nested)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        # Identity does not depend on the document order.
        reordered, _ = Adapter.parse_inventory(page(panel(content=nested + doc())))
        self.assertEqual(rows[0]['id'], reordered[0]['id'])

    def test_container_splits_instruments_and_deduplicates_aliases(self):
        key = 'modificacions-puntuals-del-poum-de-premia-de-dalt'
        children = ''.join(f'<li><p><a href="#{x}">Modificació puntual {x}</a></p><ul id="{x}">{doc(x+".pdf")}</ul></li>' for x in ('a', 'b'))
        rows, _ = Adapter.parse_inventory(page(panel(key, 'Modificacions puntuals', children) + panel('alias', content=doc('a.pdf'))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['referencias_inventario']), 2)

    def test_same_instrument_with_relocated_documents_is_merged(self):
        rows, _ = Adapter.parse_inventory(page(panel('original', content=doc('old.pdf')) + panel('relocated', content=doc('new.pdf'))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[0]['referencias_inventario']), 2)

    def test_explicit_partial_coverage(self):
        rows, excluded = Adapter.parse_inventory(page(panel() + panel('can-nolla', 'Can Nolla')))
        self.assertEqual(len(rows), 1)
        self.assertEqual(excluded[0]['url'], SOURCE + '#can-nolla')

    def test_navigation_or_forms_cannot_be_records(self):
        for html in ('<html>Login</html>', page(''), page(panel(title='Llicència urbanística d’obres majors')),
                     page(panel(content='')), page(panel(content='<li><p><a href="https://example.org/a.pdf">PDF</a></p></li>'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_pagination_rejected(self):
        for marker in ('<a rel="next" href="?page=2">Next</a>', '<div class="listingBar">2</div>',
                       '<a href="?b_start=20">Següent</a>'):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                Adapter.parse_inventory(page(panel() + marker))

    def test_manifest_and_disabled_licences(self):
        m = load_manifest('premia-de-dalt')
        self.assertEqual(m.provincia, 'Barcelona')
        self.assertFalse(m.licencias.enabled)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'licencias.jsonl'
            self.assertEqual(Adapter(m.slug).backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_live_method_fetches_and_writes_snapshot_atomically(self):
        class Response:
            url = SOURCE
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size): yield page(panel()).encode()
        with tempfile.TemporaryDirectory() as d, patch('municipio.adapters.premia_de_dalt.requests.get', return_value=Response()) as get:
            path = Path(d) / 'proyectos.jsonl'
            a = Adapter('premia-de-dalt')
            self.assertEqual(a.update_proyectos(path, Path(d) / 'state.json')['rows'], 1)
            self.assertEqual(json.loads(path.read_text())['municipio'], 'Premià de Dalt')
            self.assertEqual(get.call_args.args[0], SOURCE)
            with patch.object(a, 'parse_inventory', side_effect=ValueError('changed source')):
                before = path.read_bytes()
                with self.assertRaises(ValueError): a.backfill_proyectos(path)
                self.assertEqual(before, path.read_bytes())


if __name__ == '__main__':
    unittest.main()
