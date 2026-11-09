"""Offline structural and semantic regressions for the Lazkao inventories."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.lazkao import (
    DIAGNOSTICO, NORMAS, PGOU, VIEWER, LazkaoAyuntamientoAdapter,
    parse_normas, parse_pgou,
)
from municipio.manifest import load_manifest

NORMAS_PAGE = f'<h1>Normas subsidiarias</h1><iframe src="{VIEWER}"></iframe>'
NORMAS_DOCS = '''<h1>Normas Subsidiarias de Lazkao</h1><div id="deskarga">
<a href="dokumentazioa/Txostena.pdf">Memoria general</a>
<a href="dokumentazioa/NORMAS GENERALES.pdf">Normas Generales</a>
<a href="dokumentazioa/NORMAS GENERALES.pdf">Normas Generales</a></div>
<a href="unrelated.pdf">Fuera del inventario</a>'''
START = f'''<div class="item-page"><div class="page-header"><h2>Nuevo Plan General de Ordenación Urbana de Lazkao</h2></div>
<p>Fase 7: Aprobación definitiva PGOU. Año 2025.</p></div>
<a href="{DIAGNOSTICO}">Diagnóstico PGOU</a>'''


def document(number, title):
    return f'''<div class="pd-filebox"><div class="pd-title">{title}</div>
<div class="pd-filename"><a href="?download={number}:documento">archivo.pdf</a></div>
<div class="pd-buttons"><a href="?download={number}:documento">Descarga</a></div>
<a onmouseover="Fecha: 06 Noviembre 2025">Info</a></div>'''


DOCS = '<div id="phoca-dl-category-box"><h3 class="pd-ctitle">PGOU</h3>' + document(128, '00 Diagnóstico') + document(100, "PTP'08 contexto") + '</div><div class="pagination"></div>'


class LazkaoTests(unittest.TestCase):
    def test_normas_grouping_provenance_and_encoded_links(self):
        row = parse_normas(NORMAS_PAGE, NORMAS_DOCS)
        self.assertEqual(row['id'], 'lazkao-proy-nnss')
        self.assertEqual(len(row['documentos']), 2)
        self.assertTrue(row['documentos'][1]['url'].endswith('NORMAS%20GENERALES.pdf'))
        self.assertEqual(row['source_urls'], [NORMAS, VIEWER])
        self.assertEqual(row['codigo_ine'], '20049')

    def test_pgou_annexes_are_not_projects_or_approval_dates(self):
        row = parse_pgou(START, DOCS)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['source_url'], DIAGNOSTICO)
        for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'geometry', 'lat', 'lon'):
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)  # A list of future stages is not an actual approval.

    def test_reject_navigation_only_and_missing_documents(self):
        for start, docs in [('<a>PGOU</a>', DOCS), (START, '<h1>PGOU</h1>'),
                            (START, DOCS.replace('00 Diagnóstico', 'Solicitud licencia'))]:
            with self.assertRaises(ValueError):
                parse_pgou(start, docs)
        with self.assertRaises(ValueError):
            parse_normas(NORMAS_PAGE, NORMAS_DOCS.replace('Normas Generales', 'Impreso'))
        with self.assertRaises(ValueError):
            parse_normas(NORMAS_PAGE.replace(VIEWER, 'https://example.org'), NORMAS_DOCS)

    def test_pagination_never_silently_truncated(self):
        for extra in ['<div class="pagination"><a href="?limitstart=20">2</a></div>',
                      '<a rel="next" href="/next">→</a>', '<a href="?start=20">2</a>']:
            with self.assertRaisesRegex(ValueError, 'pagination'):
                parse_pgou(START, DOCS + extra)
            with self.assertRaisesRegex(ValueError, 'pagination'):
                parse_normas(NORMAS_PAGE, NORMAS_DOCS + extra)

    def test_refresh_disabled_licences_and_failure_preserves_output(self):
        fixtures = {NORMAS: NORMAS_PAGE, VIEWER: NORMAS_DOCS, PGOU: START, DIAGNOSTICO: DOCS}
        adapter = LazkaoAyuntamientoAdapter('lazkao')
        with TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=lambda u, n: fixtures[u]):
            dest = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(dest, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len([json.loads(line) for line in dest.read_text().splitlines()]), 2)
            before = dest.read_bytes()
            fixtures[DIAGNOSTICO] = '<h1>Unexpected page</h1>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(dest)
            self.assertEqual(dest.read_bytes(), before)
            licences = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(licences)['status'], 'disabled')
            self.assertEqual(licences.read_bytes(), b'')

    def test_manifest(self):
        manifest = load_manifest('lazkao')
        self.assertEqual(manifest.provincia, 'Gipuzkoa')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.lazkao:LazkaoAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
