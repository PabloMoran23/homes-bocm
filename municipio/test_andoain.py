"""Offline parser and failure-atomicity tests; no network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.andoain import (
    SOURCE, AndoainAyuntamientoAdapter, parse_documents, parse_inventory, parse_notice,
)

ROW = '''<tr><th><a href="/es/plan-1">Estudio de Detalle AIU-1</a></th>
<th>Exposición pública</th><th>18-03-2026</th>
<th><a href="/documents/131314/1/notice.pdf">BOG 48</a></th></tr>'''


def inventory(rows=ROW):
    return '''<div data-analytics-asset-id="544727"><h1>Planes en exposición pública</h1>
<table class="cebra"><thead><tr><td>Nombre</td><td>Estado</td>
<td>Fecha de acuerdo</td><td>BOG</td></tr>''' + rows + '</thead></table></div>'


DETAIL = '''<div class="journal-content-article"><h1>Estudio de Detalle AIU-1</h1>
<ul class="destacado"><li><a href="/documents/131314/1/notice.pdf">Anuncio</a></li>
<li><a href="/documents/131314/1/plan.pdf">Memoria y planos</a></li>
<li><a href="/documents/131314/1/plan.pdf?t=5">Memoria y planos</a></li></ul></div>
<footer><a href="/documents/131314/2/privacy.pdf">Aviso legal</a></footer>'''
NOTICE = '''AYUNTAMIENTO DE ANDOAIN
Estudio de Detalle AIU-1
Mediante Resolución de Alcaldía n.º 407 de fecha 17 de fe-
brero de 2026, ha sido aprobado, con carácter inicial y con las condiciones.
Andoain, a 20 de febrero de 2026.
Jueves, a 12 de marzo de 2026'''


class AndoainParserTests(unittest.TestCase):
    def test_grouping_source_dates_and_stable_ids(self):
        rows = parse_inventory(inventory(ROW + ROW))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['fecha_inventario'], '2026-03-18')
        self.assertIsNone(rows[0]['fecha'])
        self.assertNotIn('fecha_acuerdo', rows[0])
        changed = ROW.replace('Estudio de Detalle AIU-1', 'Estudio de Detalle AIU-1 revisado')
        self.assertEqual(rows[0]['id'], parse_inventory(inventory(changed))[0]['id'])
        docs = parse_documents(DETAIL, rows[0]['url'])
        self.assertEqual(len(docs), 2)
        self.assertFalse(any('privacy' in doc['url'] for doc in docs))

    def test_notice_dates_are_distinct_from_signature_and_inventory(self):
        parsed = parse_notice(NOTICE)
        self.assertEqual(parsed['fecha_acuerdo'], '2026-02-17')
        self.assertEqual(parsed['fecha_publicacion'], '2026-03-12')
        self.assertEqual(parsed['numero_resolucion'], '407')
        self.assertEqual(parsed['fase'], 'aprobación inicial')
        with self.assertRaises(ValueError):
            parse_notice(NOTICE.replace('Mediante Resolución', 'Otra resolución'))

    def test_rejects_truncation_missing_and_unsupported_content(self):
        for html in [inventory(''), '<html>login</html>',
                     inventory() + '<a rel="next" href="?page=2">2</a>',
                     inventory() + '<ul class="pagination"><li><a href="?page=2">2</a></li></ul>',
                     inventory(ROW.replace('Estudio de Detalle', 'Formulario de licencia')),
                     inventory(ROW.replace('/es/plan-1', 'https://example.org/plan-1')),
                     inventory(ROW + ROW.replace('18-03-2026', '19-03-2026'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_documents(DETAIL.replace('Memoria y planos', 'Anuncio'), SOURCE)

    def test_failed_refresh_preserves_previous_output_and_disabled_licences(self):
        adapter = AndoainAyuntamientoAdapter('andoain')
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'proyectos.jsonl'
            output.write_text('{"previous": true}\n')
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), b'<html>bad detail</html>']):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(output, Path(temp) / 'state.json')
            self.assertEqual(json.loads(output.read_text()), {'previous': True})
            with patch.object(adapter, '_fetch', side_effect=AssertionError('licences must not fetch')):
                self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
