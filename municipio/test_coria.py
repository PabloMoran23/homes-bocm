import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.coria import CoriaAyuntamientoAdapter, parse_inventory, parse_notice
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


INVENTORY = '''<h1>Plan General Municipal y PEPCH</h1><div class="entry-content">
<div><h3>Documentación</h3><p>2 AVANCE DEL PLAN (Diciembre 2025)</p>
<p><a href="/doc/ordenacion.pdf">02 Memoria de la Ordenación Urbanística</a></p>
<p><a href="/doc/pech.pdf">05 Plan Especial del Casco Histórico de Coria</a></p>
<p><a href="/doc/die.pdf">06 Documento Inicial Estratégico</a>Huella: abc</p>
<p><a href="/doc/die.pdf">06 Memoria de Participación Ciudadana</a>Huella: def</p>
</div></div><nav><a href="/licencia.pdf">Solicitud de licencia</a></nav>'''
NOTICE = '''<p>AYUNTAMIENTO DE CORIA</p>
<p>ANUNCIO de 19 de febrero de 2026</p>
<p>Fecha Publicación: jueves, 05 de marzo de 2026</p>
<p>Aprobado inicialmente por el Ayuntamiento-Pleno, en sesión ordinaria de 21 de enero de 2026,
el documento de avance del Plan General Municipal de Coria y el documento inicial estratégico</p>
<a href="/pdfs/doe/2026/440o/26080310.pdf">PDF</a>'''


class CoriaTests(unittest.TestCase):
    def test_grouping_and_link_aliases(self):
        rows = parse_inventory(INVENTORY, parse_notice(NOTICE))
        self.assertEqual(len(rows), 2)
        pgm, pech = rows
        self.assertEqual(len(pgm['documentos']), 4)
        self.assertEqual(len(pech['documentos']), 1)
        self.assertEqual(pgm['documentos'][1]['url'], pgm['documentos'][2]['url'])
        self.assertNotEqual(pgm['documentos'][1]['metadata_fuente'], pgm['documentos'][2]['metadata_fuente'])
        self.assertFalse(any('licencia' in d['url'] for r in rows for d in r['documentos']))

    def test_date_semantics_and_missing_geometry(self):
        pgm, pech = parse_inventory(INVENTORY, parse_notice(NOTICE))
        self.assertEqual(pgm['fecha_acuerdo'], '2026-01-21')
        self.assertEqual(pgm['fecha_publicacion'], '2026-03-05')
        self.assertIsNone(pgm['fecha_aprob'])
        self.assertIsNone(pech['fecha_acuerdo'])
        for r in (pgm, pech):
            self.assertIsNone(r['geometry'])
            self.assertIsNone(r['lat'])
            self.assertFalse(r['publication_ready'])

    def test_fail_closed_on_missing_or_wrong_sources(self):
        for html in ('<h1>Login</h1>', INVENTORY.replace('Ordenación Urbanística', 'Solicitud')):
            with self.assertRaises(ValueError):
                parse_inventory(html, parse_notice(NOTICE))
        for html in (NOTICE.replace('CORIA', 'OTRO'), NOTICE.replace('21 de enero de 2026', 'sin fecha')):
            with self.assertRaises(ValueError):
                parse_notice(html)

    def test_no_silent_pagination(self):
        with self.assertRaises(ValueError):
            parse_inventory(INVENTORY + '<a rel="next" href="/page/2">Más</a>', parse_notice(NOTICE))

    def test_all_document_links_and_stable_identity(self):
        extra = '<p><a href="/doc/nuevo.pdf">Anexo nuevo</a></p>'
        modified = INVENTORY.replace('</div></div>', extra + '</div></div>')
        original = parse_inventory(INVENTORY, parse_notice(NOTICE))
        rows = parse_inventory(modified, parse_notice(NOTICE))
        self.assertEqual([r['id'] for r in original], [r['id'] for r in rows])
        self.assertEqual(len(rows[0]['documentos']), len(original[0]['documentos']) + 1)
        with self.assertRaises(ValueError):
            parse_inventory(INVENTORY.replace('/doc/pech.pdf', 'https://example.org/pech.pdf'), parse_notice(NOTICE))

    def test_adapter_refresh_and_disabled_licences(self):
        adapter = CoriaAyuntamientoAdapter('coria')
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, NOTICE]):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len(output.read_text().splitlines()), 2)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest_loads(self):
        manifest = load_manifest('coria')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '10067')
        self.assertEqual(manifest.provincia, 'Cáceres')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), CoriaAyuntamientoAdapter)


if __name__ == '__main__':
    unittest.main()
