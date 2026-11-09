"""Parser regression tests with small source-shaped, offline fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.suria import SuriaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(body):
    return '<div id="pepe"><article>' + body + '</article></div>'

OVERVIEW = page("<p>L'Ajuntament ha iniciat el procés d'elaboració del Pla d'Ordenació Urbanística Municipal de Súria.</p>")
DOCS = page('''<h3>DOCUMENTS</h3><p>ANY 2023</p><ul>
<li>Avanç POUM: <a href="/media/avanc.pdf">Enllaç</a></li>
<li>Participació POUM: <a href="http://www.suria.cat//media/participacio.pdf">Enllaç</a></li>
<li>Cartell POUM: <a href="/media/cartell.jpg">Enllaç</a></li>
<li>Repetit: <a href="https://www.suria.cat/media/avanc.pdf">Enllaç</a></li>
</ul>''')
NORMES = page('''<p>Aquesta versió de les Normes Subsidiàries de Planejament fou aprovada definitivament
per la Comissió d'Urbanisme de Barcelona en sessió de 21 de gener de 2003, publicada en el Diari
Oficial de la Generalitat (DOGC) número 3877 de 6/05/03. Les modificacions posteriors han de ser consultades al Registre.</p>
<ul><li>Normes títol 1: <a href="/media/normes1.pdf">Enllaç</a></li>
<li>Normes títol 2: <a href="/media/normes2.pdf">Enllaç</a></li></ul>''')


class SuriaTests(unittest.TestCase):
    def parse(self, overview=OVERVIEW, docs=DOCS, normes=NORMES):
        return Adapter.parse_projects(overview, docs, normes)

    def test_grouping_provenance_and_document_isolation(self):
        rows = self.parse()
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [3, 2])
        doc = rows[0]['documentos'][1]
        self.assertEqual(doc['url'], 'https://www.suria.cat/media/participacio.pdf')
        self.assertEqual(doc['source_href'], 'http://www.suria.cat//media/participacio.pdf')
        self.assertIn('Participació', doc['titulo'])
        self.assertTrue(all('normes' in d['url'] for d in rows[1]['documentos']))

    def test_dates_have_explicit_distinct_meanings(self):
        poum, normes = self.parse()
        self.assertEqual(normes['fecha_aprob'], '2003-01-21')
        self.assertEqual(normes['fecha_publicacion'], '2003-05-06')
        for field in ['fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'fase']:
            self.assertIsNone(poum[field])
        self.assertIsNone(normes['fecha_acuerdo'])

    def test_no_geocoding_or_licence_inference(self):
        for row in self.parse():
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '08274')
            for field in ['geometry', 'lat', 'lon']:
                self.assertIsNone(row[field])

    def test_empty_navigation_and_changed_sources_fail(self):
        for changed in ['', '<nav>POUM <a href="/media/a.pdf">Avanç</a></nav>', page('<p>Notícies</p>')]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.parse(docs=changed)
        with self.assertRaises(ValueError):
            self.parse(overview=page('<p>POUM aprovat</p>'))
        with self.assertRaises(ValueError):
            self.parse(normes=NORMES.replace('6/05/03', 'data desconeguda'))

    def test_pagination_is_never_silently_truncated(self):
        for extra in ['<a rel="next" href="?page=2">2</a>', '<div class="pagination">2</div>', '<a href="?page=2">Següent</a>']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.parse(docs=DOCS.replace('</article>', extra + '</article>'))

    def test_documents_required_and_external_links_excluded(self):
        with self.assertRaises(ValueError):
            self.parse(docs=page('<h3>DOCUMENTS POUM</h3><ul><li><a href="https://elsewhere.test/a.pdf">POUM</a></li></ul>'))

    def test_snapshot_refresh_and_disabled_licences(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'rows.jsonl'
            adapter = Adapter('suria')
            with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as backfill:
                self.assertEqual(adapter.update_proyectos(out, Path(directory) / 'state'), {'rows': 2})
                backfill.assert_called_once_with(out)
            Adapter._write(out, self.parse())
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_manifest_loads_real_adapter_and_required_flags(self):
        import yaml
        manifest = load_manifest('suria')
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)
        raw = yaml.safe_load(manifest.path.read_text())
        self.assertEqual((raw['codigo_ine'], raw['nombre'], raw['provincia']), ('08274', 'Súria', 'Barcelona'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])


if __name__ == '__main__':
    unittest.main()
