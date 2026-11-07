import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from municipio.adapters.castello_d_empuries import (
    INVENTORIES, CastelloDEmpuriesAyuntamientoAdapter, parse_inventory, parse_project,
)
from municipio.manifest import load_manifest

TITLE = 'Pla Parcial PPU-2 Hort d’en Negre / Tià de l’Estanyol'
URL = INVENTORIES[0] + 'ppu-2/'
ITEM = {'url': URL, 'titulo': TITLE, 'inventory_url': INVENTORIES[0]}
DOC = 'https://www.castello.cat/wp-content/uploads/2024/11/acord.pdf'
INVENTORY = f'''<main><h1>Planejament urbanístic</h1><div class="page__content">
<h4 class="pt-cv-title"><a href="{URL}">{TITLE}</a></h4></div></main>'''
DETAIL = f'''<main><h1>{TITLE}</h1><div class="page__content">
<a href="{DOC}">Acord d’aprovació definitiva del Text Refós (02/11/2021)</a>
<a href="{DOC}" download>Baixa</a><a href="{DOC}">Acord en català</a>
<a href="/wp-content/uploads/2024/11/memoria.pdf">Memòria</a>
<a href="https://external.example/news.pdf">Unrelated</a></div></main>'''


class CastelloTests(unittest.TestCase):
    def test_inventory_scoped_and_deduplicated(self):
        self.assertEqual(parse_inventory(INVENTORY, INVENTORIES[0]), [ITEM])
        with self.assertRaises(ValueError):
            parse_inventory('<main><h1>Login</h1></main>', INVENTORIES[0])
        with self.assertRaises(ValueError):
            parse_inventory(INVENTORY.replace(TITLE, 'Llicència formulari'), INVENTORIES[0])

    def test_pagination_fails_explicitly(self):
        for control in ['<a rel="next" href="?page=2">Next</a>', '<div class="pt-cv-pagination"></div>']:
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(INVENTORY.replace('</div>', control + '</div>'), INVENTORIES[0])

    def test_document_grouping_and_unknown_dates(self):
        row = parse_project(DETAIL, ITEM)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['labels'], [
            'Acord d’aprovació definitiva del Text Refós (02/11/2021)', 'Acord en català'])
        for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['id'], parse_project(DETAIL, ITEM)['id'])

    def test_reject_title_mismatch_and_documentless_pages(self):
        for html in [DETAIL.replace(TITLE, 'Error'), f'<main><h1>{TITLE}</h1><div class="page__content">Formularis</div></main>']:
            with self.assertRaises(ValueError):
                parse_project(html, ITEM)

    def test_snapshot_and_failure_preserves_output(self):
        adapter = CastelloDEmpuriesAyuntamientoAdapter('castello-d-empuries')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, INVENTORY, DETAIL]):
                result = adapter.update_proyectos(output, Path(folder) / 'state.json')
            self.assertEqual(result['rows'], 1)
            previous = output.read_text()
            self.assertEqual(json.loads(previous)['codigo_ine'], '17047')
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, INVENTORY, '<html>Error</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), previous)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('castello-d-empuries')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'licencias.jsonl'
            result = CastelloDEmpuriesAyuntamientoAdapter(manifest.slug).backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_fetch_accepts_percent_escape_casing_but_rejects_redirect(self):
        adapter = CastelloDEmpuriesAyuntamientoAdapter('castello-d-empuries')
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        response.url = URL + 'instal%C2%B7lacio/'
        response.iter_content.return_value = [DETAIL.encode('utf-8')]
        self.assertEqual(adapter._fetch(session, URL + 'instal%c2%b7lacio/'), DETAIL)
        response.url = 'https://other.example/login'
        with self.assertRaisesRegex(ValueError, 'redirect'):
            adapter._fetch(session, URL)


if __name__ == '__main__':
    unittest.main()
