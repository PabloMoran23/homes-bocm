import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.les_borges_blanques import LesBorgesBlanquesAyuntamientoAdapter as Adapter, SOURCE
from municipio.manifest import load_manifest, load_yaml


def page(body):
    return '<article class="node--type-page"><div class="field--name-body">' + body + '</div></article>'


def inventory(items):
    return page('<h3>3.1 Normativa urbanística</h3><ul>' + items + '</ul><h2>4. PLANS</h2><ul><li><a href="/not-a-project.pdf">Other content</a></li></ul>')


ITEM = '<li><a href="/plan.pdf">Pla de Millora Urbana del carrer Test</a> [Vigent]</li>'


class LesBorgesBlanquesTests(unittest.TestCase):
    def test_scope_and_unknown_dates(self):
        row, = Adapter.parse_inventory(inventory(ITEM))
        self.assertEqual(row['codigo_ine'], '25058')
        self.assertEqual(row['estado_fuente'], 'Vigent')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])

    def test_explicit_agreement_not_publication(self):
        item = '<li><a href="/reparcel.pdf">Modificació del projecte de reparcel·lació PAU 03, aprovat definitivament per acord de JGL de data 18-9-2025</a> [Vigent]</li>'
        row, = Adapter.parse_inventory(inventory(item))
        self.assertEqual(row['fecha_acuerdo'], '2025-09-18')
        self.assertEqual(row['fecha_aprob'], '2025-09-18')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['tipo'], 'reparcelacion')

    def test_initial_approval_is_not_granted_licence(self):
        item = '<li><a href="/plan">Aprovació inicial de la modificació del Pla</a> [En tràmit]</li>'
        row, = Adapter.parse_inventory(inventory(item))
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertIsNone(row['fecha_aprob'])

    def test_group_documents_resolve_and_deduplicate(self):
        docs = Adapter.parse_documents(page('<a href="/memoria amb espais.pdf">Memòria</a><a href="planols.pdf">Plànols</a><a href="planols.pdf">Plànols</a>'), SOURCE)
        self.assertEqual(len(docs), 2)
        self.assertIn('%20', docs[0]['url'])
        self.assertEqual(docs[0]['source_url'], SOURCE)

    def test_changed_or_empty_source_fails(self):
        for html in ('<a href="/plan.pdf">Pla de Millora</a>', inventory(''), inventory('<li><a href="/form.pdf">Sol·licitud de llicència</a> [Vigent]</li>'), inventory(ITEM.replace('[Vigent]', ''))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)
        with self.assertRaises(ValueError):
            Adapter.parse_documents(page('<p>No documents</p>'), SOURCE)

    def test_pagination_never_silently_truncated(self):
        for more in ('<a rel="next" href="?page=1">2</a>', '<a href="?page=1">Següent</a>', '<nav class="pager">2</nav>'):
            with self.subTest(more=more), self.assertRaises(ValueError):
                Adapter.parse_inventory(inventory(ITEM) + more)

    def test_duplicate_identity_and_untrusted_link(self):
        self.assertEqual(len(Adapter.parse_inventory(inventory(ITEM * 2))), 1)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(inventory(ITEM.replace('/plan.pdf', 'https://example.com/plan.pdf')))

    def test_live_interface_groups_one_instrument(self):
        adapter = Adapter('les-borges-blanques')
        html = inventory('<li><a href="/detail">Pla de Millora Urbana Test</a> [Vigent]</li>')
        detail = page('<a href="/a.pdf">Memòria</a><a href="/b.pdf">Plànols</a>')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=[html, detail]):
            output = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(result['rows'], 1)
            self.assertEqual(len(rows[0]['documentos']), 2)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['status'], 'disabled')

    def test_manifest(self):
        manifest = load_manifest('les-borges-blanques')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '25058')
        self.assertEqual(manifest.provincia, 'Lleida')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
