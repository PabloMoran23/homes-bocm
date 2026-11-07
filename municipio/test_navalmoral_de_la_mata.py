import tempfile
import unittest
from pathlib import Path

from municipio.adapters.navalmoral_de_la_mata import (
    NavalmoralDeLaMataAyuntamientoAdapter, SOURCE, parse_projects,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


PREFIX = 'http://www.aytonavalmoral.es/wp-content/uploads/2025/10/'
PDF = PREFIX + '2025-09-23_PGM-Navalmoral-de-la-Mata-Viviendas-irregulares.pdf'


def fixture(links=None):
    links = links if links is not None else [(PDF, '23 de Octubre 2025 PGM-Viviendas irregulares')]
    return '''<div class="entry-content"><h1>Nuevo Plan General Municipal</h1>
    <p>Navalmoral de la Mata. El proceso de participación incluye un buzón.</p>
    <a href="/solicitud-licencia/">Solicitud licencia</a>
    <div class="et_pb_text_inner"><p>DOCUMENTACIÓN</p>''' + ''.join(
        f'<p><a href="{u}">{t}</a></p>' for u, t in links
    ) + '</div></div>'


class PGMTests(unittest.TestCase):
    def test_grouping_provenance_and_unknown_dates(self):
        other = PREFIX + '2025-09-23_PGM-Navalmoral-de-la-Mata-Vivienda-y-Actividad-Economica.pdf'
        rows = parse_projects(fixture([(PDF, '23 de Octubre 2025'), (other, 'Actividad'), (PDF, 'Duplicado')]))
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(len(r['documentos']), 2)
        self.assertEqual(r['documentos'][0]['url'], PDF)
        self.assertEqual(r['documentos'][0]['source_url'], SOURCE)
        self.assertEqual(r['documentos'][0]['titulo'], '23 de Octubre 2025')
        for k in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(r[k])
        self.assertFalse(r['publication_ready'])
        self.assertEqual(r['codigo_ine'], '10131')

    def test_identity_stable_as_documents_change(self):
        a = parse_projects(fixture())[0]['id']
        b = parse_projects(fixture([(PDF + '?download=1', 'Otro rótulo')]))[0]['id']
        self.assertEqual(a, b)

    def test_forms_navigation_and_empty_inventory_fail(self):
        for html in ('<h1>Login</h1>', '<a href="/pgm">Nuevo Plan General Municipal</a>', fixture([])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_projects(html)

    def test_missing_participation_fails(self):
        with self.assertRaises(ValueError):
            parse_projects(fixture().replace('El proceso de participación', 'Información'))

    def test_wrong_document_or_external_provenance_fails(self):
        for url in ('https://example.org/pgm.pdf', PREFIX + 'solicitud-licencia.pdf', '/next-page/'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_projects(fixture([(url, 'Documento')]))

    def test_pagination_is_not_silently_truncated(self):
        for extra in ('<a rel="next" href="/page/2">Siguiente</a>', '<div class="page-links">2</div>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_projects(fixture() + extra)

    def test_manifest_loading_and_disabled_licences(self):
        manifest = load_manifest('navalmoral-de-la-mata')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, NavalmoralDeLaMataAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'licencias.jsonl'
            result = adapter.backfill_licencias(output)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
