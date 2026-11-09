import tempfile
import unittest
from pathlib import Path

from municipio.adapters.esporles import (
    EsporlesAyuntamientoAdapter, ROOT_TYPES, SOURCE, STUDY, parse_page,
)
from municipio.manifest import load_manifest, load_yaml


def html(title, folders=(), entries=(), docs=(), body='', pager=''):
    def anchors(items):
        return ''.join(f'<a href="{url}">{name}</a>' for name, url in items)
    return (
        '<div class="region-content"><h1>' + title + '</h1>'
        '<div class="view-children-terms">' + anchors(folders) + '</div>'
        + ''.join(f'<article><h2>{anchors([entry])}</h2></article>' for entry in entries)
        + '<div class="field--name-field-attached-files">' + anchors(docs) + '</div>'
        + '<div class="field--name-description">' + body + '</div>' + pager + '</div>'
    )


class EsporlesTests(unittest.TestCase):
    def inventory(self):
        urls = {name: f'https://esporles.cat/ca/root-{i}' for i, name in enumerate(ROOT_TYPES)}
        docs = [('Memòria', '/sites/cilma_esporles/files/memoria.pdf')]
        pages = {
            SOURCE: html('Urbanisme', [('Normativa', '/ca/normativa'), (STUDY, '/ca/llum')],
                         [('Sol·licitud llicència', '/ca/form'), ('Notícia', '/ca/news')]),
            'https://esporles.cat/ca/normativa': html('Normativa', list(urls.items())),
            'https://esporles.cat/ca/llum': html(STUDY, entries=[(STUDY, '/ca/detail')]),
            'https://esporles.cat/ca/detail': html(STUDY, docs=docs * 2),
        }
        for name, url in urls.items():
            pages[url] = html(name, docs=docs)
        return pages, urls

    def test_bundles_pagination_modifications_dates_and_exclusions(self):
        pages, urls = self.inventory()
        base = urls['Normes Subsidiàries']
        pages[base] = html('Normes Subsidiàries', folders=[('Escrita', '/ca/escrita')],
            body='NS aprovades definitivament per la Comissió el 23/11/2001 (BOIB 22/12/2001).',
            pager='<nav class="pager"><a href="?page=1">2</a></nav>')
        pages[base + '?page=1'] = html('Normes Subsidiàries',
            entries=[('Modificació límits UA4, març 2015', '/ca/ua4')],
            pager=f'<nav class="pager"><a href="{base}">Anterior</a></nav>')
        pages['https://esporles.cat/ca/escrita'] = html('Escrita',
            docs=[('Normes', '/sites/cilma_esporles/files/ns.pdf')])
        pages['https://esporles.cat/ca/ua4'] = html('Modificació límits UA4, març 2015',
            docs=[('Acord', '/sites/cilma_esporles/files/20150301.pdf')])
        calls = []
        def fetch(url):
            calls.append(url)
            return pages[url]
        adapter = EsporlesAyuntamientoAdapter('esporles')
        rows = adapter.extract(fetch)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(calls), len(set(calls)))
        ns = next(r for r in rows if r['tipo'] == 'normas_subsidiarias')
        self.assertEqual(ns['fecha_aprob'], '2001-11-23')
        self.assertEqual(ns['fecha_publicacion'], '2001-12-22')
        self.assertEqual(ns['fecha_acuerdo'], None)
        self.assertEqual(len(ns['documentos']), 1)
        modification = next(r for r in rows if r['tipo'] == 'modificacion_planeamiento')
        self.assertEqual(modification['instrumento_padre_url'], base)
        self.assertIsNone(modification['fecha_aprob'])
        self.assertIsNone(modification['fecha_publicacion'])
        study = next(r for r in rows if r['tipo'] == 'estudio_detalle')
        self.assertEqual(len(study['documentos']), 1)
        self.assertEqual(study['documentos'][0]['fuentes'], ['https://esporles.cat/ca/detail'])
        self.assertTrue(all(r['lat'] is None and not r['publication_ready'] for r in rows))
        self.assertFalse(any('/ca/form' in c or '/ca/news' in c for c in calls))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in adapter.extract(pages.__getitem__)])

    def test_ptim_date_is_not_adaptation_approval(self):
        pages, urls = self.inventory()
        url = urls['Adaptació de les Normes Subsidiàries al Pla Territorial']
        pages[url] = html('Adaptació', docs=[('Normes', '/sites/cilma_esporles/files/n.pdf')],
            body='El 13/12/2004 es va aprovar definitivament el PTIM. Adaptació inicial abril 2011.')
        row = next(r for r in EsporlesAyuntamientoAdapter('esporles').extract(pages.__getitem__)
                   if r['tipo'] == 'adaptacion_planeamiento')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fase'])

    def test_source_changes_and_missing_documents_fail(self):
        with self.assertRaises(ValueError):
            parse_page('<h1>Access denied</h1>', SOURCE)
        with self.assertRaises(ValueError):
            parse_page(html('X', pager='<nav class="pager">More</nav>'), SOURCE)
        with self.assertRaises(ValueError):
            parse_page(html('X', folders=[('X', 'https://example.org/')]), SOURCE)
        pages, urls = self.inventory()
        pages[urls['Normes Subsidiàries']] = html('NS')
        with self.assertRaisesRegex(ValueError, 'no source documents'):
            EsporlesAyuntamientoAdapter('esporles').extract(pages.__getitem__)
        pages, _ = self.inventory()
        pages['https://esporles.cat/ca/normativa'] = html('Normativa', [('New', '/ca/new')])
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            EsporlesAyuntamientoAdapter('esporles').extract(pages.__getitem__)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('esporles')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '07020')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = EsporlesAyuntamientoAdapter('esporles').backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
