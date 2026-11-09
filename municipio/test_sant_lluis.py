import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from municipio.adapters.sant_lluis import SantLluisAyuntamientoAdapter as Adapter, SOURCE, BASE
from municipio.manifest import load_manifest


def page(active, body, links=''):
    return ('<h1>NORMATIVA URBANÍSTICA DE SANT LLUÍS</h1><div class="PLA_texte">'
            f'<a class="boton2" href="#*">{active}</a>{links}{body}</div>')


def doc(name, path):
    return f'<a href="/WebEditor/{path}.pdf">{name}</a>'


class SantLluisTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        html = page('Altres normatives urbanístiques',
                    '<strong>Pla Especial de Ses Barraques</strong>' + doc('Pla', 'pla') +
                    doc('Plànols', 'planols') + doc('Pla duplicat', 'pla') +
                    '<strong>Pla Especial de Binifadet</strong>' + doc('Pla', 'binifadet'))
        _, groups = Adapter.parse_page(html, SOURCE)
        self.assertEqual([len(v) for v in groups.values()], [2, 1])
        self.assertEqual(groups['Pla Especial de Ses Barraques'][0]['source_url'], SOURCE)

    def test_all_documents_no_truncation(self):
        _, groups = Adapter.parse_page(page('Normes Subsidiàries als nuclis tradicionals i sòl rústic',
            doc('Normativa', 'normativa') + ''.join(doc(str(i), str(i)) for i in range(80))), SOURCE)
        self.assertEqual(len(groups['Normes Subsidiàries de Sant Lluís']), 81)

    def test_navigation(self):
        links, _ = Adapter.parse_page(page('Normes Subsidiàries a les zones turístiques',
            doc('Normativa Text Refòs 2013', 'normativa'),
            '<a class="boton" href="/contingut.aspx?IdPub=37100">Altres</a>'), SOURCE)
        self.assertEqual(links, [BASE + '/Contingut.aspx?IdPub=37100'])

    def test_fail_closed(self):
        valid = page('Normes Subsidiàries', doc('Normativa', 'normativa'))
        for html in ['<h1>Login</h1>', page('Normes Subsidiàries', ''),
                     valid + '<a href="?page=2">2</a>',
                     valid + '<a href="?x=2" rel="next">»</a>',
                     valid + '<a href="?x=2">Següent</a>',
                     page('Altres normatives urbanístiques', doc('Sense grup', 'pla'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_page(html, SOURCE)

    def test_snapshot_groups_tabs_and_preserves_unknown_dates(self):
        tab2, tab3 = [BASE + '/Contingut.aspx?IdPub=' + str(i) for i in (37093, 37100)]
        htmls = {
            SOURCE: page('Normes Subsidiàries als nuclis tradicionals i sòl rústic', doc('Normativa', 'normativa'),
                         '<a class="boton" href="' + tab2 + '">Zones</a>'),
            tab2: page('Normes Subsidiàries a les zones turístiques', doc('Normativa 2013', 'normativa2013'),
                       '<a class="boton" href="' + tab3 + '">Altres</a>'),
            tab3: page('Altres normatives urbanístiques', '<strong>Pla Especial de Binifadet</strong>' + doc('Pla', 'pla') +
                       '<strong>Nucli Rural Camp Sarc</strong>' + doc('Normativa', 'camp')),
        }
        class Response:
            def __init__(self, url):
                self.url, self.content = url, htmls[url].encode()
            def raise_for_status(self):
                pass
        with TemporaryDirectory() as tmp, patch('municipio.adapters.sant_lluis.requests.Session.get',
                                                side_effect=lambda url, **kw: Response(url)) as get:
            out = Path(tmp) / 'proyectos.jsonl'
            result = Adapter('sant-lluis').backfill_proyectos(out)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(get.call_count, 3)
            nnss = next(row for row in rows if row['titulo'].startswith('Normes'))
            self.assertEqual(len(nnss['documentos']), 2)
            for row in rows:
                self.assertIsNone(row['fecha_aprob'])
                self.assertIsNone(row['fecha_publicacion'])
                self.assertIsNone(row['geometry'])

    def test_disabled_licences_and_manifest(self):
        manifest = load_manifest('sant-lluis')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(Adapter('sant-lluis').backfill_licencias(out)['rows'], 0)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
