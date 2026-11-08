"""Offline parser contract tests; all content here is a synthetic fixture."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.caudete import CaudeteAyuntamientoAdapter, SOURCE
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def fixture():
    return '''<div class="entry"><h1>Obras y Urbanismo – Legislación</h1><ul><li><ul>
    <li>Texto de Normas Subsidiarias de Planeamiento de Caudete.
    No incluyen modificaciones puntuales ni estudios de detalle.
    <a href="http://www.caudete.org/urbanismo/TEXTO NNSS 29_05_96.pdf">Pulse aquí</a></li>
    <li>Planos de Alineaciones y Rasantes de Normas Subsidiarias de Planeamiento de Caudete.
    <a href="/urbanismo/NNSS.jpg">Alta resolución</a>
    <a href="/urbanismo/NNSS2.jpg">Baja resolución</a></li>
    <li>Planos agrupados. <a href="/urbanismo/PLANOS AGRUPADOS NNSS.pdf">Pulse aquí</a></li>
    <li>Acuerdo de la Comisión Provincial de Urbanismo de Aprobación del Proyecto de
    Revisión de Normas Subsidiarias <a href="https://docm.jccm.es/docm/descargarDisposicionAntigua.do?ruta=1996/06/28&amp;idDisposicion=123">Pulse aquí</a></li>
    <li>Aprobación definitiva Texto Refundido de las Normas Subsidiarias de Caudete.
    <a href="/urbanismo/PUBLICACION NNSS BOP CAUDETE.pdf">Pulse aquí</a></li>
    <li>Ordenanza Fiscal Nº 7 licencias urbanísticas <a href="/urbanismo/OF7.pdf">Pulse aquí</a></li>
    <li>Solicitud licencia de obra <a href="/form.pdf">Formulario</a></li>
    <li>Protección del patrimonio arqueológico en el planeamiento urbanístico de Caudete
    <a href="/patrimonio.pdf">Pulse aquí</a></li>
    </ul></li></ul></div>'''


class CaudeteTests(unittest.TestCase):
    def test_groups_documents_excludes_forms_and_legislation(self):
        rows = CaudeteAyuntamientoAdapter.parse_projects(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '02025')
        self.assertEqual(len(row['documentos']), 6)
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        self.assertEqual(row['documentos'][0]['url'],
                         'https://www.caudete.org/urbanismo/TEXTO%20NNSS%2029_05_96.pdf')
        self.assertTrue(row['documentos'][0]['url_original'].startswith('http:'))
        self.assertIn('modificaciones puntuales', row['cobertura'])

    def test_no_dates_from_filenames_or_geometry_from_municipality(self):
        row = CaudeteAyuntamientoAdapter.parse_projects(fixture())[0]
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_incomplete_or_navigation_only_page_fails(self):
        for html in ('<a href="/urbanismo/nnss.pdf">Normas Subsidiarias</a>',
                     fixture().replace('Texto de Normas Subsidiarias', 'Texto genérico'),
                     fixture().replace('Aprobación definitiva Texto Refundido', 'Documento desconocido')):
            with self.subTest(html=html[:70]), self.assertRaises(ValueError):
                CaudeteAyuntamientoAdapter.parse_projects(html)

    def test_pagination_never_silently_truncated(self):
        for pager in ('<a rel="next" href="?page=2">2</a>',
                      '<div class="pagination">2</div>',
                      '<a href="?page=2">Siguiente</a>'):
            with self.subTest(pager=pager), self.assertRaises(ValueError):
                CaudeteAyuntamientoAdapter.parse_projects(fixture().replace('</div>', pager + '</div>'))

    def test_unreviewed_document_host_and_empty_link_fail(self):
        for replacement in ('https://example.com/nnss.pdf', '#'):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                CaudeteAyuntamientoAdapter.parse_projects(fixture().replace(
                    'http://www.caudete.org/urbanismo/TEXTO NNSS 29_05_96.pdf', replacement))

    def test_duplicates_do_not_create_instruments_or_documents(self):
        html = fixture().replace('>Alta resolución</a>', '>Alta resolución</a><a href="/urbanismo/NNSS.jpg">duplicado</a>')
        row = CaudeteAyuntamientoAdapter.parse_projects(html)[0]
        self.assertEqual(len(row['documentos']), 6)
        self.assertEqual(row['id'], CaudeteAyuntamientoAdapter.parse_projects(fixture())[0]['id'])

    def test_disabled_licences_and_snapshot_update(self):
        adapter = CaudeteAyuntamientoAdapter('caudete')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            out.write_text('stale record')
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 1}) as backfill:
                adapter.update_proyectos(out, Path(tmp) / 'state.json')
                backfill.assert_called_once_with(out)

    def test_manifest_contract_and_registry(self):
        manifest = load_manifest('caudete')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('02025', 'Caudete', 'Albacete'))
        for section, flag in (('schedule', 'enabled'), ('geocode', 'jitter_missing'), ('licencias', 'enabled')):
            self.assertIs(raw[section][flag], False)
        self.assertIsInstance(load_portal_adapter(manifest), CaudeteAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
