"""Offline parser and traversal contract tests; no external network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.pasaia import (
    BASE, SOURCE, PasaiaAyuntamientoAdapter, parse_inventory, parse_page,
)
from municipio.manifest import load_manifest


def page(body):
    return '<main id="main-content">' + body + '</main>'


def catalogue(links):
    return page('<div class="journal-content-article"><h2>PLANEAMIENTO</h2>' + links + '</div>')


class PasaiaTests(unittest.TestCase):
    def test_inventory_scoped_and_deduplicated(self):
        html = catalogue('<a href="/nnss">Normas subsidiarias</a><a href="/nnss"><img></a>')
        html += '<a href="?news_cur=2">Siguiente</a>'
        self.assertEqual(parse_inventory(html), {BASE + '/es/nnss': 'Normas subsidiarias'})
        with self.assertRaises(ValueError):
            parse_inventory(catalogue('<a href="/form">Solicitud licencia</a>'))
        with self.assertRaises(ValueError):
            parse_inventory(catalogue('<a href="?x_cur=2">Siguiente</a>'))

    def test_document_titles_provenance_and_folder_discovery(self):
        root = BASE + '/es/plan-especial-portuario'
        docs, children, _ = parse_page(page('''
            <div class="documento"><a href="/documents/1/2/m.pdf/uuid?t=1">PDF</a>
            <div class="titulo">Memoria</div></div>
            <a href="?folder=12">Planos</a><a href="https://outside.invalid/d">otra web</a>
        '''), root)
        self.assertEqual(list(docs.values()), [{'titulo': 'Memoria',
            'url': BASE + '/documents/1/2/m.pdf/uuid', 'source_urls': [root]}])
        self.assertEqual(children, [root + '?folder=12'])
        with self.assertRaises(ValueError):
            parse_page(page('<a href="?pager_cur=2">2</a>'), root)
        with self.assertRaises(ValueError):
            parse_page('<html>login</html>', root)
        with self.assertRaises(ValueError):
            parse_page(page('no documents'), root)

    def test_traversal_cycles_grouping_and_distinct_approval(self):
        root = BASE + '/es/plan-berezia-poblado-salinas-eta-andonaegi'
        folder = root + '?folder=42'
        doc = '/documents/1/2/approval.pdf/uuid'
        pages = {SOURCE: catalogue('<a href="' + root + '">Plan Especial Poblado, Salinas y Andonaegi</a>'),
            root: page('''<div class="journal-content-article"><ul><li>
                <a href="''' + doc + '''">Resolución de 14 de diciembre de 2023</a>
                de Aprobación definitiva del Proyecto de Urbanización del área 2.06.04 Andonaegi de Pasaia.
                </li></ul></div><a href="?folder=42">documentos</a>'''),
            folder: page('<a href="?folder=42">cycle</a><a href="' + doc + '?t=4">duplicate</a>'
                         '<a href="/documents/1/2/plan.pdf/uuid2">Plan</a>')}
        adapter = PasaiaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as d, patch.object(adapter, '_fetch', side_effect=pages.__getitem__) as fetch:
            output = Path(d) / 'projects.jsonl'
            result = adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(fetch.call_count, 3)
            plan = next(r for r in rows if r['tipo'] == 'planeamiento_urbanistico')
            works = next(r for r in rows if r['tipo'] == 'proyecto_urbanizacion')
            self.assertEqual(len(plan['documentos']), 1)
            self.assertEqual(len(works['documentos']), 1)
            self.assertEqual(works['fecha_acuerdo'], '2023-12-14')
            self.assertIsNone(plan['fecha_aprob'])
            self.assertTrue(all(r['fecha_publicacion'] is None and r['geometry'] is None for r in rows))
            before = output.read_bytes()
            with patch.object(adapter, '_fetch', return_value=page('broken')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(before, output.read_bytes())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('pasaia')
        self.assertEqual((manifest.nombre, manifest.provincia), ('Pasaia', 'Gipuzkoa'))
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'licencias.jsonl'
            result = PasaiaAyuntamientoAdapter().backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_named_modification_owns_its_subfolders(self):
        root = BASE + '/es/nnss'
        sub = BASE + '/es/nnss-c'
        pages = {
            SOURCE: catalogue('<a href="/nnss">Normas subsidiarias</a>'),
            root: page('<a href="/nnss-c">Normas</a><a href="/documents/1/2/base.pdf/u">Base</a>'),
            sub: page('<a href="?folder=1">Modificación NNSS - Salinas</a>'
                      '<a href="?folder=2">Modificación NNSS - Salinas</a>'),
            sub + '?folder=1': page('<a href="?folder=3">Planos</a>'
                                   '<a href="/documents/1/2/mem.pdf/u1">Memoria</a>'),
            sub + '?folder=2': page('<a href="/documents/1/2/mem.pdf/u1?t=2">Memoria</a>'),
            sub + '?folder=3': page('<a href="?folder=1">Modificación NNSS - Salinas</a>'
                                   '<a href="/documents/1/2/map.pdf/u2">Plano</a>'),
        }
        adapter = PasaiaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as d, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            path = Path(d) / 'p.jsonl'
            adapter.backfill_proyectos(path)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        base = next(r for r in rows if r['titulo'] == 'Normas subsidiarias')
        modification = next(r for r in rows if r['titulo'].startswith('Modificación'))
        self.assertEqual(len(base['documentos']), 1)
        self.assertEqual(len(modification['documentos']), 2)
        memory = next(d for d in modification['documentos'] if d['titulo'] == 'Memoria')
        self.assertEqual(len(memory['source_urls']), 2)


if __name__ == '__main__':
    unittest.main()
