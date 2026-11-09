"""Offline parser/crawler contract tests; run with unittest."""
import json
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.urduliz import (
    BASE, PREFIX, ROOT, UrdulizAyuntamientoAdapter, canonical, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def page(body):
    return '<div id="main-content"><div id="ProcedureContent">' + body + '</div></div>'


def link(name, title):
    return f'<a href="{BASE}{PREFIX}Paginas/{name}">{title}</a>'


def doc(name, title="04-2026 | Documento de avance"):
    return f'<a href="{BASE}{PREFIX}docs/{name}.pdf">{title}</a>'


def inventory(number, names, total, next_page=None):
    return page('<div><h3 class="ms-WPTitle">Documentación gráfica</h3>'
                '<div class="ms-WPBody">Resultados ' + str(number) + ' - ' + str(number)
                + ' de ' + str(total) + ''.join(doc(n) for n in names)
                + (link('pgou-avance.aspx?page=' + str(next_page), '>') if next_page else '')
                + '</div></div>')


class UrdulizTests(unittest.TestCase):
    def adapter(self, fixtures):
        adapter = UrdulizAyuntamientoAdapter('urduliz')
        adapter._fetch = fixtures.__getitem__
        return adapter

    def test_manifest(self):
        m = load_manifest('urduliz')
        raw = load_yaml(m.path)
        self.assertEqual((m.nombre, m.provincia, raw['codigo_ine']), ('Urduliz', 'Bizkaia', '48089'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(m.licencias.enabled)

    def test_content_scope_labels_and_dedup(self):
        parsed = parse_page('<a href="https://example.org/unrelated.pdf">outside</a>'
                            + page(doc('one') + doc('one') + link('PGOU.aspx', 'PGOU')), ROOT)
        self.assertEqual(len(parsed['documents']), 1)
        self.assertEqual(next(iter(parsed['documents'].values()))['source_url'], ROOT)

    def test_missing_markup_and_unsafe_pagination(self):
        for html in ('<html>error</html>', page('<a href="?offset=20">Siguiente</a>'),
                     page('<a href="https://example.org/?page=2">Next</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_page(html, ROOT)
        self.assertEqual(canonical(ROOT + '?page=1'), ROOT)

    def test_pagination_follows_last_page_and_deduplicates(self):
        start = BASE + PREFIX + 'Paginas/pgou-avance.aspx'
        fixtures = {start: inventory(1, ['a'], 3, 2),
                    start + '?page=2': inventory(2, ['a', 'b'], 3, 3),
                    start + '?page=3': inventory(3, ['c'], 3)}
        _, docs, sources = self.adapter(fixtures)._inventory(start)
        self.assertEqual(len(docs), 3)
        self.assertEqual(len(sources), 3)

    def test_incomplete_and_changing_totals_rejected(self):
        start = BASE + PREFIX + 'Paginas/pgou-avance.aspx'
        for fixtures in ({start: inventory(1, ['a'], 137)},
                         {start: inventory(1, ['a'], 2, 2),
                          start + '?page=2': inventory(2, ['b'], 3)}):
            with self.assertRaises(ValueError):
                self.adapter(fixtures)._inventory(start)

    def test_full_snapshot_groups_instruments_and_keeps_unknown_dates(self):
        base = BASE + PREFIX + 'Paginas/'
        fixtures = {
            ROOT: page(link('PGOU.aspx', '') + link('planeamiento-desarrollo.aspx', 'Planeamiento')),
            base + 'planeamiento-desarrollo.aspx': page(link('centro.aspx', 'Plan Especial del centro de salud')),
            base + 'centro.aspx': page(doc('memoria') + doc('plano')),
            base + 'PGOU.aspx': page(link('documentacion.aspx', 'Documentación técnica')),
            base + 'documentacion.aspx': page(link('pgou-avance.aspx', 'Avance')),
            base + 'pgou-avance.aspx': inventory(1, ['avance'], 2, 2),
            base + 'pgou-avance.aspx?page=2': inventory(2, ['anexo'], 2),
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            adapter = self.adapter(fixtures)
            self.assertEqual(adapter.backfill_proyectos(out)['rows'], 2)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual([len(r['documentos']) for r in rows], [2, 2])
            for row in rows:
                for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                    self.assertIsNone(row[key])
            ids = [r['id'] for r in rows]
            adapter.update_proyectos(out, Path(tmp) / 'unused-state')
            self.assertEqual(ids, [json.loads(line)['id'] for line in out.read_text().splitlines()])
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')

    def test_failed_snapshot_does_not_replace_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                self.adapter({ROOT: page('no inventory')}).backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
