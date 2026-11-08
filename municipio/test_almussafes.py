import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.almussafes import AlmussafesAyuntamientoAdapter, SOURCE
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def page(body):
    return '<main><article><div class="entry-content"><h3>PLANTEJAMENT VIGENT</h3><figure><table>' + body + '</table></figure></div></article></main>'


HEADER = '<tr><td>DESCRIPCIÓ</td><td>DOCUMENT</td></tr>'
GENERAL = '<tr><td>01 – PLA GENERAL</td><td></td></tr>'
DOC = '<tr><td>NORMATIVA</td><td><a href="/wp-content/uploads/2019/01/plan.pdf"><img></a></td></tr>'
DRIVE = '<tr><td>MODIFICACIONS</td><td><a href="https://drive.google.com/file/d/ABC_123/view"><img></a></td></tr>'


class AlmussafesTests(unittest.TestCase):
    def test_group_documents_and_do_not_invent_dates_or_coordinates(self):
        rows = AlmussafesAyuntamientoAdapter.parse_projects(page(HEADER + GENERAL + DOC + DRIVE +
            '<tr><td>02 – PLA PARCIAL PORTETA</td><td></td></tr>' + DOC))
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(rows[0]['documentos'][0]['url_procedencia'], SOURCE)
        self.assertEqual(rows[0]['codigo_ine'], '46035')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(rows[0][field])
        reordered = AlmussafesAyuntamientoAdapter.parse_projects(page(HEADER + GENERAL + DRIVE + DOC))
        self.assertEqual(reordered[0]['id'], rows[0]['id'])

    def test_fail_closed_for_changed_or_incomplete_content(self):
        invalid = [page(''), '<main>Login</main>', page(HEADER + DOC), page(HEADER + GENERAL),
                   page(HEADER + GENERAL + DOC + GENERAL + DOC),
                   page(HEADER + GENERAL + DOC + '<tr><td>03 – PLA ESPECIAL LA TORRE</td><td></td></tr>' + DOC),
                   page(HEADER + GENERAL + DOC.replace('plan.pdf', 'application-form.html'))]
        for html in invalid:
            with self.subTest(html=html), self.assertRaises(ValueError):
                AlmussafesAyuntamientoAdapter.parse_projects(html)

    def test_pagination_is_not_silently_ignored(self):
        for link in ('<a rel="next" href="/more">More</a>', '<a href="?paged=2">2</a>',
                     '<a href="/more">MOSTRAR MÉS</a>'):
            with self.subTest(link=link), self.assertRaises(ValueError):
                AlmussafesAyuntamientoAdapter.parse_projects(page(HEADER + GENERAL + DOC).replace('</div>', link + '</div>'))

    def test_unrelated_news_outside_table_is_excluded(self):
        html = page(HEADER + GENERAL + DOC).replace('</figure>', '</figure><h3>PARC INDUSTRIAL</h3><p>Obres 1995; inauguració 1996</p>')
        self.assertEqual(len(AlmussafesAyuntamientoAdapter.parse_projects(html)), 1)

    def test_manifest_and_snapshot_failure_preserve_previous_output(self):
        manifest = load_manifest('almussafes')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46035')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous snapshot\n')
            with patch('municipio.adapters.almussafes.requests.get') as get:
                response = get.return_value.__enter__.return_value
                response.url = SOURCE
                response.iter_content.return_value = [b'<main>Login</main>']
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot\n')
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
