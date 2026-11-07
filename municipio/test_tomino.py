import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.tomino import SOURCE, TominoAyuntamientoAdapter
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest


def section(title, links):
    return '<h5 class="title-holder">' + title + '</h5><div class="accordion_content">' + links + '</div>'


def document(name='Memoria', href='/wp-content/uploads/2026/02/memoria.pdf'):
    return f'<a href="{href}">{name}</a>'


def inventory(extra=''):
    return ('<h3>Plan Xeral de Ordenación Municipal (PXOM) e outros planeamentos</h3>'
            + section('PXOM 2001 - Normativa', document()) + extra
            + '<h3>Trámites e Procedementos</h3>'
            + section('Licenzas de obra con proxecto técnico', document('FORMULARIO')))


class TominoTests(unittest.TestCase):
    def test_group_documents_and_exclude_forms_and_instructions(self):
        rows = TominoAyuntamientoAdapter.parse_projects(inventory(
            section('PXOM 2001 – PLANOS DE CLASIFICACIÓN DO SOLO E 1/5.000',
                    document('Plano', 'http:///tomino.gal/wp-content/uploads/2015/10/plano.pdf'))
            + section('INSTRUCCIÓN DE SERVIZO NÚM. 1/2024', document('Exemplo'))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        doc = rows[0]['documentos'][1]
        self.assertTrue(doc['url'].startswith('https://tomino.gal/'))
        self.assertTrue(doc['href_original'].startswith('http:///'))
        self.assertEqual(doc['url_procedencia'], SOURCE)

    def test_initial_phase_not_dates_from_upload_or_filename(self):
        row = TominoAyuntamientoAdapter.parse_projects(inventory(section(
            'M.P. Nº 10 - PARQUE AGRO INDUSTRIAL (APROBACIÓN INICIAL)',
            document('36054_MP10PXOM_202212_AI.pdf', 'https://drive.google.com/file/d/abc/view?usp=sharing'))))[1]
        self.assertEqual(row['fase'], 'aprobación inicial')
        for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertEqual(row['id'], 'tomino-proy-mp-10')

    def test_fail_closed_on_missing_or_changed_inventory(self):
        for html in ('<h1>Login</h1>', inventory().replace('<h3>Trámites e Procedementos</h3>', ''),
                     inventory(section('NOVO PLAN', document())),
                     inventory(section('M.P. Nº 9 - TEST', '')),
                     inventory(section('M.P. Nº 9 - TEST', document(href='https://example.org/file.pdf')))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                TominoAyuntamientoAdapter.parse_projects(html)

    def test_pagination_never_silently_truncated(self):
        for marker in ('<a rel="next" href="?page=2">Next</a>', '<div class="pagination">2</div>'):
            with self.assertRaises(ValueError):
                TominoAyuntamientoAdapter.parse_projects(inventory() + marker)

    def test_manifest_registry_and_disabled_licences(self):
        manifest = load_manifest('tomino')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            with patch.object(TominoAyuntamientoAdapter, 'backfill_proyectos',
                              lambda self, output: self._write(output, self.parse_projects(inventory()))):
                adapter = load_portal_adapter(manifest)
                result = adapter.backfill_proyectos(path)
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(path.read_text())['codigo_ine'], '36054')
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
