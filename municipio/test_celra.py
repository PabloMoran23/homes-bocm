"""Offline parser and adapter-contract tests; no live HTTP dependency."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.celra import CelraAyuntamientoAdapter, SOURCE
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def panel(title, docs=None, narrative=''):
    docs = docs if docs is not None else [('Memòria', '/plan.pdf'), ('Plànol', '/map.pdf')]
    links = ''.join(f'<a href="{url}">{name}</a>' for name, url in docs)
    return f'<div class="panel"><div class="panel-heading"><h5>{title}</h5></div><div class="panel-body">{narrative}{links}</div></div>'


def page(body):
    return '<h1>Planejament urbanístic vigent</h1>' + body


class CelraTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        html = page(panel("Revisió del Pla general d'ordenació urbana - data d'aprovació 10/03/1999")
                    + panel('Modificació puntual 24 - data d’aprovació 19/06/2024')
                    + panel("Pla Especial Urbanístic del Sistema d'Equipaments Comunitaris - data d'aprovació 01/10/2025",
                            narrative='<p>Aprovació definitiva per la Comissió Territorial l’1 d’octubre de 2025</p>'))
        rows = CelraAyuntamientoAdapter.parse_projects(html)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['fecha_aprob'], '1999-03-10')
        self.assertEqual(rows[2]['fase'], 'aprobación definitiva')
        self.assertEqual(rows[1]['fase'], 'aprobado (sin precisar fase)')
        for row in rows:
            for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
        changed_date = html.replace('19/06/2024', '20/06/2024')
        self.assertEqual(rows[1]['id'], CelraAyuntamientoAdapter.parse_projects(changed_date)[1]['id'])

    def test_partial_plans_and_invalid_source_date(self):
        html = page('<ul><li><b>Pla Parcial Falgueres Sud-2</b> – data d’aprovació 18/09/20007'
                    '<ol><li><a href="/normativa.pdf">Normativa</a></li>'
                    '<li><a href="/map.pdf">Plànols</a></li></ol></li></ul>')
        rows = CelraAyuntamientoAdapter.parse_projects(html)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertEqual(rows[0]['fecha_aprob_original'], '18/09/20007')
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][0]['url'], 'https://www.celra.cat/normativa.pdf')

    def test_nested_container_does_not_duplicate_instruments(self):
        inner = panel('Modificació puntual 1 - data d’aprovació 20/12/2000')
        html = page('<div class="panel"><div class="panel-heading"><h5>Modificacions</h5></div>' + inner + '</div>')
        self.assertEqual(len(CelraAyuntamientoAdapter.parse_projects(html)), 1)

    def test_rejects_empty_forms_missing_documents_and_changed_markup(self):
        invalid = [page('<a href="/licencia.pdf">Sol·licitud de llicència</a>'),
                   '<h1>Login</h1>',
                   page(panel('Modificació puntual 1 - data d’aprovació 20/12/2000', docs=[])),
                   page(panel('Modificació puntual 1'))]
        for html in invalid:
            with self.subTest(html=html), self.assertRaises(ValueError):
                CelraAyuntamientoAdapter.parse_projects(html)

    def test_no_silent_pagination_or_duplicate(self):
        item = panel('Modificació puntual 1 - data d’aprovació 20/12/2000')
        for extra in ('<a href="/page/2" rel="next">2</a>',
                      '<a href="/page/2">Següent</a>', item):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                CelraAyuntamientoAdapter.parse_projects(page(item + extra))

    def test_manifest_and_snapshot_contract(self):
        manifest = load_manifest('celra')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('17049', 'Celrà', 'Girona'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CelraAyuntamientoAdapter)
        html = page(panel('Modificació puntual 1 - data d’aprovació 20/12/2000'))
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass
            def iter_content(self, size): yield html.encode()
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.celra.requests.get', return_value=Response()) as get:
            out = Path(tmp) / 'proyectos.jsonl'
            adapter = CelraAyuntamientoAdapter('celra')
            result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '17049')
            self.assertEqual(get.call_args.args[0], SOURCE)
            out.write_text('previous snapshot')
            with patch.object(adapter, 'parse_projects', side_effect=ValueError('changed source')):
                with self.assertRaises(ValueError): adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
