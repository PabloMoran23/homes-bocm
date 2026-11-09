"""Offline parser checks; synthetic markup, never synthetic output records."""
import unittest

from municipio.adapters.dalias import (
    BASE, SOURCE, group_instruments, inventory_links, inventory_soup, parse_detail,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def page(title='PLANOS', category='Normas Subsidiarias', attachment='Plano', doc='plan.pdf'):
    return f'''<h1>{title}</h1><div id="doc-lectura-cultura">
    <div class="left"><h2>Ayuntamiento de Dalías</h2>
    <p>Territorio - Planeamiento Urbanístico - {category}</p></div>
    <div class="right">Publicado: <strong>15/01/2025</strong></div>
    <table id="attachments"><tr><td><a href="/Servicios/Tablon/anexos.nsf/A/$file/{doc}">{attachment}</a></td>
    <td><a href="/Servicios/Tablon/anexos.nsf/A/$file/{doc}">[descargar]</a></td></tr></table></div>'''


def inventory(body=''):
    return '<form class="xspForm"><table class="xspDataTable">' + body + '</table></form>'


class DaliasParserTests(unittest.TestCase):
    def test_group_documents_and_keep_page_dates(self):
        a = parse_detail(page(), BASE + '/a')
        b = parse_detail(page('MEMORIA', attachment='Memoria', doc='memoria.pdf'), BASE + '/b')
        c = parse_detail(page(category='Adaptacion Parcial NNSS'), BASE + '/c')
        rows = group_instruments([a, b, c])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['fichas']), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['documentos'][1]['source_url'], BASE + '/b')
        self.assertEqual(rows[0]['fichas'][0]['fecha_publicacion'], '2025-01-15')
        self.assertEqual(rows[0]['codigo_ine'], '04038')
        for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, rows[0])

    def test_separate_detail_instruments(self):
        cat = 'Estudios de Detalle Ajuste de Alineaciones'
        rows = group_instruments([parse_detail(page('Calle 37', cat), BASE + '/37'),
                                  parse_detail(page('Calle 46', cat, doc='46.pdf'), BASE + '/46')])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])

    def test_unrelated_form_excluded(self):
        html = page('Solicitud de licencia').replace('Territorio - Planeamiento Urbanístico - Normas Subsidiarias',
                                                     'Territorio - Urbanismo - Formularios')
        self.assertIsNone(parse_detail(html, BASE + '/form'))

    def test_solar_requires_project_document(self):
        html = page('INSTALACION SOLAR FOTOVOLTÁICA DE AUTOCONSUMO EN SUELO RÚSTICO', attachment='Proyecto de Actuacion')
        html = html.replace('Planeamiento Urbanístico - Normas Subsidiarias',
                            'Urbanismo - Autorización para actuaciones extraordinarias de interés público en suelo rústico')
        self.assertEqual(parse_detail(html, BASE + '/solar')['tipo'], 'proyecto_actuacion')
        with self.assertRaises(ValueError):
            parse_detail(html.replace('Proyecto de Actuacion', 'Anuncio'), BASE + '/solar')

    def test_fail_closed_layout_municipality_documents(self):
        for html in ('<title>Login</title>', page().replace('Dalías', 'Otro'),
                     page().replace('/Servicios/Tablon/anexos.nsf/', '/forms/'),
                     page().replace('15/01/2025', 'invalid'),
                     page(category='Nueva categoria')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_detail(html, BASE + '/a')
        with self.assertRaises(ValueError):
            group_instruments([])

    def test_pagination_and_collapsed_tree_rejected(self):
        for body in ('<button title="plegado Normas"></button>',
                     '<button title="collapsed Normas"><img src="/theme/expand.gif"></button>',
                     '<span class="xspPagerLeft"><a>2</a></span>',
                     '<a href="?page=2" rel="next">Más</a>'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                inventory_links(inventory(body))
        with self.assertRaises(ValueError):
            inventory_soup('<h1>Login</h1>')

    def test_inventory_deduplication_and_host_guard(self):
        link = '<a href="/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Dalias&amp;documentId=' + 'A' * 32 + '">Plan</a>'
        self.assertEqual(len(inventory_links(inventory(link + link))), 1)
        with self.assertRaises(ValueError):
            inventory_links(inventory(link.replace('/Servicios/', 'https://other.example/Servicios/')))

    def test_archived_attachments_retained_with_provenance(self):
        html = page().replace('anexos.nsf', 'archivadoanexos_1.nsf')
        detail = parse_detail(html, BASE + '/archived')
        document = detail['documentos'][0]
        self.assertTrue(document['archivado'])
        self.assertEqual(document['fecha_publicacion_ficha'], '2025-01-15')
        self.assertNotIn('fecha_publicacion', document)
        from municipio.entity_policy import classify
        row = group_instruments([detail])[0]
        self.assertEqual(classify(row)['entity_type'], 'documento')

    def test_manifest_and_adapter_contract(self):
        manifest = load_manifest('dalias')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '04038')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(load_portal_adapter(manifest).slug, 'dalias')


if __name__ == '__main__':
    unittest.main()
