import unittest
from municipio.adapters.cullar_vega import CullarVegaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

HTML = '''<div class="post_content"><h2>DESCARGAS</h2>
<a href="/licencia.pdf">Declaración responsable</a>
<h2>NORMAS SUBSIDIARIAS</h2>
<p>Las Normas Subsidiarias de Cúllar Vega tiene su aprobación definitiva con fecha 30/marzo/2001
<a href="/nnss.pdf">Revisión de las Normas Subsidiarias</a></p>
<ul><li>Texto íntegro Normas Subsidiarias: <a href="https://bop2.dipgra.es/2009">BOP nº 77 de 24 de abril de 2009</a></li>
<li>Texto íntegro Adaptación Parcial Normas Subsidiarias a la LOUA: <a href="https://bop2.dipgra.es/2011">BOP nº26 de 8 de febrero de 2011</a></li></ul>
<a href="/map.pdf">Descarga: Zonificacion-usos-Cullar</a>
<a href="/map.pdf">Descarga: Zonificacion-usos-Cullar</a>
<hr><p>PLAN GENERAL DE ORDENACIÓN MUNICIPAL DE CÚLLAR VEGA</p><ol><li>Aprobación Definitiva</li></ol></div>'''


class ParserTests(unittest.TestCase):
    def test_instruments_grouping_and_date_semantics(self):
        nnss, adaptation = Adapter.parse_projects(HTML)
        self.assertEqual(nnss['fecha_aprob'], '2001-03-30')
        self.assertEqual(nnss['fecha_publicacion'], '2009-04-24')
        self.assertEqual(adaptation['fecha_publicacion'], '2011-02-08')
        self.assertIsNone(adaptation['fecha_aprob'])
        self.assertIsNone(adaptation['fase'])
        self.assertEqual(len(nnss['documentos']), 3)
        self.assertEqual(len(adaptation['documentos']), 1)
        self.assertIsNone(nnss['fecha_acuerdo'])
        self.assertIsNone(nnss['geometry'])
        self.assertFalse(any('licencia.pdf' in d['url'] for r in (nnss, adaptation) for d in r['documentos']))

    def test_missing_dates_are_not_inferred(self):
        rows = Adapter.parse_projects(HTML.replace('30/marzo/2001', '').replace('24 de abril de 2009', ''))
        self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertIsNone(rows[0]['fecha_publicacion'])

    def test_reject_changed_inventory_or_navigation(self):
        for html in ('<a>Urbanismo</a>', HTML.replace('NORMAS SUBSIDIARIAS', 'Otro inventario'), HTML.replace('Revisión de las Normas Subsidiarias', 'Formulario')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_reject_pagination_and_unexpected_document_hosts(self):
        for html in (HTML + '<a rel="next" href="/page/2">2</a>', HTML + '<a href="/page/2">Siguiente</a>', HTML.replace('/nnss.pdf', 'https://example.org/a.pdf')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_identity_stable_across_link_changes(self):
        first = Adapter.parse_projects(HTML)
        second = Adapter.parse_projects(HTML.replace('/nnss.pdf', '/revised.pdf'))
        self.assertEqual([r['id'] for r in first], [r['id'] for r in second])

    def test_manifest_integration(self):
        manifest = load_manifest('cullar-vega')
        self.assertEqual(manifest.provincia, 'Granada')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), Adapter)


if __name__ == '__main__':
    unittest.main()
