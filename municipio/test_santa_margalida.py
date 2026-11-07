"""Offline parser/contract tests; no evidence files or live network required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_margalida import BASE, SOURCE, SantaMargalidaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest

TITLES = [
    'Normes Subsidiàries de Santa Margalida de1986',
    'Modificació de 2013 de NNSS 1986: construcció piscines (BOIB 1 08 2013)',
    'Documentacio APROVACIO INICIAL MODIFICACIO 2014 2015: zonificació esportiva sector 7',
    'Edicte de publicació dins tràmit de MODIFICACIO 2014 2015: zonificació esportiva sector 7',
    'Edicte 1 MODIFICACIO 2016: implantació d’un sistema general sanitari-assistencial i d’aparcaments públics',
    'Edicte 2 MODIFICACIO 2016 continuada al 2017 per errada a la de 2016: implantació d’un sistema general sanitari-assistencial i d’aparcaments públics',
]


def inventory(titles=TITLES):
    return '<h1>7.1. PLANEJAMENT URBANÍSTIC</h1><table class="TransparencyListPanel"><tbody>' + ''.join(
        f'<tr><td class="class_name"><a href="/preview-document/00000000-0000-0000-0000-{i:012d}">{t}</a></td></tr>'
        for i, t in enumerate(titles)) + '</tbody></table>'


PREVIEW = '<h1>Informació del document</h1><p>Data de creació 14-oct-2020</p><iframe src="/preview/pdf/document.pdf"></iframe>'


class SantaMargalidaTests(unittest.TestCase):
    def test_grouping_preserves_six_documents_in_four_instruments(self):
        rows = Adapter.parse_inventory(inventory())
        self.assertEqual(len(rows), 4)
        self.assertEqual(sorted(len(r['documentos']) for r in rows), [1, 1, 2, 2])
        self.assertEqual(len({d['url'] for r in rows for d in r['documentos']}), 6)
        spaced = Adapter.parse_inventory(inventory().replace('aparcaments públics', 'aparcaments  públics'))
        self.assertEqual([(r['id'], len(r['documentos'])) for r in rows],
                         [(r['id'], len(r['documentos'])) for r in spaced])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '07055')
            self.assertIsNone(row['lat'])
            self.assertIsNone(row['geometry'])

    def test_publication_is_not_agreement_or_creation(self):
        rows = Adapter.parse_inventory(inventory())
        dated = [r for r in rows if r['fecha_publicacion']]
        self.assertEqual([r['fecha_publicacion'] for r in dated], ['2013-08-01'])
        for row in rows:
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha'])
            self.assertIsNone(row['fase'])
        metadata = Adapter.parse_preview(PREVIEW, SOURCE)
        self.assertNotIn('fecha_publicacion', metadata)

    def test_missing_invalid_and_unreviewed_sources_fail(self):
        for html in ['<h1>Login</h1>', inventory([]), inventory(['Sol·licitud de llicència']),
                     inventory().replace('/preview-document/', 'https://example.org/preview-document/')]:
            with self.subTest(html=html[:100]), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        for html in ['<p>login</p>', PREVIEW.replace('/preview/pdf/document.pdf', 'https://example.org/doc.pdf')]:
            with self.assertRaises(ValueError):
                Adapter.parse_preview(html, SOURCE)

    def test_pagination_including_ajax_is_never_silently_skipped(self):
        for pager in ['<a rel="next" href="?page=1">→</a>', '<button onclick="ajax()">Següent</button>',
                      '<div class="navigator"><a onclick="ajax()">2</a></div>']:
            with self.subTest(pager=pager), self.assertRaises(ValueError):
                Adapter.parse_inventory(inventory() + pager)

    def test_full_snapshot_and_failure_preserves_previous_output(self):
        adapter = Adapter('santa-margalida')
        with tempfile.TemporaryDirectory() as temp:
            output, state = Path(temp) / 'rows.jsonl', Path(temp) / 'state.json'
            with patch.object(adapter, '_fetch', side_effect=lambda u: inventory() if u == SOURCE else PREVIEW):
                result = adapter.update_proyectos(output, state)
            self.assertEqual(result['rows'], 4)
            old = output.read_text()
            self.assertEqual(sum(len(json.loads(r)['documentos']) for r in old.splitlines()), 6)
            with patch.object(adapter, '_fetch', side_effect=[inventory(), '<h1>Login</h1>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), old)
            self.assertFalse(state.exists())

    def test_manifest_and_disabled_licences(self):
        m = load_manifest('santa-margalida')
        self.assertEqual(m.provincia, 'Illes Balears')
        self.assertFalse(m.licencias.enabled)
        self.assertEqual(m.portal.config['ine_code'], '07055')
        adapter = Adapter(m.slug)
        with tempfile.TemporaryDirectory() as temp, patch.object(adapter, '_fetch') as fetch:
            p = Path(temp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(p)['status'], 'disabled')
            self.assertEqual(p.read_text(), '')
            fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
