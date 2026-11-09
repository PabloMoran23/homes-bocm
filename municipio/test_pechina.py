"""Offline parser/transport contract checks; no network or evidence dependency."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.pechina import (
    SOURCE, PechinaAyuntamientoAdapter, document_links, group_documents,
    parse_attachments, parse_detail,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

UID = 'B1995C861192B023C12577EA002D5464'
URL = SOURCE.replace('tablon_view', 'tablon') + '&documentId=' + UID
DETAIL = '''<div id="doc-dipalme-titulo"><h1>MEMORIA JUSTIFICATIVA. ADPATACION NN.SS. A LA LOUA</h1></div>
<h2>Ayuntamiento de Pechina</h2><p>Territorio - Planeamiento Urbanístico - A. MEMORIA</p>
Publicado: <strong>29/11/2010</strong>'''


class PechinaTests(unittest.TestCase):
    def test_identity_and_disabled_features(self):
        manifest = load_manifest('pechina')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('04074', 'Almería'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), PechinaAyuntamientoAdapter)

    def test_inventory_deduplicates_and_checks_municipality(self):
        link = f'<a href="{URL}">Memoria</a>'
        self.assertEqual(len(document_links(link * 2)), 1)
        self.assertEqual(document_links('<a href="/formulario.pdf">Licencia</a>'), {})
        with self.assertRaises(ValueError):
            document_links(link.replace('p=Pechina', 'p=huercal-overa'))

    def test_publication_is_not_agreement(self):
        doc = parse_detail(DETAIL, URL)
        self.assertEqual(doc['fecha_publicacion'], '2010-11-29')
        self.assertNotIn('fecha_acuerdo', doc)
        self.assertNotIn('fecha_aprob', doc)
        with self.assertRaises(ValueError):
            parse_detail(DETAIL.replace('<h2>Ayuntamiento de Pechina</h2>', '<h2>Ayuntamiento de Benahadux</h2>'), URL)

    def test_attachment_provenance(self):
        attachment = f'/Servicios/Tablon/Tablon.nsf/0/{UID}/$FILE/memoria.pdf'
        html = f'Ayuntamiento de Pechina <a href="{attachment}">Memoria</a><a href="/other.pdf">Otra</a>'
        self.assertEqual(len(parse_attachments(html, UID)), 1)
        with self.assertRaises(ValueError):
            parse_attachments('Ayuntamiento de Pechina <a href="/other.pdf">Otra</a>', UID)

    def test_grouping_retains_documents_without_inferred_dates_or_geometry(self):
        doc = parse_detail(DETAIL, URL)
        rows = group_documents([doc])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['documentos'], [doc])
        for field in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'fase']:
            self.assertNotIn(field, rows[0])
        with self.assertRaises(ValueError):
            group_documents([])
        with self.assertRaises(ValueError):
            group_documents([doc, {**doc, 'url': URL.replace(UID, '0' * 32)}])

    def test_next_page_is_followed(self):
        adapter = PechinaAyuntamientoAdapter('pechina')
        first = '<table id="view:_id6:viewPanel1"><tr><td>one</td></tr></table><a id="pager__Next__lnk">Siguiente</a>'
        last = '<table id="view:_id6:viewPanel1"><tr><td>two</td></tr></table>'
        with patch.object(adapter, '_post', return_value=last) as post:
            self.assertEqual(list(adapter._pages(None, first)), [first, last])
            post.assert_called_once_with(None, first, 'pager__Next')
        with patch.object(adapter, '_post', return_value=first):
            with self.assertRaises(ValueError):
                list(adapter._pages(None, first))

    def test_licences_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            result = PechinaAyuntamientoAdapter('pechina').backfill_licencias(path)
            self.assertTrue(result['disabled'])
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
