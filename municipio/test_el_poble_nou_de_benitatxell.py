"""Offline parser regressions; live evidence is deliberately not a test fixture."""
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from municipio.adapters.el_poble_nou_de_benitatxell import (
    SOURCE, ElPobleNouDeBenitatxellAdapter, parse_inventory, parse_records,
)


def inventory():
    nav = json.dumps({'enabled': False, 'query': {'posts_per_page': -1}})
    titles = ['OE-01. Classificació del sòl', 'OP-01. Urbanització Racó de Nadal',
              '1.1-Document de síntesi_Benitachell-V05',
              '1.2-NN-UU-Text-Consolidat_Benitatxell-V05',
              '1.3 — Criteri interpretatiu Cumbre del Sol']
    links = ''.join(f'<div class="jet-listing-grid__item"><a href="/wp-content/uploads/2025/12/{i}.pdf">{t}</a></div>'
                    for i, t in enumerate(titles))
    return f"<div class='jet-listing-grid__items' data-nav='{nav}'>{links}</div>"


CERT = '''CERTIFICADO EXPEDIENTE Nº ÓRGANO COLEGIADO FECHA DE LA SESIÓN
1237/2024 El Pleno 13/05/2024
CRITERIO INTERPRETATIVO OLIVOS PUEBLO DEL MAR Fecha Firma: 09/05/2024'''


class ParserTests(unittest.TestCase):
    def test_grouping_dedup_and_exclusions(self):
        html = inventory()
        html += '<a href="/form.pdf">Solicitud de licencia de obra</a>'
        docs = parse_inventory(html + html)
        self.assertEqual([len(docs[k]) for k in ('normas', 'criterio')], [4, 1])
        rows = parse_records(docs, 'NORMAS SUBSIDIARIAS', 'NORMAS SUBSIDIARIAS', CERT)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['fecha_acuerdo'], '2024-05-13')
        self.assertEqual(rows[1]['expediente'], '1237/2024')
        self.assertEqual(rows[0]['url'], SOURCE)
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['lat'])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '03042')

    def test_pagination_fails_closed(self):
        for html in (inventory().replace('"enabled": false', '"enabled": true'),
                     inventory().replace('"posts_per_page": -1', '"posts_per_page": 10')):
            with self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(html)

    def test_missing_documents_and_foreign_links_fail(self):
        for html in ('<a>Solicitud de licencia</a>', inventory().replace('1.2-NN', 'Otra-NN'),
                     inventory().replace('/wp-content/uploads/', 'https://example.org/')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pdf_verification_and_date_semantics(self):
        docs = parse_inventory(inventory())
        for text in (CERT.replace('13/05/2024', '31/02/2024'),
                     CERT.replace('FECHA DE LA SESIÓN', 'Fecha Firma')):
            with self.assertRaises(ValueError):
                parse_records(docs, 'NORMAS SUBSIDIARIAS', 'NORMAS SUBSIDIARIAS', text)
        with self.assertRaises(ValueError):
            parse_records(docs, 'Solicitud', 'NORMAS SUBSIDIARIAS', CERT)
        changed = parse_records(docs, 'NORMAS SUBSIDIARIAS', 'NORMAS SUBSIDIARIAS', CERT.replace('13/05/2024', '14/05/2024'))
        self.assertEqual(changed[1]['fecha_acuerdo'], '2024-05-14')

    def test_failed_refresh_preserves_previous_output(self):
        adapter = ElPobleNouDeBenitatxellAdapter('el-poble-nou-de-benitatxell')
        with TemporaryDirectory() as d:
            out = Path(d) / 'proyectos.jsonl'
            out.write_text('previous\n')
            with patch.object(adapter, '_fetch', return_value=b'<html>error</html>'):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(out, Path(d) / 'state.json')
            self.assertEqual(out.read_text(), 'previous\n')
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
