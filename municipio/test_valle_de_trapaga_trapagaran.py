"""Offline parser/graph tests: synthetic fixtures, no dependency on evidence files."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.valle_de_trapaga_trapagaran import (
    BASE, PREFIX, SOURCE, ValleDeTrapagaTrapagaranAyuntamientoAdapter,
    parse_page, publication_date,
)
from municipio.manifest import load_manifest

ROOT = BASE + PREFIX + 'Paginas/proyecto.aspx'
CHILD = BASE + PREFIX + 'Paginas/fase.aspx'
DOC = BASE + PREFIX + 'proyecto/plano.pdf'
DOC2 = BASE + PREFIX + 'proyecto/memoria.pdf'


def page(title, links='', text=''):
    return ('<div id="SectionBody"><div class="articleInfoBox"><h3>' + title
            + '</h3></div><div class="contentArticle"><div class="ms-rtestate-field">'
            + text + '</div></div>' + links + '<div class="viewMore">'
            '<a href="/es-ES/Servicios/Urbanismo/">Ir a lista</a></div></div>')


def link(url, title):
    return f'<a href="{url}">{title}</a>'


class TrapagaranTests(unittest.TestCase):
    def adapter(self):
        return ValleDeTrapagaTrapagaranAyuntamientoAdapter('valle-de-trapaga-trapagaran')

    def test_manifest_contract(self):
        manifest = load_manifest('valle-de-trapaga-trapagaran')
        self.assertEqual(manifest.provincia, 'Bizkaia')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIn('valle_de_trapaga_trapagaran:', manifest.portal.adapter)

    def test_publication_not_agreement_or_filename_date(self):
        text = ('En el Boletín Oficial de Bizkaia nº 145 d4e 30 de julio de 2020 '
                'se ha publicado el anuncio relativo a la aprobación inicial.')
        self.assertEqual(publication_date(text), '2020-07-30')
        self.assertIsNone(publication_date('Acuerdo de 30 de julio de 2020'))
        self.assertIsNone(publication_date('20211103-anuncio.pdf'))

    def test_parser_scopes_navigation_and_rejects_missing_structure(self):
        parsed = parse_page(link(BASE + '/unrelated', 'Outside') + page('Proyecto', link(DOC, 'Plano')), ROOT)
        self.assertEqual(parsed['documentos'], {DOC: 'Plano'})
        self.assertEqual(parsed['paginas'], {})
        with self.assertRaises(ValueError):
            parse_page('<html>Service unavailable</html>', ROOT)
        with self.assertRaises(ValueError):
            parse_page(page('Proyecto', link('javascript:__doPostBack(1)', 'Siguiente')), ROOT)
        with self.assertRaises(ValueError):
            parse_page(page('Proyecto', link('https://external.example/a', 'Documento')), ROOT)

    def fixtures(self):
        return {
            SOURCE: page('Proyectos de urbanización', link(SOURCE + '?page=2', '2')),
            SOURCE + '?page=2': page('Proyectos de urbanización', link(ROOT, 'Proyecto de Urbanización Ejemplo')),
            ROOT: page('Proyecto de Urbanización Ejemplo', link(CHILD, 'Fase 0') + link(DOC, 'Plano')),
            CHILD: page('Fase 0', link(DOC, 'Plano') + link(CHILD + '?page=2', '>')),
            CHILD + '?page=2': page('Fase 0', link(DOC2, 'Memoria') + link(CHILD, '1')),
        }

    def test_pagination_grouping_and_provenance(self):
        a = self.adapter()
        fixtures = self.fixtures()
        with tempfile.TemporaryDirectory() as d, patch.object(a, '_fetch', side_effect=fixtures.__getitem__) as fetch:
            out = Path(d) / 'records.jsonl'
            result = a.backfill_proyectos(out)
            rows = [json.loads(s) for s in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 1)
            self.assertEqual(fetch.call_count, 5)
            row = rows[0]
            self.assertEqual(len(row['documentos']), 2)
            self.assertEqual(len(row['documentos'][0]['procedencia']), 2)
            self.assertEqual(row['codigo_ine'], '48080')
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['geometry'])
            self.assertFalse(row['publication_ready'])
            stable_id = row['id']
            a.update_proyectos(out, Path(d) / 'state.json')
            self.assertEqual(json.loads(out.read_text())['id'], stable_id)

    def test_failed_document_page_preserves_previous_output(self):
        a = self.adapter()
        fixtures = self.fixtures()
        fixtures[CHILD + '?page=2'] = '<html>Error</html>'
        with tempfile.TemporaryDirectory() as d, patch.object(a, '_fetch', side_effect=fixtures.__getitem__):
            out = Path(d) / 'records.jsonl'
            out.write_text('previous snapshot\n')
            with self.assertRaises(ValueError):
                a.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')

    def test_forms_are_not_inventory_projects_and_licences_disabled(self):
        a = self.adapter()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'records.jsonl'
            with patch.object(a, '_fetch', return_value=page('Proyectos de urbanización', link(ROOT, 'Solicitud de licencia'))):
                with self.assertRaises(ValueError):
                    a.backfill_proyectos(out)
            self.assertFalse(out.exists())
            self.assertEqual(a.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
