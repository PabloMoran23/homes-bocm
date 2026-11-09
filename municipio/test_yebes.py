"""Offline contract tests for the live Yebes document inventory adapter."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from municipio.adapters.yebes import (
    BASE, INVENTORY, INSTRUMENTS, YebesAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def page(entries):
    return '<h1>Ayuntamiento de Yebes</h1><table class="TransparencyListPanel">' + entries + '</table>'


def doc(name, ident):
    return f'<tr><td><a href="{BASE}/preview-document/{ident}">{name}</a></td></tr>'


def folder(name, count, ident):
    return (f'<a class="exp" href="#" onclick="wicketAjaxGet(\'?x={ident}\')">'
            f'{name} ( {count} )</a>')


class YebesTests(TestCase):
    def fixture(self):
        pages = {INVENTORY: page(''.join(folder(label, 2, n) for n, label in enumerate(INSTRUMENTS)))}
        for n in range(4):
            pages[f'{BASE}/transparency/test{n}/'] = page(doc(('Mod N 2 POM. Memoria 20210724' if n == 0 else '26004_MpPP nº 2 S1 Yebes_Memoria' if n == 3 else 'Memoria 20210724'), f'{n}-a') + folder('Versión anterior', 1, f'child{n}'))
            pages[f'{BASE}/transparency/testchild{n}/'] = page(doc(('Mod N 2 POM. Planos' if n == 0 else '26004_MpPP nº 2 S1 Yebes_TRNNUU' if n == 3 else 'Planos'), f'{n}-b'))
        return pages

    def run_fixture(self, pages, output):
        adapter = YebesAyuntamientoAdapter('yebes')
        def get(session, url, ajax=False):
            return SimpleNamespace(text=pages[url])
        def child(session, f):
            return f"{BASE}/transparency/test{f['callback'].split('=')[-1]}/"
        with patch.object(adapter, '_get', side_effect=get), patch.object(adapter, '_folder', side_effect=child):
            return adapter.backfill_proyectos(output)

    def test_grouping_provenance_dates_and_stable_identity(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            self.assertEqual(self.run_fixture(self.fixture(), out)['rows'], 4)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual([len(r['documentos']) for r in rows], [2] * 4)
            self.assertEqual(len({r['id'] for r in rows}), 4)
            for row in rows:
                self.assertEqual(row['codigo_ine'], '19326')
                for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                    self.assertIsNone(row[field])
                self.assertFalse(row['publication_ready'])
                self.assertIn('/testchild', row['documentos'][1]['inventory_url'])
            self.assertEqual(rows[3]['fase'], 'en tramitación')
            first = out.read_bytes()
            self.run_fixture(self.fixture(), out)
            self.assertEqual(out.read_bytes(), first)

    def test_count_mismatch_preserves_previous_snapshot(self):
        pages = self.fixture()
        pages[f'{BASE}/transparency/testchild0/'] = page(doc('Extra', 'x') + doc('Extra 2', 'y'))
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaisesRegex(ValueError, 'count mismatch'):
                self.run_fixture(pages, out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_fail_closed_for_pagination_login_and_external_documents(self):
        for html in ('<h1>Identifícate</h1>', page(doc('Plan', 'a')) + '<a>Mostrar más</a>',
                     page('<a href="https://example.org/preview-document/a">Memoria</a>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, INVENTORY)

    def test_missing_instrument_does_not_emit_records(self):
        pages = self.fixture()
        pages[INVENTORY] = page(folder('Formularios de licencia', 2, 0))
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            with self.assertRaisesRegex(ValueError, 'Missing or ambiguous'):
                self.run_fixture(pages, out)
            self.assertFalse(out.exists())

    def test_licences_disabled_and_manifest_loads(self):
        m = load_manifest('yebes')
        self.assertEqual((m.nombre, m.provincia), ('Yebes', 'Guadalajara'))
        self.assertFalse(m.licencias.enabled)
        self.assertEqual(m.portal.adapter, 'municipio.adapters.yebes:YebesAyuntamientoAdapter')
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            result = YebesAyuntamientoAdapter('yebes').backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    main()
