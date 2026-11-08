import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.arta import (
    ArtaAyuntamientoAdapter, SOURCE, article_url, parse_detail, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(extra=''):
    return '''<div class="titol">Planejament i normativa urbanística</div>
    <p><a href="http://arta.cat/ajuntament/article.php?idart=167">Normes subsidiàries</a></p>
    <p><a href="http://arta.cat:82/ajuntament/article.php?idart=408">Modificació puntual 5a de les Normes subsidiàries</a> Aprovat definitivament</p>
    <p><a href="form.pdf">Sol·licitud de llicència</a></p>
    <p><a href="contract.pdf">Licitació de les obres</a></p>''' + extra


def detail(title, links):
    return '<div class="titol">' + title + '</div><div class="descripcio">' + links + '</div>'


class ArtaParserTests(unittest.TestCase):
    def test_inventory_excludes_forms_procurement_and_unrelated_news(self):
        entries, corrections = parse_inventory(inventory('<a href="news.php">Notícia</a>'))
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]['fase'], 'aprobación definitiva')
        self.assertEqual(corrections, [])
        self.assertEqual(article_url(entries[1]['source_href']),
                         'https://www.arta.cat/ajuntament/article.php?idart=408')

    def test_group_all_documents_and_stage_pages_without_footer(self):
        html = detail('Normes subsidiàries', '''
        <a href="/images/memoria.pdf">Memòria 2015</a>
        <a href="https://seu.arta.cat/absis/verificadorfirma.asp?codigoVerificacion=123">Normativa</a>
        <a href="article.php?idart=450">Aprovació inicial</a>''')
        html += '<a href="/images/privacy.pdf">Privacy</a>'
        heading, documents, children = parse_detail(html, article_url('https://arta.cat/ajuntament/article.php?idart=167'))
        self.assertEqual(heading, 'Normes subsidiàries')
        self.assertEqual(len(documents), 2)
        self.assertEqual(children, ['https://www.arta.cat/ajuntament/article.php?idart=450'])
        self.assertEqual(documents[0]['titulo'], 'Memòria 2015')

    def test_rejects_login_empty_and_pagination(self):
        for html in ['<html>Login</html>', inventory('<div class="pagination">2</div>'),
                     inventory('<a rel="next" href="?page=2">Next</a>')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_detail(detail('Empty', ''), SOURCE)
        with self.assertRaises(ValueError):
            article_url('https://example.org/ajuntament/article.php?idart=167')

    def test_snapshot_grouping_phase_conflict_cycles_and_no_inferred_dates(self):
        base = 'https://www.arta.cat/ajuntament/article.php?idart='
        pages = {
            SOURCE: inventory(),
            base + '167': detail('Normes subsidiàries', '<a href="/images/normativa.pdf">Normativa</a>'),
            base + '408': detail('Modificació puntual 5a. Aprovat inicialment.',
                '<a href="/images/BOIB.pdf">BOIB 57 de 30 d’abril. APROVACIÓ DEFINITIVA</a>'
                '<a href="article.php?idart=450">Aprovació inicial</a>'),
            base + '450': detail('Aprovació inicial',
                '<a href="/images/memoria.pdf">Memòria</a><a href="article.php?idart=408">Tornar</a>'),
        }
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            adapter = ArtaAyuntamientoAdapter()
            with patch.object(adapter, '_fetch', side_effect=lambda u: pages[u]):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            modification = rows[1]
            self.assertEqual(len(modification['documentos']), 2)
            self.assertEqual(modification['fase'], 'aprobación definitiva')
            self.assertIn('inicialment', modification['detail_headings'][0]['titulo'])
            for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
                self.assertIsNone(modification[field])
            previous = output.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[inventory(), pages[base + '167'], 'Login']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), previous)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('arta')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '07006')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as directory:
            adapter = ArtaAyuntamientoAdapter()
            output = Path(directory) / 'licencias.jsonl'
            with patch.object(adapter, '_fetch', side_effect=AssertionError('Must not fetch licences')):
                self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
                self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
