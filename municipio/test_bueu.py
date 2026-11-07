"""Offline parser contract tests; fixture mirrors municipal document widgets."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.bueu import BueuAyuntamientoAdapter, GROUP_MINIMUMS, SOURCE
from municipio.manifest import load_manifest, load_yaml


def fixture(extra=""):
    groups = []
    for group, count in GROUP_MINIMUMS.items():
        links = "".join(
            f'<a href="/wp-content/uploads/2018/02/{group.replace(" ", "_")}_{i}.pdf">Documento {i}</a>'
            for i in range(count)
        )
        groups.append(f'<div class="lsvr_document-attachments-widget"><h3 class="widget__title">{group}</h3>{links}</div>')
    return ('<main><div class="page__content"><h3>PXOM Bueu (Aprobación definitiva orde 22/09/2017)</h3>'
            + "".join(groups) + extra + '</div></main>')


class BueuTests(unittest.TestCase):
    def test_instrument_and_explicit_date_provenance(self):
        rows = BueuAyuntamientoAdapter.parse_projects(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '36004')
        self.assertEqual(row['fecha_aprob'], '2017-09-22')
        for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertEqual(len(row['documentos']), 13)
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))

    def test_duplicate_links_and_new_documents(self):
        duplicate = '<div class="lsvr_document-attachments-widget"><h3 class="widget__title">MEMORIA</h3><a href="/wp-content/uploads/2018/02/MEMORIA_0.pdf">Duplicate</a><a href="/wp-content/uploads/2026/new.pdf">New document</a></div>'
        row = BueuAyuntamientoAdapter.parse_projects(fixture(duplicate))[0]
        self.assertEqual(len(row['documentos']), 14)
        self.assertEqual(row['id'], 'bueu-proy-pxom')

    def test_fail_closed_on_pagination_missing_documents_or_changed_source(self):
        for html in (
            fixture('<a rel="next" href="/pxom/page/2/">2</a>'),
            fixture('<a href="?page=2">Seguinte</a>'),
            fixture().replace('class="lsvr_document-attachments-widget"', 'class="lost"'),
            fixture().replace('PXOM Bueu', 'Solicitude de licenza'),
            fixture().replace('22/09/2017', '31/02/2017'),
            fixture().replace('/wp-content/uploads/2018/02/MEMORIA_0.pdf', 'https://example.org/doc.pdf'),
            '<html>Unrelated news</html>',
        ):
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                BueuAyuntamientoAdapter.parse_projects(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('bueu')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('36004', 'Pontevedra'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = BueuAyuntamientoAdapter('bueu').backfill_licencias(out)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
