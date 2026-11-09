"""Offline parser and full pagination tests; no evidence files required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.villanueva_del_ariscal import (
    ARCHIVE, DOCUMENTS, GROUPS, HOST, PAGE_KEY, SOURCE,
    VillanuevaDelAriscalAyuntamientoAdapter, canonical_page,
    group_projects, parse_inventory_page,
)
from municipio.manifest import load_manifest, load_yaml


def fixture(files, page=1, pages=2):
    links = ''.join(f'<tr><td><a href="/export/sites/villanuevadelariscal/es/transparencia/.galleries/IND-61-/{f}">{f}</a></td></tr>' for f in files)
    pagination = ''.join(f'<a class="{"currentpagelink" if n == page else "pagelink"}" numpag="{n}" href="{SOURCE}?{PAGE_KEY}={n}#galleryfiles-1-1">{n}</a>' for n in range(1, pages + 1))
    return '<h1>Obras más importantes de infraestructura que están en curso</h1><table class="table"><tbody>' + links + '</tbody></table>' + pagination


def response(url, html):
    return Mock(url=url, text=html, status_code=200)


class VillanuevaDelAriscalTests(unittest.TestCase):
    def test_all_reviewed_documents_and_grouping(self):
        docs, excluded, pages = parse_inventory_page(fixture(list(DOCUMENTS) + [ARCHIVE]), SOURCE)
        rows = group_projects(docs + docs)
        self.assertEqual(len(rows), 11)
        self.assertEqual(sum(len(r['documentos']) for r in rows), 14)
        self.assertEqual(len(excluded), 1)
        self.assertIn('?'+PAGE_KEY+'=2', next(p for p in pages if p != SOURCE))
        by_id = {r['id']: r for r in rows}
        for key in ('supera-iv-piscina', 'supera-iv-accesos-ceip', 'supera-iv-alumbrado'):
            self.assertEqual(len(by_id['villanueva-del-ariscal-proy-' + key]['documentos']), 2)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '41098')
            self.assertEqual(row['provincia'], 'Sevilla')
            for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertNotIn('fase', row)
            self.assertFalse(row['publication_ready'])

    def test_programmes_and_interventions_stay_separate(self):
        docs, _, _ = parse_inventory_page(fixture(list(DOCUMENTS)), SOURCE)
        rows = group_projects(docs)
        viarios = [r for r in rows if 'viarios' in r['id']]
        self.assertEqual(len(viarios), 3)
        self.assertTrue(all(len(r['documentos']) == 1 for r in viarios))

    def test_fail_closed_on_forms_empty_changed_or_unknown_documents(self):
        for html in ('<h1>Licencias</h1>', fixture([]), fixture(['Solicitud-de-licencia.pdf']), fixture(['Proyecto-nuevo.pdf'])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory_page(html, SOURCE)
        with self.assertRaises(ValueError):
            parse_inventory_page(fixture(list(DOCUMENTS)).replace('/export/sites/', 'https://example.org/export/sites/'), SOURCE)

    def test_full_pagination_and_snapshot_update(self):
        files = list(DOCUMENTS)
        page2 = SOURCE + '?' + PAGE_KEY + '=2'
        payloads = {SOURCE: fixture(files[:8]), page2: fixture(files[8:] + [ARCHIVE], page=2)}
        session = Mock(headers={})
        session.get.side_effect = lambda url, **kwargs: response(url, payloads[url])
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.villanueva_del_ariscal.requests.Session', return_value=session):
            out = Path(tmp) / 'proyectos.jsonl'
            adapter = VillanuevaDelAriscalAyuntamientoAdapter('villanueva-del-ariscal')
            report = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows), 11)
            self.assertEqual(report['document_count'], 14)
            self.assertEqual(report['pages'], [SOURCE, page2])
            self.assertEqual(session.get.call_count, 2)
            self.assertFalse((Path(tmp) / 'state.json').exists())

    def test_broken_pagination_does_not_write_partial_output(self):
        files = list(DOCUMENTS)
        session = Mock(headers={})
        session.get.side_effect = lambda url, **kwargs: response(url, fixture(files[:8]))
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.villanueva_del_ariscal.requests.Session', return_value=session):
            out = Path(tmp) / 'projects.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                VillanuevaDelAriscalAyuntamientoAdapter('villanueva-del-ariscal').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_pagination_provenance(self):
        self.assertEqual(canonical_page(SOURCE.rstrip('/') + '?' + PAGE_KEY + '=1#gallery'), SOURCE)
        for url in (HOST + '/other', 'https://example.org/', SOURCE + '?unexpected=2', SOURCE + '?' + PAGE_KEY + '=0'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_page(url)

    def test_manifest_and_disabled_licences(self):
        path = Path('data/municipios/villanueva-del-ariscal/manifest.yaml')
        raw = load_yaml(path)
        manifest = load_manifest(path)
        self.assertEqual(raw['codigo_ine'], '41098')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.villanueva_del_ariscal:VillanuevaDelAriscalAyuntamientoAdapter')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            report = VillanuevaDelAriscalAyuntamientoAdapter(manifest.slug).backfill_licencias(out)
            self.assertTrue(report['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
