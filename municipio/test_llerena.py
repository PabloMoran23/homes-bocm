"""Parser contract tests; synthetic markup, no network or local evidence required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.llerena import (
    LlerenaAyuntamientoAdapter, MODIFICATIONS, parse_modifications, parse_pgm, parse_works,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(body):
    return '<section id="content"><div class="post-content">' + body + '</div></section>'


MOD = page('''<table><tr><td>Aprobación definitiva. Modificación 1/2024.
Cambio de calificación dotacional. Parcela San Antón, nº3</td><td>
<a href="/wp-content/uploads/2025/11/notice.pdf">Anuncio DOE 31 – Octubre – 2025</a></td>
<td><a href="/wp-content/uploads/2025/11/agreement-31-07-2025.pdf">Acuerdo. Anexos</a>
<a href="https://drive.google.com/file/d/test/view?usp=sharing">Plano</a></td></tr></table>''')
PGM_PAGE = page('''<h3>Planos Llerena Información</h3><h3>Planos Llerena Ordenación</h3>
<h3>Información General</h3><a href="#planos">Planos</a>
<a href="/memoria.pdf">MEMORIA JUSTIFICATIVA</a><a href="/normativa.pdf">NORMATIVA</a>
<a href="/normativa.pdf">NORMATIVA repetida</a>''')
WORK_PAGE = page('''<ul><li><a href="https://drive.google.com/file/d/project/view">
Proyecto de construcción de nuevos nichos en el Cementerio Municipal (Módulo K)</a></li>
<li><a href="/notice.pdf">Anuncio exposición pública construcción nuevo módulo en el Cementerio Municipal</a></li></ul>''')


class LlerenaTests(unittest.TestCase):
    def test_modification_groups_documents_and_preserves_date_meaning(self):
        rows = parse_modifications(MOD)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '06074')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['fecha_publicacion'], '2025-10-31')
        self.assertIsNone(row['fecha_acuerdo'])  # not from a filename
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertEqual(row['documentos'][2]['source_url'], MODIFICATIONS)
        self.assertEqual(row['documentos'][2]['alojamiento'], 'enlace_externo_municipal')
        self.assertIsNone(row['geometry'])

    def test_multiple_instruments_and_stable_ids(self):
        second = MOD.replace('1/2024', '2/2024')
        body = '<table>' + MOD.split('<table>')[1].split('</table>')[0] + second.split('<table>')[1].split('</table>')[0] + '</table>'
        rows = parse_modifications(page(body))
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[0]['id'], parse_modifications(MOD.replace('San Antón', 'San Antón corregido'))[0]['id'])

    def test_pgm_one_instrument_with_deduplicated_documents(self):
        rows = parse_pgm(PGM_PAGE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertNotIn('fase', rows[0])

    def test_works_groups_project_and_public_notice_without_approval_claim(self):
        row = parse_works(WORK_PAGE)[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertNotIn('fase', row)
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_aprob'])

    def test_pagination_rejected_for_all_inventories(self):
        for parser, html in [(parse_pgm, PGM_PAGE), (parse_modifications, MOD), (parse_works, WORK_PAGE)]:
            for pagination in ['<a href="?page=2" rel="next">2</a>', '<a href="?page=2">Siguiente</a>', '<div class="page-links">1 2</div>']:
                with self.subTest(parser=parser.__name__, pagination=pagination), self.assertRaises(ValueError):
                    parser(html + pagination)

    def test_forms_login_and_changed_structure_rejected(self):
        for parser in [parse_pgm, parse_modifications, parse_works]:
            for html in ['<html>Login</html>', page('<a href="/solicitud.pdf">Licencia urbanística</a>')]:
                with self.subTest(parser=parser.__name__), self.assertRaises(ValueError):
                    parser(html)
        with self.assertRaises(ValueError):
            parse_modifications(MOD.replace('Octubre', 'Unknown'))
        with self.assertRaises(ValueError):
            parse_modifications(MOD.replace('31 – Octubre', '32 – Octubre'))
        with self.assertRaises(ValueError):
            parse_works(WORK_PAGE.replace('</ul>', '<li><a href="/new.pdf">Proyecto nuevo</a></li></ul>'))
        with self.assertRaises(ValueError):
            parse_modifications(MOD.replace('drive.google.com', 'unverified.example'))

    def test_snapshot_fetch_failure_does_not_overwrite_existing_output(self):
        adapter = LlerenaAyuntamientoAdapter('llerena')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            output.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[PGM_PAGE, RuntimeError('network failed')]):
                with self.assertRaises(RuntimeError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_manifest_registry_snapshot_and_disabled_licences(self):
        adapter = load_portal_adapter(load_manifest('llerena'))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[PGM_PAGE, MOD, WORK_PAGE]):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 3)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 3)
            with patch.object(adapter, '_fetch', side_effect=AssertionError('licences must not fetch')):
                self.assertEqual(adapter.backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
