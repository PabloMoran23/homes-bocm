import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.etxebarri import AREA, SOURCE, EtxebarriAyuntamientoAdapter, discover, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest

PLAN = AREA + 'Paginas/PGOU-Etxebarri.aspx'
DOCS = AREA + 'Paginas/PGOU-Documentacion.aspx'
INVENTORY = '''<div class="ms-rtestate-field">PGOU. Documentación del proceso en las diferentes fases:
<a href="../PGOU/avance.pdf">Avance</a><a href="../PGOU/plano.pdf">Planos</a>
<a href="../PGOU/avance.pdf">Avance copia</a></div>'''


class EtxebarriTests(unittest.TestCase):
    def test_group_documents_without_invented_dates_or_geometry(self):
        rows = parse_inventory(INVENTORY, DOCS, PLAN)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '48029')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['url'], AREA + 'PGOU/avance.pdf')
        for field in ['fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'geometry', 'lat', 'lon']:
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])

    def test_missing_inventory_and_form_rejected(self):
        for html in ['', '<a href="licencia.pdf">Solicitud licencia</a>', INVENTORY.replace('>Avance<', '>Solicitud<')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, DOCS, PLAN)

    def test_pagination_is_not_silently_ignored(self):
        for link in ['<a href="?page=2">Siguiente</a>', '<a rel="next" href="?p=2">2</a>']:
            with self.assertRaises(ValueError):
                parse_inventory(INVENTORY + link, DOCS, PLAN)

    def test_changed_document_provenance_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory(INVENTORY.replace('../PGOU/plano.pdf', 'https://other.example/plano.pdf'), DOCS, PLAN)

    def test_discovery_and_manifest_extraction(self):
        manifest = load_manifest('etxebarri')
        adapter = load_portal_adapter(manifest)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(discover(f'<a href="{PLAN}"></a>', SOURCE, 'PGOU-Etxebarri.aspx'), PLAN)
        pages = {SOURCE: f'<a href="{PLAN}"></a>',
                 PLAN: f'Plan General de Ordenación Urbana de Etxebarri <a href="{DOCS}"></a>',
                 DOCS: INVENTORY}
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
            path = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(path.read_text())['municipio'], 'Etxebarri')
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')['rows'], 0)

    def test_failed_snapshot_preserves_output(self):
        adapter = EtxebarriAyuntamientoAdapter('etxebarri')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=''):
            path = Path(tmp) / 'out.jsonl'
            path.write_text('previous snapshot')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot')


if __name__ == '__main__':
    unittest.main()
