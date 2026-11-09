"""Offline semantic and traversal tests; live evidence is generated separately."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.esquivias import (
    SOURCE, EsquiviasAyuntamientoAdapter, municipality_filter, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

TITLE = 'PAU, PERI Y ANTEPROYECTO DEL P.16'
DETAIL = SOURCE.rsplit('/', 1)[0] + '/pau/p16'
FILTERED = SOURCE + '?municipio=1118'


def inventory(url=DETAIL, title=TITLE, municipality='Esquivias', pager=''):
    return f'''<table class="views-table"><thead><tr><th>Denominación</th>
    <th>Municipio</th><th>Fecha de constitución</th></tr></thead><tbody><tr>
    <td><a href="{url}">{title}</a></td><td>{municipality}</td><td>29/07/2021</td>
    </tr></tbody></table>{pager}'''


def detail(title=TITLE):
    return f'''<article class="node--type-programa-actuacion-urbanizadora"><h1>{title}</h1>
    <div class="field--name-municipios-clm"><ul><li>TOLEDO</li><li>Esquivias</li></ul></div>
    <div class="field--name-field-fecha-aprobacion"><time datetime="2021-07-29T12:00:00Z"></time></div>
    <div class="field--name-field-publicacion-docm"><time datetime="2021-10-04T12:00:00Z"></time></div>
    <a href="/sites/default/files/plan.pdf">Plan</a>
    <a href="/sites/default/files/plan.pdf">Duplicado</a>
    <a href="/sites/default/files/memoria.pdf">Memoria</a></article>'''


class Response:
    def __init__(self, url, html):
        self.url, self.html = url, html
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def raise_for_status(self):
        pass
    def iter_content(self, size):
        yield self.html.encode()


class EsquiviasTests(unittest.TestCase):
    def test_manifest_contract(self):
        manifest = load_manifest('esquivias')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('45064', 'Toledo'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), EsquiviasAyuntamientoAdapter)

    def test_dates_grouping_and_no_invention(self):
        row = parse_detail(detail(), DETAIL, TITLE)
        self.assertEqual(row['fecha_aprob'], '2021-07-29')
        self.assertEqual(row['fecha_publicacion'], '2021-10-04')
        self.assertEqual(len(row['documentos']), 3)  # One instrument, ficha + two PDFs.
        for key in ('lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)
        self.assertNotIn('fecha_acuerdo', row)
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['id'], parse_detail(detail(), DETAIL, TITLE)['id'])

    def test_missing_dates_not_borrowed(self):
        html = detail().replace('datetime=', 'data-old-date=')
        row = parse_detail(html, DETAIL, TITLE)
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_reject_wrong_municipality_title_and_navigation(self):
        for html in ('<a href="/licencias">Solicitud de licencia</a>',
                     detail().replace('Esquivias', 'Illescas'),
                     detail().replace('TOLEDO', 'MADRID'), detail('Otro PAU')):
            with self.assertRaises(ValueError):
                parse_detail(html, DETAIL, TITLE)
        for html in ('<p>No hay resultados</p>', inventory(municipality='Illescas'),
                     inventory(url='https://example.org/registros/pau/otro')):
            with self.assertRaises(ValueError):
                parse_inventory(html, FILTERED)

    def test_dynamic_filter_and_pagination_guard(self):
        self.assertEqual(municipality_filter('<select name="municipio"><option value="999">-Esquivias</option></select>'), '999')
        with self.assertRaises(ValueError):
            municipality_filter('<p>Esquivias</p>')
        with self.assertRaises(ValueError):
            parse_inventory(inventory(pager='<div class="pager"><a href="?page=1">Next</a></div>'), FILTERED)

    def test_live_path_traverses_pages_and_replaces_snapshot(self):
        page2 = FILTERED + '&page=1'
        other = DETAIL + '-otro'
        pages = {SOURCE: '<select name="municipio"><option value="1118">-Esquivias</option></select>',
                 FILTERED: inventory(pager=f'<div class="pager"><a href="{page2}">Next</a></div>'),
                 page2: inventory(other, 'PAU OTRO'), DETAIL: detail(), other: detail('PAU OTRO')}
        visited = []
        def get(session, url, **kwargs):
            visited.append(url)
            return Response(url, pages[url])
        with tempfile.TemporaryDirectory() as directory, patch('requests.Session.get', get):
            output = Path(directory) / 'proyectos.jsonl'
            adapter = EsquiviasAyuntamientoAdapter('esquivias')
            report = adapter.update_proyectos(output, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(report['live_records'], 2)
            self.assertEqual(len(rows), 2)
            self.assertIn(page2, visited)
            output.write_text('previous valid snapshot')
            pages[other] = '<p>Login</p>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous valid snapshot')


if __name__ == '__main__':
    unittest.main()
