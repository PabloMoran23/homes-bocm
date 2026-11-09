import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from municipio.adapters.siguenza import (
    SOURCE, SiguenzaAyuntamientoAdapter, parse_documents, parse_inventory,
)

PECH = 'INFORMACIÓN PÚBLICA: DOCUMENTO PARA APROBACION INICIAL DEL PLAN ESPECIAL DE REHABILITACIÓN DEL CASCO HISTÓRICO'
LANDSCAPE = 'BORRADOR PARA CONSULTA PREVIA DEL PLAN ESPECIAL DEL PAISAJE DEL MUNICIPIO DE SIGÜENZA'


def page(body):
    return '<main><div class="entry-content"><h2>URBANISMO</h2>' + body + '</div></main>'


def inventory():
    return page(f'<a href="/pagina/8/87/">{PECH}</a>'
                f'<a href="/pagina/8/88/">{LANDSCAPE}</a>')


def response(url, html, status=200):
    result = requests.Response()
    result.status_code, result.url = status, url
    result._content = html.encode()
    result.encoding = 'utf-8'
    return result


class SiguenzaTests(unittest.TestCase):
    def test_two_real_instruments_and_semantics(self):
        rows = parse_inventory(inventory())
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '19257')
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertNotIn('fase', row)
            self.assertNotIn('lat', row)
            self.assertFalse(row['publication_ready'])

    def test_noise_excluded_and_empty_rejected(self):
        noise = '<a href="/form.pdf">Solicitud de licencia de obras</a>' \
                '<a href="/licitacion">Licitación de obras</a>' \
                '<a href="/noticia">Fiestas de Sigüenza</a><p>Plan de Peatonalización</p>'
        self.assertEqual(len(parse_inventory(inventory().replace('</div>', noise + '</div>'))), 2)
        with self.assertRaises(ValueError):
            parse_inventory(page(noise))

    def test_grouping_and_parent_document_provenance(self):
        html = inventory().replace('</div>', f'<a href="/otra-ficha/">{PECH}</a></div>')
        self.assertEqual(len(parse_inventory(html)[0]['documents']), 2)
        docs = parse_documents(page('<a href="/normas.pdf">Normas</a>'
                                    '<a href="/normas.pdf">duplicado</a>'
                                    '<a href="/planos.zip">Planos</a>'), 'https://siguenza.es/ficha/')
        self.assertEqual(len(docs), 2)
        self.assertTrue(all(d['inventory_url'].endswith('/ficha/') for d in docs))

    def test_fail_closed_on_changed_markup_pagination_or_external_link(self):
        for html in [inventory() + '<a rel="next" href="?page=2">2</a>',
                     inventory().replace('entry-content', 'removed'),
                     inventory().replace('/pagina/8/87/', 'https://example.org/plan')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_live_path_reports_broken_details_without_claiming_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = SiguenzaAyuntamientoAdapter()
            with patch.object(adapter, '_get', side_effect=lambda url: response(
                    url, inventory() if url == SOURCE else 'Not Found',
                    200 if url == SOURCE else 404)):
                target = Path(tmp) / 'projects.jsonl'
                report = adapter.backfill_proyectos(target)
            rows = [json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual(report['count'], 2)
            self.assertTrue(all(r['documents'][0]['http_status'] == 404 for r in rows))
            self.assertEqual(len(report['source_urls']), 3)

    def test_attachments_stay_with_their_instrument(self):
        def fetch(url):
            body = inventory() if url == SOURCE else page(
                '<a href="/casco.pdf">Casco</a>' if '/87/' in url else
                '<a href="/paisaje.pdf">Paisaje</a>')
            return response(url, body)
        with tempfile.TemporaryDirectory() as tmp:
            adapter = SiguenzaAyuntamientoAdapter()
            with patch.object(adapter, '_get', side_effect=fetch):
                target = Path(tmp) / 'p.jsonl'
                adapter.backfill_proyectos(target)
            rows = [json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual(rows[0]['documents'][-1]['url'], 'https://siguenza.es/casco.pdf')
            self.assertEqual(rows[1]['documents'][-1]['url'], 'https://siguenza.es/paisaje.pdf')


if __name__ == '__main__':
    unittest.main()
