import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from municipio.adapters.sanlucar_la_mayor import (
    DOC_PATH, SOURCE, SanlucarLaMayorAyuntamientoAdapter, group_documents,
    page_url, parse_page,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def fixture(titles, current=1, total=1):
    links = ''.join(f'<tr><td><a href="{DOC_PATH}{i}.pdf">{title}</a></td></tr>'
                    for i, title in enumerate(titles))
    pager = ''.join(f'<a class="{"currentpagelink" if n == current else "pagelink"}" '
                    f'numpag="{n}" href="{page_url(n)}#galleryfiles-1-1">{n}</a>'
                    for n in range(1, total + 1))
    return f'<table class="table"><thead><tr><th>Fichero</th></tr></thead><tbody>{links}</tbody></table>{pager}'


class ParserTests(unittest.TestCase):
    def test_grouping_and_exclusions(self):
        titles = ['14.Innv nº5_Cementerio', '15.Innv nº5_Cementerio EsIA',
                  '17.Innv nº7_ResumenEjecutivo', '18.Innv nº7_Memoria',
                  '01.PGOU_LOUA Memoria', '06.PGOU_LOUA Plano IN.S.01',
                  '00.00.NNSS 1982', '00.01.PERI Encinares de Sanlúcar',
                  '00.02.MP Ranchos del Guadiamar', '00.03.PP15-La Marquesa',
                  'PGOM_Fase1-PT_y_PPC_29-04-2024',
                  '00.ORDENANZA MUNICIPAL DE EDIFICACIONES EN SUELO URBANO',
                  '00.ZONIFICACION ACUSTICA', '00.00.DETERMINACIONES SUELO URBANO']
        docs, _ = parse_page(fixture(titles), page_url(1))
        rows = group_documents(docs + docs)
        self.assertEqual(len(rows), 8)
        by_id = {r['id'].split('-plan-')[1]: r for r in rows}
        self.assertEqual(len(by_id['innovacion-5']['documentos']), 2)
        self.assertEqual(len(by_id['innovacion-7']['documentos']), 2)
        self.assertEqual(len(by_id['pgou-loua']['documentos']), 2)
        self.assertIn('Cementerio', by_id['innovacion-5']['documentos'][0]['titulo'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '41087')
            self.assertEqual(row['provincia'], 'Sevilla')
            self.assertFalse(row['publication_ready'])
            self.assertFalse({'fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion',
                              'lat', 'lon', 'fase'} & row.keys())

    def test_pagination_and_ignored_query(self):
        _, pages = parse_page(fixture(['00.00.NNSS 1982'], 1, 4), page_url(1))
        self.assertEqual(pages, {1, 2, 3, 4})
        with self.assertRaises(ValueError):
            parse_page(fixture(['00.00.NNSS 1982'], 1, 4), page_url(2))

    def test_reject_changed_empty_or_untrusted_inventory(self):
        for html in ('<html>Access denied</html>', fixture([]),
                     fixture(['01.PGOU_LOUA Memoria']).replace(DOC_PATH, 'https://example.org/')):
            with self.assertRaises(ValueError):
                parse_page(html, page_url(1))
        with self.assertRaises(ValueError):
            group_documents([{'titulo': 'Anuncio de licitación', 'url': SOURCE}])

    def test_backfill_follows_new_pages_and_preserves_output_on_failure(self):
        class Response:
            encoding = 'utf-8'
            def __init__(self, url):
                self.url = url
                n = int(url.rsplit('=', 1)[1])
                self.text = fixture(['01.PGOU_LOUA Memoria'] if n == 1 else
                                    ['14.Innv nº5_Cementerio'], n, 2)
                self.text = self.text.replace('IND-50-/0.pdf', f'IND-50-/{n}.pdf')
            def raise_for_status(self): pass
        with tempfile.TemporaryDirectory() as tmp, patch('requests.Session.get', side_effect=lambda u, **kw: Response(u)) as get:
            out = Path(tmp) / 'records.jsonl'
            adapter = SanlucarLaMayorAyuntamientoAdapter('sanlucar-la-mayor')
            result = adapter.backfill_proyectos(out)
            self.assertEqual(get.call_count, 2)
            self.assertEqual(result['count'], 2)
            original = out.read_text()
            with patch('requests.Session.get', side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError): adapter.backfill_proyectos(out)
            self.assertEqual(original, out.read_text())
            self.assertEqual(len([json.loads(x) for x in original.splitlines()]), 2)

    def test_manifest_adapter_and_disabled_licences(self):
        manifest = load_manifest('sanlucar-la-mayor')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, SanlucarLaMayorAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(out)['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
