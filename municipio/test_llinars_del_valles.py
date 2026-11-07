import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.llinars_del_valles import (
    LlinarsDelVallesAyuntamientoAdapter, SOURCE, parse_inventory, parse_sheet,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory(links=None):
    links = links or [('Consolidació estructural de l’edifici', 'one.pdf')]
    return ('<div id="readspeakerPage"><h1>Projectes d\'obra</h1><div class="ddbbtext">'
            + ''.join(f'<a href="http://www.llinarsdelvalles.cat/media/repository/documents/urbanisme/projectes-dobra/2016/{url}">{title}</a>' for title, url in links)
            + '</div><span class="updated">23.05.2016</span></div>')


def sheet(approval='31 d’agost de 2015', expediente='426/2014'):
    return f'''OBRA: CONSOLIDACIÓ ESTRUCTURAL
EXP. ADM.                  {expediente}
TIPUS D’INTERVENCIÓ         Consolidació estructural
SITUACIÓ                   Sector D “Can Marquès”
DATA D’APROVACIÓ            {approval}
ESTAT DE L’OBRA             En execució
'''


class LlinarsTests(unittest.TestCase):
    def test_inventory_requires_real_content(self):
        for html in ['<nav>Projectes d\'obra</nav>', inventory().replace('Consolidació estructural de l’edifici', 'Sol·licitud de llicència')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_urls_and_deduplication(self):
        docs = parse_inventory(inventory([('Consolidació edifici', 'a.pdf')] * 2))
        self.assertEqual(len(docs), 1)
        self.assertTrue(docs[0]['url'].startswith('https://'))
        self.assertTrue(docs[0]['url_original'].startswith('http://'))
        with self.assertRaises(ValueError):
            parse_inventory(inventory().replace('www.llinarsdelvalles.cat', 'example.org'))

    def test_pagination_fails_instead_of_truncating(self):
        for markup in ['<a rel="next" href="?page=2">2</a>', '<a href="?pag=2">2</a>', '<div class="pagination">2</div>']:
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(inventory() + markup)

    def test_explicit_approval_dates(self):
        for source, expected in [('31 d’agost de 2015', '2015-08-31'), ('31 de març de 2014', '2014-03-31'), ('29 de març 2016', '2016-03-29')]:
            self.assertEqual(parse_sheet(sheet(source))['fecha_aprob'], expected)
        for text in [sheet('31 de febrer de 2016'), sheet().replace('DATA D’APROVACIÓ', 'DATA PUBLICACIÓ')]:
            with self.assertRaises(ValueError):
                parse_sheet(text)

    def test_group_documents_and_separate_date_semantics(self):
        adapter = LlinarsDelVallesAyuntamientoAdapter('llinars-del-valles')
        html = inventory([('Consolidació edifici', 'a.pdf'), ('Consolidació edifici annex', 'b.pdf')])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda url, limit: html.encode() if url == SOURCE else b'%PDF-fixture'), patch.object(adapter, '_pdf_text', return_value=sheet()):
                result = adapter.backfill_proyectos(path)
            row, = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(row['documentos']), 2)
            self.assertEqual(row['fecha_aprob'], '2015-08-31')
            for field in ['fecha_publicacion', 'fecha_acuerdo', 'fecha', 'fase', 'geometry', 'lat', 'lon']:
                self.assertIsNone(row[field])
            self.assertEqual(row['estado_obra_segun_ficha'], 'En execució')

    def test_failure_preserves_existing_output(self):
        adapter = LlinarsDelVallesAyuntamientoAdapter('llinars-del-valles')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proyectos.jsonl'
            path.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', return_value=b'<html>login</html>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')

    def test_reject_non_pdf_attachment(self):
        with self.assertRaises(ValueError):
            LlinarsDelVallesAyuntamientoAdapter._pdf_text(b'<html>login</html>')

    def test_manifest_loads_through_registry(self):
        manifest = load_manifest('llinars-del-valles')
        self.assertIsInstance(load_portal_adapter(manifest), LlinarsDelVallesAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08106')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
