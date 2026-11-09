"""Offline parser and traversal checks; no network needed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.casabermeja import (
    ROOT, CasabermejaAyuntamientoAdapter, group_instruments,
    parse_documents, parse_inventory,
)


def inventory(number='30', detail='1', page=1, pages=1, municipality='CASABERMEJA'):
    headings = ['Órgano Tramitador', 'Actuación', 'Provincia', 'Otras Provincias', 'Municipio',
                'Otros Municipios', 'Tipo de Resolución', 'Fecha de Resolución', 'Número de Expediente', 'Documentos']
    cells = ['Junta de Andalucía', 'PLAN PARCIAL DE ORDENACIÓN DEL SECTOR PP-8', 'MÁLAGA', '',
             municipality, '', 'Documento de Alcance', '29/11/2024', f'(EA/MA/{number}/22)',
             f'<a href="/medioambiente/daepu/resolucions/{detail};jsessionid=ABC">Detalle</a>']
    return ('<table><tr>' + ''.join(f'<th>{h}</th>' for h in headings) + '</tr><tr>' +
            ''.join(f'<td>{c}</td>' for c in cells) + '</tr></table>' + f'Página {page} de {pages}')


def document(number='30', municipality='CASABERMEJA'):
    fields = {'Municipio:': municipality, 'Provincia:': 'MÁLAGA',
              'Número de Expediente:': f'EA/MA/{number}/22', 'Fecha de Resolución:': '29/11/2024'}
    return (''.join(f'<div><label>{k}</label><div class="box">{v}</div></div>' for k, v in fields.items()) +
            '<table><tr><td>Documento de Alcance (DA)</td><td>29/11/2024</td>'
            '<td><a href="downloadFile/abc">Documento</a></td></tr></table>')


class CasabermejaTests(unittest.TestCase):
    def test_group_documents_and_date_semantics(self):
        rows, page, pages = parse_inventory(inventory(), ROOT)
        self.assertEqual((page, pages), (1, 1))
        first = rows[0]
        first['documentos'] = parse_documents(document(), first['url'], first)
        second = {**first, 'url': ROOT + 'resolucions/2', 'fecha_resolucion': '2023-02-22',
                  'documentos': [{**first['documentos'][0], 'url': ROOT + 'resolucions/downloadFile/def'}]}
        grouped = group_instruments([first, second, first])
        self.assertEqual(len(grouped), 1)
        self.assertEqual(len(grouped[0]['documentos']), 2)
        self.assertEqual(len(grouped[0]['resoluciones']), 2)
        self.assertEqual(grouped[0]['expediente_ambiental'], 'EA/MA/30/22')
        self.assertEqual(first['fecha_resolucion'], '2024-11-29')
        self.assertNotIn('jsessionid', first['url'])
        for field in ('fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(grouped[0][field])
        self.assertNotIn('fase', grouped[0])

    def test_boja_table_date_is_not_publication_or_agreement(self):
        first = parse_inventory(inventory(), ROOT)[0][0]
        html = document().replace('Documento de Alcance (DA)', 'Publicación en BOJA (PB)')
        doc = parse_documents(html, first['url'], first)[0]
        self.assertEqual(doc['fecha_fuente'], '2024-11-29')
        self.assertEqual(doc['campo_fecha_fuente'], 'Fecha de Resolución')
        self.assertIsNone(doc['fecha_resolucion'])
        self.assertNotIn('fecha_publicacion', doc)
        self.assertNotIn('fecha_acuerdo', doc)

    def test_reject_changed_or_wrong_sources(self):
        for html in ('<html>blocked</html>', inventory(municipality='MÁLAGA'),
                     inventory().replace('29/11/2024', '31/11/2024'),
                     inventory().replace('PLAN PARCIAL DE ORDENACIÓN DEL SECTOR PP-8', 'Solicitud de licencia')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, ROOT)
        first = parse_inventory(inventory(), ROOT)[0][0]
        for html in (document(municipality='MÁLAGA'), document(number='31'),
                     document().replace('<a href="downloadFile/abc">Documento</a>', '')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_documents(html, first['url'], first)

    def test_traverses_every_page_and_groups_same_instrument(self):
        class Response:
            status_code = 200
            def __init__(self, url, html):
                self.url, self.content = url, html.encode()
            def raise_for_status(self):
                pass
        visited = []
        def get(session, url, **kwargs):
            visited.append(url)
            if '/find?' in url:
                page = 2 if 'page=2' in url else 1
                return Response(url, inventory(detail=str(page), page=page, pages=2))
            return Response(url, document())
        adapter = CasabermejaAyuntamientoAdapter('casabermeja')
        with tempfile.TemporaryDirectory() as directory, patch('requests.Session.get', get):
            output = Path(directory) / 'projects.jsonl'
            result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['pages'], 2)
            self.assertEqual(result['resolutions'], 2)
            self.assertEqual(len(json.loads(output.read_text())['resoluciones']), 2)
            self.assertTrue(any('page=2' in u for u in visited))
            adapter.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')

    def test_repeated_page_fails_without_overwriting_output(self):
        class Response:
            status_code = 200
            def __init__(self, url, html):
                self.url, self.content = url, html.encode()
            def raise_for_status(self):
                pass
        def get(session, url, **kwargs):
            return Response(url, inventory(pages=2) if '/find?' in url else document())
        with tempfile.TemporaryDirectory() as directory, patch('requests.Session.get', get):
            output = Path(directory) / 'projects.jsonl'
            output.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                CasabermejaAyuntamientoAdapter('casabermeja').backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
