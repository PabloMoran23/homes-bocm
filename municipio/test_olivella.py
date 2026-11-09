"""Offline parser tests; fixtures model the official Liferay article structure."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.olivella import CATEGORIES, SOURCE, OlivellaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def article(body, updated='24/11/2025'):
    return ('<div class="journal-content-article"><div class="item_indicador">Help</div></div>'
            '<div class="journal-content-article">' + body +
            '<div class="datatable_info_footer">Actualització: ' + updated + ' | Font: Propi ens</div></div>'
            '<div class="journal-content-article"><div class="accessdirecte_element">Navigation</div></div>')


def doc(title, uid):
    return f'<li><a href="/documents/1125140/20120023/title/{uid}">Descarrega {title}</a></li>'


class OlivellaTests(unittest.TestCase):
    def test_plan_annexes_are_one_instrument_and_dates_stay_distinct(self):
        html = article('<p>APROVACIÓ INICIAL PLA ESPECIAL CÀMPING</p><p>EXP. 2266-0932/2022</p><ul>' +
                       doc('PEU TORRENT ROMEGUERA', 'main') + ''.join(doc('ANNEX ' + str(i), str(i)) for i in range(1, 6)) +
                       doc('NOTA ACLARIDORA', 'note') + '</ul>')
        rows = Adapter.parse_category(html, SOURCE + '/pla-especial-urbanistic-aprovacio-inicial-216')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 7)
        self.assertEqual(row['expediente'], '2266-0932/2022')
        self.assertEqual(row['fecha_actualizacion_fuente'], '2025-11-24')
        for key in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertNotIn('Help', row['descripcion'])
        self.assertFalse(row['publication_ready'])

    def test_distinct_complete_works_are_separate(self):
        html = article('<p>Aprovació inicial projecte obres</p><ul>' + doc('Projecte obres millora aparcament El Querol', 'a') +
                       doc('MEMORIA I ANNEXOS PROJECTE OBRES ITINERARIS SALUDABLES I PEDALABLES', 'b') + '</ul>')
        rows = Adapter.parse_category(html, SOURCE + '/projectes-d-obres-aprovacio-inicial-205')
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertTrue(all(len(r['documentos']) == 1 for r in rows))

    def test_empty_section_and_unusable_content(self):
        url = SOURCE + '/projectes-de-reparcel-lacio-aprovacio-definitiva-215'
        self.assertEqual(Adapter.parse_category(article('<div></div>'), url), [])
        for html in ('<html>Access denied</html>', article('<p>Formulari llicència urbanística</p>')):
            with self.assertRaises(ValueError):
                Adapter.parse_category(html, url)

    def test_pagination_is_not_silently_ignored(self):
        for link in ('<a rel="next" href="?page=2">More</a>', '<a href="?cur=2">2</a>', '<a href="/next">Següent</a>'):
            with self.assertRaises(ValueError):
                Adapter.parse_inventory(link)

    def test_inventory_requires_all_reviewed_sections(self):
        html = ''.join(f'<a href="{SOURCE}/{key}">{key}</a>' for key in CATEGORIES)
        self.assertEqual(len(Adapter.parse_inventory(html)), 9)
        with self.assertRaises(ValueError):
            Adapter.parse_inventory('<a href="/forms">Projectes</a>')

    def test_ambiguous_grouping_fails(self):
        html = article('<ul>' + doc('Project A', 'a') + doc('Project B', 'b') + '</ul>')
        with self.assertRaises(ValueError):
            Adapter.parse_category(html, SOURCE + '/pla-especial-urbanistic-aprovacio-inicial-216')

    def test_manifest_loads_and_licences_disabled(self):
        manifest = load_manifest('olivella')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08148')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(out)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(out.read_text(), '')

    def test_update_is_full_snapshot(self):
        adapter = Adapter('olivella')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 7}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('unused'), Path('state')), {'rows': 7})
            backfill.assert_called_once_with(Path('unused'))


if __name__ == '__main__':
    unittest.main()
