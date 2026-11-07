"""Offline parser and adapter contract tests; no live network required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.canet_de_mar import CanetDeMarAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(body):
    return '<h1>PLANEJAMENT URBANÍSTIC</h1><div id="cos"><p>Normativa aplicable i enllaços de consulta:</p>' + body + '</div>'


def item(name='Pla especial del catàleg de masies', doc='636228'):
    return (f'<p>- {name}, (DOGC núm. 6379 de data 21-05-2013)</p>'
            f'<p><a href="https://dogc.gencat.cat/ca/document-del-dogc/?documentId={doc}">EDICTE de 13 de maig de 2013</a></p>')


class ParserTests(unittest.TestCase):
    def test_dates_provenance_and_no_invented_geometry(self):
        row = Adapter.parse_projects(page(item()))[0]
        self.assertEqual(row['fecha_publicacion'], '2013-05-21')
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha'])
        self.assertEqual(row['codigo_ine'], '08040')
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['vigencia_verificada'])
        self.assertIn('13 de maig', row['documentos'][0]['titulo'])

    def test_group_documents_and_ignore_unrelated_links(self):
        html = page(item() + '<p><a href="https://dogc.gencat.cat/ca/document-del-dogc/?documentId=999">Second edict</a></p>'
                    + item() + '<p>Informació relacionada:</p>'
                    + '<p><a href="document.php?id=123">Procurement announcement</a></p>')
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['id'], Adapter.parse_projects(page(item()))[0]['id'])

    def test_inverted_dogc_dates(self):
        html = page(item().replace('(DOGC núm. 6379 de data 21-05-2013)', 'de data 18-07-2011 (DOGC núm. 5922).'))
        self.assertEqual(Adapter.parse_projects(html)[0]['fecha_publicacion'], '2011-07-18')

    def test_context_does_not_become_an_approved_poum(self):
        html = page('<p>nul·litat del POUM de Canet de Mar</p>' + item()
                    + '<p>Per acord del Ple s’ha acordat iniciar els estudis per al nou POUM</p>')
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['contexto_planeamiento']), 2)
        self.assertIsNone(rows[0]['fase'])

    def test_reject_empty_forms_missing_docs_and_pagination(self):
        for html in [page('<p>Llicència urbanística: formulari</p>'),
                     page('<p>- Pla especial sense documents</p>'),
                     page(item() + '<a href="?page=2" rel="next">2</a>'),
                     '<h1>Login</h1>',
                     page(item().replace('21-05-2013', '31-02-2013'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_official_latin1_encoding(self):
        html = ('<meta charset="iso-8859-1">' + page(item())).encode('iso-8859-1')
        self.assertEqual(Adapter.parse_projects(html)[0]['fecha_publicacion'], '2013-05-21')

    def test_missing_publication_date_stays_null(self):
        row = Adapter.parse_projects(page(item().replace(' de data 21-05-2013', '')))[0]
        self.assertIsNone(row['fecha_publicacion'])

    def test_registry_and_full_refresh(self):
        manifest = load_manifest('canet-de-mar')
        adapter = load_portal_adapter(manifest)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(adapter.slug, 'canet-de-mar')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 4}) as backfill:
                self.assertEqual(adapter.update_proyectos(output, Path(directory) / 'state.json')['rows'], 4)
                backfill.assert_called_once_with(output)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
