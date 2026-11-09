import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.numancia_de_la_sagra import (
    BASE, SOURCE, NumanciaDeLaSagraAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def column(label, href):
    return f'<div class="elementor-column"><p>{label}</p><a href="{href}"></a></div>'


def page(body):
    return '<main><div class="entry-content">' + body + '</div></main>'


def section(body):
    return '<section class="elementor-top-section">' + body + '</section>'


INVENTORY = page(
    section('<p>Modificación puntual N12 NNSS</p>' + ''.join(
        column(f'Tomo {i}', f'/wp-content/uploads/2022/12/mp12-{i}.pdf') for i in range(4)))
    + section(column('Modificación plan parcial S-7', '/Modificacion_Plan_Parcial')
              + column('Modificación proyecto urbanización', '/Modificacion_Proyecto')
              + column('Propuesta de convenio y posición júridico económica S-7', '/convenio.pdf'))
    + section('<p>Modificación Plan parcial y proyecto reparcelación sector 8</p>')
    + section(column('Propuesta Estatutos Pol. La Sagra', '/estatutos.pdf'))
)
DETAIL = page(column('Memoria', '/memoria.pdf') + column('Plano', '/plano.pdf')
              + column('Plano duplicado', '/plano.pdf'))


class ParserTests(unittest.TestCase):
    def test_document_grouping_and_provenance(self):
        drafts = Adapter.parse_inventory(INVENTORY)
        self.assertEqual(len(drafts), 3)
        self.assertEqual(len(drafts[0][4]), 4)
        docs = Adapter.parse_detail(DETAIL, BASE + '/Modificacion_Proyecto')
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]['url_origen'], BASE + '/Modificacion_Proyecto')
        self.assertEqual(docs[0]['titulo'], 'Memoria')

    def test_missing_documents_and_changed_inventory_fail(self):
        for html in ('<html>error</html>', INVENTORY.replace('mp12-0.pdf', 'missing'),
                     INVENTORY.replace('Modificación plan parcial S-7', 'Nuevo proyecto S-8')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        with self.assertRaises(ValueError):
            Adapter.parse_detail(page('<h1>Sin documentos</h1>'), SOURCE)

    def test_pagination_and_external_documents_fail(self):
        for extra in ('<a href="?page=2" rel="next">2</a>',
                      '<a href="?page=2">Siguiente</a>', '<div class="page-numbers">2</div>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Adapter.parse_inventory(INVENTORY.replace('</main>', extra + '</main>'))
        with self.assertRaises(ValueError):
            Adapter.parse_detail(page(column('Memoria', 'https://example.org/m.pdf')), SOURCE)

    def test_adapter_snapshot_no_fabricated_dates_or_extra_records(self):
        class Response:
            status_code = 200
            headers = {'Content-Type': 'text/html; charset=UTF-8'}

            def __init__(self, url):
                self.url = url
                self.text = INVENTORY if url == SOURCE else DETAIL
                self.content = self.text.encode()

            def raise_for_status(self):
                pass

        with tempfile.TemporaryDirectory() as directory, patch(
            'municipio.adapters.numancia_de_la_sagra.requests.Session.get',
            side_effect=lambda url, **kwargs: Response(url),
        ) as get:
            path = Path(directory) / 'proyectos.jsonl'
            adapter = Adapter('numancia-de-la-sagra')
            result = adapter.update_proyectos(path, Path(directory) / 'unused-state.json')
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['rows'], 3)
            self.assertEqual(get.call_count, 3)
            self.assertEqual(len(rows[1]['documentos']), 3)
            self.assertEqual(len({r['id'] for r in rows}), 3)
            for row in rows:
                for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
                    self.assertIsNone(row[key])
            licence = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(licence)['status'], 'disabled')
            self.assertEqual(licence.read_text(), '')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('numancia-de-la-sagra')
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        self.assertEqual(manifest.provincia, 'Toledo')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
