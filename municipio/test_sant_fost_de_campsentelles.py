import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_fost_de_campsentelles import SantFostDeCampsentellesAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory(extra='', duplicate=False):
    plan = '<a href="/media/repository/plan.pdf"><span class="txt">PLA D’ORDENACIÓ URBANÍSTICA MUNICIPAL SANT FOST <span>(73.6MB)</span></span></a>'
    return ('<h1>Normes urbanístiques</h1><div>Darrera actualització: 13.10.2026</div>'
            '<section id="page-documents">' + plan + (plan if duplicate else '') +
            '<a href="/media/repository/normes.pdf">Normes text refós POUM (CAT) (663.5KB)</a>'
            '<a href="/media/repository/normes-cast.pdf">Normes text refós POUM (CAST)</a>' + extra + '</section>')


class SantFostTests(unittest.TestCase):
    def test_group_documents_and_dates(self):
        rows = Adapter.parse_projects(inventory(duplicate=True))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 3)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[key])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['codigo_ine'], '08209')
        self.assertEqual(row['id'], Adapter.parse_projects(inventory())[0]['id'])

    def test_reject_non_records(self):
        for html in ('<h1>Login</h1>', '<h1>Normes urbanístiques</h1>',
                     '<h1>Normes urbanístiques</h1><section id="page-documents"><a href="/form.pdf">Sol·licitud de llicència</a></section>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_pagination_fails_visibly(self):
        for pagination in ('<a rel="next" href="?page=2">2</a>', '<div class="pagination">1 2</div>', '<a href="?page=2">Següent</a>'):
            with self.subTest(pagination=pagination), self.assertRaises(ValueError):
                Adapter.parse_projects(inventory() + pagination)

    def test_unreviewed_or_officially_unrelated_document_fails(self):
        for html in (inventory('<a href="/media/repository/other.pdf">Pla parcial sector X</a>'),
                     inventory().replace('/media/repository/plan.pdf', 'https://example.org/plan.pdf'),
                     inventory().replace('Normes text refós POUM (CAT)', 'Licitació obres')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_loads_adapter_and_disabled_feeds(self):
        manifest = load_manifest('sant-fost-de-campsentelles')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Sant Fost de Campsentelles', 'Barcelona', '08209'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(target)['status'], 'disabled')
            self.assertFalse(target.exists())

    def test_update_refreshes_full_snapshot(self):
        adapter = Adapter('sant-fost-de-campsentelles')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 1}) as backfill:
            target, state = Path('out'), Path('state')
            self.assertEqual(adapter.update_proyectos(target, state), {'rows': 1})
            backfill.assert_called_once_with(target)
