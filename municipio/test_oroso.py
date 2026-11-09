"""Offline parser and traversal checks; no municipal network dependency."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.oroso import (
    LEGACY, SOURCE, OrosoAyuntamientoAdapter, parse_inventory, parse_pxom_page,
)
from municipio.manifest import load_manifest, load_yaml

INVENTORY = '''<div class="entry"><h2>Oficina Municipal de Urbanismo</h2>
<p>Plan Xeral de Ordenación Municipal (PXOM), aprobado definitivamente na orde 16/02/05</p>
<a href="https://www.concellooroso.com/pxom/index.htm">PXOM</a></div>
<div class="modal-content"><h4>Polígono Industrial San Martiño II</h4>
<p>Plan Parcial do Área de Reparto Número 10</p>
<a href="https://www.concellooroso.com/polsmar/memoria.pdf">Memoria</a>
<a href="https://www.concellooroso.com/polsmar/planos/o_viario.pdf">I-13</a>
<a href="https://www.concellooroso.com/polsmar/planos/o_viario.pdf">COTAS-VIARIOS</a>
<h4>Proxecto de reparcelación do Sector 10</h4>
<a href="https://www.concellooroso.com/polsmar/reparcelacion/memoria.pdf">Memoria reparcelación</a>
</div><a href="formulario.pdf">Licenza</a><footer>2026</footer>'''


class OrosoTests(unittest.TestCase):
    def test_grouping_and_date_semantics(self):
        rows = parse_inventory(INVENTORY)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['fecha_aprob'], '2005-02-16')
        self.assertEqual(len(rows[1]['documentos']), 2)
        self.assertEqual(rows[1]['documentos'][1]['titulos_fuente'], ['I-13', 'COTAS-VIARIOS'])
        self.assertEqual(len(rows[2]['documentos']), 1)
        for row in rows:
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['geometry'])
            self.assertEqual(row['codigo_ine'], '15060')
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertNotIn('fase', rows[1])

    def test_missing_inventory_and_documents_fail(self):
        for html in ['<a href="formulario.pdf">Licenza</a>',
                     INVENTORY.replace('aprobado definitivamente na orde', 'publicado'),
                     INVENTORY.replace('/polsmar/reparcelacion/', '/outside/')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_frames_script_menus_maps_and_relative_urls(self):
        html = '''<frame src="menu.htm"><script>
submenu[1]='<a href="normativa/01.pdf">Normas Xerais</a> | <a href="planos/rural.htm">Rural</a>'
</script><map><area href="planos/02.pdf" alt="Plano 02"></map>
<a href="https://example.org/other.pdf">Outside</a>'''
        pages, docs = parse_pxom_page(html, LEGACY + 'index.htm')
        self.assertEqual(pages, {LEGACY + 'menu.htm', LEGACY + 'planos/rural.htm'})
        self.assertEqual({d['url'] for d in docs}, {LEGACY + 'normativa/01.pdf', LEGACY + 'planos/02.pdf'})
        self.assertTrue(all(d['source_urls'] == [LEGACY + 'index.htm'] for d in docs))

    def test_pagination_and_unknown_links_fail(self):
        for html in ['<a rel="next" href="page2">2</a>', '<a href="page2">Seguinte</a>',
                     '<script>submenu[1]="<a href=\'new.pdf\'>New syntax</a>"</script>',
                     '<a href="data.csv">New format</a>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_pxom_page(html, LEGACY + 'index.htm')

    def test_complete_traversal_cycles_and_document_dedup(self):
        pages = {SOURCE: INVENTORY, LEGACY + 'index.htm': '<frame src="menu.htm">',
                 LEGACY + 'menu.htm': '<a href="index.htm">Back</a><a href="a.pdf">Plan</a><a href="next.htm">More</a>',
                 LEGACY + 'next.htm': '<a href="a.pdf">Alternate label</a><a href="b.pdf">Other plan</a>'}
        adapter = OrosoAyuntamientoAdapter('oroso')
        visited = []
        def fetch(session, url):
            visited.append(url)
            return pages[url]
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=fetch), patch('municipio.adapters.oroso.time.sleep'):
            output = Path(directory) / 'projects.jsonl'
            result = adapter.backfill_proyectos(output)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(set(visited), set(pages))
        self.assertEqual(len(visited), len(pages))
        self.assertEqual(result['rows'], 3)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(len(rows[0]['documentos'][0]['source_urls']), 2)

    def test_failed_traversal_preserves_previous_snapshot(self):
        adapter = OrosoAyuntamientoAdapter('oroso')
        with tempfile.TemporaryDirectory() as directory, patch.object(adapter, '_fetch', side_effect=[INVENTORY, '<a rel="next" href="page2">2</a>']), patch('municipio.adapters.oroso.time.sleep'):
            output = Path(directory) / 'projects.jsonl'
            output.write_text('previous snapshot\n')
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot\n')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('oroso')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('15060', 'Oroso', 'A Coruña'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            result = OrosoAyuntamientoAdapter('oroso').backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
