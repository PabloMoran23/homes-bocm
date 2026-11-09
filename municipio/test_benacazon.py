"""Offline parser and crawler regressions; no evidence files required."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import Mock, patch

import requests

from municipio.adapters.benacazon import (
    BenacazonAyuntamientoAdapter, DOC_ROOT, SOURCE, page_url, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def document(path, title):
    return f'<a href="{DOC_ROOT}{path}">{title}</a>'


def page(number=1, extra=''):
    return (f'<h4>NORMAS SUBSIDIARIAS</h4>'
            + document(f'pgou/nnss-{number}.PDF', f'NNSS plano {number}')
            + '<h3>Proyecto del PGOU, planimetría</h3><h4>Información</h4>'
            + document('avance-pgou/informacion/plano.pdf', 'AVANCE PGOU plano')
            + '<h3>Aprobación Inicial del PGOU, planimetría</h3>'
            + document('avance-pgou/informacion/plano.pdf', 'AVANCE PGOU plano')
            + '<h3>Aprobación Inicial del PGOU en el BOP</h3><h4>'
            + document('avance-pgou/16.pdf', '16') + '</h4>' + extra)


def pagination(number, last=3):
    return (f'<ul class="pagination"><li class="active"><a>{number}</a></li>'
            f'<li><a class="lastpagelink" href="{page_url(last)}#galleryfiles-1-1">Última</a></li></ul>')


class BenacazonTests(TestCase):
    def test_grouping_and_duplicate_section_provenance(self):
        groups, pages = parse_inventory(page(), SOURCE)
        self.assertEqual(set(groups), {'nnss', 'pgou'})
        self.assertFalse(pages)
        docs = list(groups['pgou']['documentos'].values())
        self.assertEqual(len(docs), 2)
        self.assertEqual(len(docs[0]['secciones_fuente']), 2)
        self.assertEqual(docs[1]['secciones_fuente'], ['Aprobación Inicial del PGOU en el BOP'])
        self.assertEqual(len(groups['nnss']['documentos']), 1)

    def test_unrelated_sources_are_not_projects(self):
        for html in ('<h1>Sin datos</h1>',
                     '<h4>Solicitud de licencia</h4>' + document('pgou/formulario.pdf', 'Impreso'),
                     '<h4>NORMAS SUBSIDIARIAS</h4><a href="https://otro.es/plan.pdf">Plan</a>',
                     '<h3>Contratación</h3>' + document('avance-pgou/anuncio.pdf', 'Licitación')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCE)

    def test_pagination_includes_intermediate_pages(self):
        _, pages = parse_inventory(page(extra=pagination(1, 5)), SOURCE)
        self.assertEqual(pages, {1, 2, 3, 4, 5})
        for href in ('?offset=20', page_url(101), 'https://otro.es/?pagegalleryfiles-1-1=2'):
            with self.subTest(href=href), self.assertRaises(ValueError):
                parse_inventory(page(extra=f'<ul class="pagination"><a href="{href}">Next</a></ul>'), SOURCE)

    def test_opencms_shared_parameter_out_of_range_next(self):
        smaller = ('<ul class="pagination">'
                   f'<a href="{page_url(3)}">3</a>'
                   f'<a class="nextpagelink" href="{page_url(4)}">Next</a>'
                   f'<a class="lastpagelink" href="{page_url(2)}">Last</a></ul>')
        _, pages = parse_inventory(page(3, pagination(3) + smaller), page_url(3))
        self.assertEqual(pages, {1, 2, 3})
        terminal = ('<ul class="pagination">'
                    f'<a href="{page_url(3)}">3</a>'
                    '<a class="lastpagelink" href="#galleryfiles-1-1">Last</a></ul>')
        self.assertEqual(parse_inventory(page(3, terminal), page_url(3))[1], {1, 2, 3})

    def test_document_in_wrong_group_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory('<h4>NORMAS SUBSIDIARIAS</h4>' + document('avance-pgou/plan.pdf', 'Plan'), SOURCE)

    def test_live_contract_offline_full_crawl_and_refresh(self):
        def get(url, **kwargs):
            number = {page_url(n): n for n in (1, 2, 3)}[url]
            return Mock(url=url, text=page(number, pagination(number)))
        with TemporaryDirectory() as temp, patch('municipio.adapters.benacazon.requests.Session') as session:
            client = session.return_value.__enter__.return_value
            client.get.side_effect = get
            adapter = BenacazonAyuntamientoAdapter('benacazon')
            output = Path(temp) / 'projects.jsonl'
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['count'], 2)
            self.assertEqual(client.get.call_count, 3)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            nnss = next(r for r in rows if r['id'].endswith('nnss'))
            self.assertEqual(len(nnss['documentos']), 3)
            for row in rows:
                self.assertEqual(row['codigo_ine'], '41015')
                self.assertFalse(row['publication_ready'])
                self.assertFalse(set(row) & {'fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'})
            adapter.update_proyectos(output, Path(temp) / 'state.json')
            self.assertEqual(client.get.call_count, 6)
            adapter.backfill_licencias(Path(temp) / 'licenses.jsonl')
            self.assertEqual((Path(temp) / 'licenses.jsonl').read_text(), '')

    def test_network_failure_keeps_existing_output(self):
        with TemporaryDirectory() as temp, patch('municipio.adapters.benacazon.requests.Session') as session:
            client = session.return_value.__enter__.return_value
            client.get.side_effect = requests.HTTPError('unavailable')
            output = Path(temp) / 'projects.jsonl'
            output.write_text('previous snapshot')
            with self.assertRaises(requests.HTTPError):
                BenacazonAyuntamientoAdapter('benacazon').backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')

    def test_ignored_pagination_fails(self):
        with TemporaryDirectory() as temp, patch('municipio.adapters.benacazon.requests.Session') as session:
            client = session.return_value.__enter__.return_value
            client.get.side_effect = lambda url, **kw: Mock(url=url, text=page(extra=pagination(1)))
            with self.assertRaisesRegex(ValueError, 'not served'):
                BenacazonAyuntamientoAdapter('benacazon').backfill_proyectos(Path(temp) / 'out.jsonl')

    def test_manifest(self):
        manifest = load_manifest('benacazon')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('41015', 'Benacazón', 'Sevilla'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.benacazon:BenacazonAyuntamientoAdapter')


if __name__ == '__main__':
    main()
