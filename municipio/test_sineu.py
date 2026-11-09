"""Offline parser/adapter regressions using representative municipal markup."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sineu import (
    EXCLUDED, GROUPS, PREFIX, SOURCE, SineuAyuntamientoAdapter,
    group_records, parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest


def inventory(keys=None):
    keys = list(GROUPS) + list(EXCLUDED) if keys is None else keys
    cards = ''.join(f'<a href="{PREFIX}{k}"><h3>{k}</h3><p>1 document</p></a>' for k in keys)
    return f'<main><h1>Urbanisme</h1><div class="taxonomy-term-files">{cards}</div></main>'


def detail(entry, date='08/09/2020'):
    return (f'<main><h1>{entry["titulo"]}</h1><article class="node-file-or-document">'
            f'<div><h3>{entry["titulo"]}</h3><span>PDF · 85 KB · {date}</span>'
            f'<a download href="/sites/cilma_sineu/files/2020-09/{entry["key"]}.pdf">Descarregar</a>'
            '</div></article></main>')


class SineuTests(unittest.TestCase):
    def test_grouped_instruments_not_files_or_procedures(self):
        entries = parse_inventory(inventory())
        docs = {e['key']: parse_documents(detail(e), e) for e in entries if e['key'] in GROUPS}
        rows = group_records(entries, docs)
        self.assertEqual(len(rows), 3)
        ari = next(r for r in rows if r['id'] == 'sineu-proy-ari')
        self.assertEqual(len(ari['documentos']), 2)
        self.assertTrue(ari['url'].split('/')[-1].startswith('programa-'))
        self.assertEqual(len(ari['source_pages']), 2)
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in group_records(list(reversed(entries)), docs)])
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['geometry'])
            self.assertIsNone(row['lat'])
            self.assertEqual(row['codigo_ine'], '07060')

    def test_file_date_keeps_own_semantics(self):
        e = parse_inventory(inventory())[0]
        d = parse_documents(detail(e), e)[0]
        self.assertEqual(d['fecha_fichero_portal'], '2020-09-08')
        self.assertIsNone(d['fecha_publicacion'])
        self.assertIsNone(d['fecha_acuerdo'])
        self.assertIsNone(parse_documents(detail(e, ''), e)[0]['fecha_fichero_portal'])

    def test_pagination_fails_visibly(self):
        for pager in ['<nav class="pager"></nav>', '<a href="?page=1">2</a>', '<a rel="next" href="/more">More</a>']:
            with self.subTest(pager=pager), self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(inventory().replace('</main>', pager + '</main>'))

    def test_unknown_entries_and_empty_or_login_fail(self):
        for html in [inventory(['new-project']), inventory([]), '<main><h1>Login</h1></main>', '<a href="/plan">Plan</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_missing_attachments_and_wrong_detail_fail(self):
        e = parse_inventory(inventory())[0]
        for html in [detail(e).replace(' download ', ' '), detail(e).replace(e['titulo'], 'Login'), '<main><h1>Login</h1></main>']:
            with self.assertRaises(ValueError):
                parse_documents(html, e)
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            parse_documents(detail(e), {**e, 'document_count': 2})
        with self.assertRaises(ValueError):
            parse_documents(detail(e).replace('/sites/cilma_sineu/', 'https://unrelated.example/'), e)

    def test_snapshot_and_failed_refresh_preserves_output(self):
        adapter = SineuAyuntamientoAdapter()
        entries = parse_inventory(inventory())
        payloads = {SOURCE: inventory().encode()}
        for e in entries:
            if e['key'] in GROUPS:
                payloads[e['url']] = detail(e).encode()
                doc = parse_documents(detail(e), e)[0]
                payloads[doc['url']] = b'%PDF-1.4 test source'
        with tempfile.TemporaryDirectory() as td, patch.object(adapter, '_fetch', side_effect=lambda u, **kw: payloads[u]):
            output = Path(td) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(td) / 'state.json')
            self.assertEqual(result['rows'], 3)
            self.assertEqual(len(result['excluded_entries']), 1)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertTrue(all(len(d['sha256']) == 64 for r in rows for d in r['documentos']))
            original = output.read_bytes()
            payloads[SOURCE] = inventory(['unknown']).encode()
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), original)

    def test_manifest_and_disabled_licences(self):
        m = load_manifest('sineu')
        self.assertEqual((m.nombre, m.provincia), ('Sineu', 'Illes Balears'))
        self.assertFalse(m.licencias.enabled)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'licencias.jsonl'
            self.assertEqual(SineuAyuntamientoAdapter().backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
