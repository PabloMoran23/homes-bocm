import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.lloseta import LlosetaAyuntamientoAdapter as Adapter, ROOT, SOURCE
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

PLAN = '55e/2025 MP 1/2024 NS de Lloseta per implantar ús turístic'
WASTE = '13a/2024 Centre de gestió de residus no perillosos T.M. Lloseta'


def page(title, body):
    return '<main><div class="imc--contenido-html"><div><h1>' + title + '</h1>' + body + '</div></div></main>'


def inventory(extra=''):
    # Detail links also exist in site navigation; its other municipalities and
    # navigation-only Lloseta entries must not become inventory records.
    return ('<nav><a href="' + ROOT + 'plan/">' + PLAN + '</a>'
            '<a href="' + ROOT + 'waste/">' + WASTE + '</a>'
            '<a href="' + ROOT + 'other/">99e/2020 Lloseta</a></nav>' +
            page("Publicació de documents ambientals en tramitació d'avaluació simplificada",
                 '<table><tr><td><a href="contenido.do?idsite=7085&amp;cont=1">' + PLAN + '</a></td></tr>'
                 '<tr><td><a href="archivopub.do?id=7">' + WASTE + '</a></td></tr>'
                 '<tr><td><a href="other/">12a/2024 Centre de residus T.M. Inca</a></td></tr></table>' + extra))


def dossier(title=PLAN, docs=True):
    return page(title, ('<a href="archivopub.do?id=1">Memoria</a>'
                        '<a href=" \tarchivopub.do?id=2">Estudi ambiental</a>'
                        '<a href="archivopub.do?id=1">Memoria duplicada</a>') if docs else '')


class LlosetaParserTests(unittest.TestCase):
    def test_inventory_scope_and_stable_identity(self):
        entries = Adapter.parse_inventory(inventory())
        self.assertEqual([e['expediente'] for e in entries], ['13a/2024', '55e/2025'])
        self.assertEqual(entries[0]['url'], ROOT + 'waste/')
        self.assertIn('archivopub.do', entries[0]['url_inventario_enlace'])

    def test_documents_grouped_and_no_invented_dates(self):
        entry = Adapter.parse_inventory(inventory())[1]
        row = Adapter.parse_dossier(dossier(), entry)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['tipo'], 'planeamiento_urbanistico')
        self.assertEqual(row['id'], 'lloseta-caib-55e-2025')
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase']:
            self.assertIsNone(row[key])
        self.assertTrue(all(d['url_procedencia'] == entry['url'] for d in row['documentos']))

    def test_pagination_fails_closed(self):
        for extra in ['<a rel="next" href="?p=2">2</a>', '<a href="?page=1">2</a>',
                      '<div class="pagination"><a href="p2/">2</a></div>']:
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'Pagination'):
                Adapter.parse_inventory(inventory(extra))

    def test_ambiguous_dossier_fails(self):
        html = inventory() + '<a href="' + ROOT + 'plan2/">' + PLAN + '</a>'
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            Adapter.parse_inventory(html)

    def test_missing_and_wrong_dossiers_fail(self):
        entry = Adapter.parse_inventory(inventory())[1]
        for html in [dossier(docs=False), dossier(WASTE), '<h1>Login</h1>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_dossier(html, entry)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory(page('Formularis', '<a href="x">Sol·licitud llicència</a>'))

    def test_external_document_rejected(self):
        entry = Adapter.parse_inventory(inventory())[1]
        with self.assertRaisesRegex(ValueError, 'Unexpected source URL'):
            Adapter.parse_dossier(page(PLAN, '<a href="https://example.org/archivopub.do?id=1">Doc</a>'), entry)

    def test_snapshot_is_only_replaced_after_complete_extraction(self):
        adapter = Adapter()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous\n')
            with patch.object(adapter, '_fetch', side_effect=[inventory(), dossier(WASTE), dossier(docs=False)]):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous\n')
            with patch.object(adapter, '_fetch', side_effect=[inventory(), dossier(WASTE), dossier()]):
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 2)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('lloseta')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '07029')
        self.assertEqual(manifest.provincia, 'Illes Balears')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
