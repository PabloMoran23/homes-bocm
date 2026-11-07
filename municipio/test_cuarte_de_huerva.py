"""Offline parser tests; synthetic markup exercises semantics, not live records."""
import copy
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.cuarte_de_huerva import (
    CuarteDeHuervaAyuntamientoAdapter, PAGES, SOURCE, parse_projects,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def page(title, body):
    return f'<h1 id="body_content_title">{title}</h1><section id="body_content_left">{body}</section>'


def pdf(name, label=''):
    return f'<a href="/system/resources/test/{name}.pdf">{label}</a>'


class CuarteTests(unittest.TestCase):
    def setUp(self):
        self.pages = {
            SOURCE: page('Urbanismo', pdf('notice', 'Anuncio BOPZ 4 de agosto 2026') +
                         pdf('study', 'Modificación de estudio de detalle manzana 5 del sector 5.2 El Plano') +
                         pdf('memory', 'Memoria modificación manzana 5') +
                         pdf('maps', 'Planos modificación manzana 5')),
            PAGES['plan-general-de-ordenacion-urbana']: page('Plan General de Ordenación Urbana',
                '<p>Revisión del Plan General de Cuarte de Huerva. Se suspendió la ejecutoriedad en 2000.</p>' +
                f'<a href="{PAGES["memoria"]}">Memoria</a><a href="{PAGES["planos"]}">Planos</a>'),
            PAGES['memoria']: page('Memoria del PGOU', pdf('text', 'Texto Refundido')),
            PAGES['planos']: page('Planos del PGOU', pdf('map1', 'Información') +
                                 pdf('map2') + pdf('map2')),
        }
        self.notice = '''Núm. 177 4 agosto 2026 AYUNTAMIENTO DE CUARTE DE HUERVA
        Mediante acuerdo de la Junta de Gobierno Local de 28 de julio de 2026 se ha
        aprobado inicialmente el estudio de detalle relativo a la manzana 5 del sector 5.2.'''

    def test_grouping_dates_and_geometry(self):
        pgou, study = parse_projects(self.pages, self.notice)
        self.assertEqual(len(pgou['documentos']), 3)
        self.assertEqual(len(study['documentos']), 4)
        self.assertEqual(study['fecha_publicacion'], '2026-08-04')
        self.assertEqual(study['fecha_acuerdo'], '2026-07-28')
        self.assertEqual(study['fase'], 'aprobación inicial')
        self.assertIsNone(pgou['fecha_aprob'])
        self.assertIsNone(pgou['fase'])
        self.assertEqual(pgou['documentos'][-1]['titulo'], 'map2.pdf')
        for row in (pgou, study):
            self.assertEqual(row['codigo_ine'], '50089')
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['geometry'])
            self.assertIsNone(row['fecha'])

    def test_stable_identity_when_document_url_changes(self):
        before = parse_projects(self.pages, self.notice)
        changed = {k: v.replace('/test/study.pdf', '/test/study-v2.pdf') for k, v in self.pages.items()}
        self.assertEqual([r['id'] for r in before], [r['id'] for r in parse_projects(changed, self.notice)])

    def test_missing_wrong_or_navigation_only_content_rejected(self):
        for replacement in ('<p>Login</p>', page('Urbanismo', '<a href="/tramites">Licencias</a>')):
            changed = {**self.pages, SOURCE: replacement}
            with self.assertRaises(ValueError):
                parse_projects(changed, self.notice)
        with self.assertRaises(ValueError):
            parse_projects(self.pages, self.notice.replace('CUARTE DE HUERVA', 'OTRO MUNICIPIO'))
        with self.assertRaises(ValueError):
            parse_projects(self.pages, self.notice.replace('se ha\n        aprobado inicialmente', 'se ha aprobado definitivamente'))

    def test_pagination_and_unknown_documents_fail_closed(self):
        for extra in ('<a rel="next" href="?page=2">Siguiente</a>',
                      pdf('other', 'Proyecto de otra urbanización')):
            changed = copy.copy(self.pages)
            changed[SOURCE] = changed[SOURCE].replace('</section>', extra + '</section>')
            with self.assertRaises(ValueError):
                parse_projects(changed, self.notice)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('cuarte-de-huerva')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, CuarteDeHuervaAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '50089')
        self.assertEqual(raw['provincia'], 'Zaragoza')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
