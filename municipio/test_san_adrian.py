import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.san_adrian import SOURCE, SanAdrianAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest


def inventory(items=''):
    return '''<article><div class="entry-content">
    <div id="lipsum">Publicación del Plan General Municipal de San Adrián,
    aprobado definitivamente por Orden Foral 186/09, de 22 de octubre.</div>
    <ul class="lista-items"><li>Plan General Municipal. Descargar BOLETÍN Nº 111
    <a href="/docs/plan.pdf">Descargar (PDF)</a></li>''' + items + '</ul></div></article>'


class SanAdrianTests(unittest.TestCase):
    def test_group_documents_dates_and_identity(self):
        html = inventory('''<li><span class="txt-item">Modificación 15 Abr. 2011.</span>
            <a href="/docs/mod.pdf">Acuerdo</a><a href="/docs/annex.pdf">Anexo</a>
            <a href="/docs/mod.pdf">Duplicado</a></li>''')
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[1]['documentos']), 2)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '31215')
            for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[key])
        self.assertIn('15 Abr. 2011', rows[1]['source_label'])
        self.assertEqual(rows[0]['id'], parse_inventory(inventory())[0]['id'])

    def test_forms_navigation_and_markup_rejected(self):
        for html in ('<a href="/docs/plan.pdf">Plan General Municipal</a>',
                     inventory().replace('Plan General Municipal. Descargar', 'Solicitud de licencia'),
                     inventory().replace('/docs/plan.pdf', 'https://example.org/plan.pdf'),
                     inventory().replace('<a href="/docs/plan.pdf">Descargar (PDF)</a>', '')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_rejected(self):
        for extra in ('<a rel="next" href="?page=2">2</a>', '<nav class="pagination">2</nav>',
                      '<a href="?page=2">Siguiente</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(inventory() + extra)

    def test_live_contract_and_failed_document_preserves_output(self):
        adapter = SanAdrianAyuntamientoAdapter('san-adrian')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), b'%PDF-1.7\nfixture']):
                result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            row = json.loads(out.read_text())
            self.assertEqual(row['inventory_url'], SOURCE)
            self.assertEqual(len(row['documentos'][0]['sha256']), 64)
            before = out.read_bytes()
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), b'<html>login</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), before)
            self.assertEqual(adapter.backfill_licencias(Path(tmp) / 'lic.jsonl')['status'], 'disabled')

    def test_manifest(self):
        manifest = load_manifest('san-adrian')
        self.assertEqual(manifest.provincia, 'Navarra')
        self.assertFalse(manifest.licencias.enabled)
        self.assertTrue(manifest.proyectos.enabled)


if __name__ == '__main__':
    unittest.main()
