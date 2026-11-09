import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.tauste import (
    PLAN, SOURCE, TABS, TausteAyuntamientoAdapter, parse_projects,
    verify_municipal_link,
)
from municipio.manifest import load_manifest


def fixture():
    pages = {t: '<h1>PGOU TAUSTE</h1><a href="https://drive.google.com/open?id=Document12345">Normas</a>' for t in TABS}
    pages['normas'] += '<p>Texto refundido aprobado en Diciembre de 2018.</p><iframe aria-label="Drive, indice.pdf" data-src="https://drive.google.com/file/d/Index12345678/preview"></iframe>'
    return pages


class TausteTests(unittest.TestCase):
    def test_grouping_provenance_and_date_precision(self):
        row, = parse_projects(fixture())
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos'][0]['source_urls']), 4)
        self.assertIn('Diciembre de 2018', row['fecha_aprob_texto'])
        for field in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_missing_dates_not_inferred(self):
        pages = fixture()
        pages['normas'] = pages['planos']
        self.assertIsNone(parse_projects(pages)[0]['fecha_aprob_texto'])

    def test_incomplete_or_changed_inventory_fails(self):
        for tab in TABS:
            pages = fixture()
            pages[tab] = '<h1>Login</h1>'
            with self.assertRaises(ValueError):
                parse_projects(pages)
        pages = fixture()
        del pages['fichas']
        with self.assertRaises(ValueError):
            parse_projects(pages)

    def test_new_tabs_and_pagination_fail(self):
        for link in ['<a href="?page=2" rel="next">2</a>', '<a href="?page=2">Siguiente</a>', '<a href="/view/pgoutauste/nuevos">Nuevos</a>']:
            pages = fixture()
            pages['planos'] += link
            with self.assertRaises(ValueError):
                parse_projects(pages)

    def test_municipal_provenance_required(self):
        verify_municipal_link('<h1>Plan General de Ordenación Urbana de Tauste</h1><a href="' + PLAN + '">PGOU</a>')
        with self.assertRaises(ValueError):
            verify_municipal_link('<h1>Plan General de Ordenación Urbana de Tauste</h1>')

    def test_snapshot_and_manifest(self):
        manifest = load_manifest('tauste')
        self.assertEqual(manifest.provincia, 'Zaragoza')
        self.assertFalse(manifest.licencias.enabled)
        adapter = TausteAyuntamientoAdapter()
        responses = {SOURCE: '<h1>Plan General de Ordenación Urbana de Tauste</h1><a href="'+PLAN+'">PGOU</a>', **{PLAN+'/'+t: html for t, html in fixture().items()}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=lambda url, capture: responses[url]):
            out = Path(tmp) / 'records.jsonl'
            result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['codigo_ine'], '50252')
            self.assertEqual(adapter.backfill_licencias(Path(tmp)/'lic.jsonl')['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
