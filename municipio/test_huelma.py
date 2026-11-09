import unittest

from municipio.adapters.huelma import inventory_url, parse_inventory
from municipio.manifest import load_manifest

PDF = '''MUNICIPIO:                   043. HORNOS
Estudio de Detalle             Otro municipio                     Ap. Inicial
MUNICIPIO:                   044. HUELMA
Figura                        Ámbito                              Acuerdo
Estudio de Detalle             U.A. 5 "Los lavaderos"              Ap. inicial     26/01/2002   11/12/2001
                                                                  Ap. definitiva  26/03/02     04/03/02
                               Reparcelacion finca nº40             A.Definitiva     4/7/17      15/6/17
Ordenanza fiscal               Licencias urbanisticas              Ap. Inicial
Proyecto Urbanización          U.E. 12                             Ap. Inicial     13/09/2005   22/08/2005
10/09/2026
13:17
91
\f                               Ap. Definitiva                     12/01/06     22/12/05
Proyecto Reparcelación         U.E. 12                             Ap. Inicial     13/09/2005   22/08/2005
Estudio de Detalle             U.A. 5 "Los lavaderos"              Ap. definitiva  26/03/02     04/03/02
NN.SS.                         Proyecto de reparcelación de las fincas       Ap.Inicial
                               número 26, 27, 28, manzana C,                  Ap.definitiva
                               del Polígono Industrial "Los Retiros".
MUNICIPIO:                   045. HUESA
Estudio de Detalle             Fuera de Huelma                      Ap. definitiva
'''
URL = 'https://www.dipujaen.es/inventory.pdf'


class HuelmaTests(unittest.TestCase):
    def test_section_pages_grouping_and_semantics(self):
        rows = parse_inventory(PDF, URL)
        self.assertEqual(len(rows), 4)
        study = next(r for r in rows if r['tipo'] == 'Estudio de Detalle')
        self.assertEqual(len(study['texto_fuente']), 2)
        self.assertNotIn('finca', study['titulo'])
        self.assertIn('Reparcelacion finca', study['texto_fuente'][0])
        urban = next(r for r in rows if r['tipo'] == 'Proyecto de Urbanización')
        self.assertIn('12/01/06', urban['texto_fuente'][0])
        self.assertTrue(any('número 26, 27, 28, manzana C' in r['titulo'] for r in rows))
        for row in rows:
            self.assertNotIn('Fuera de Huelma', row['titulo'])
            self.assertEqual(row['codigo_ine'], '23044')
            self.assertEqual(row['documentos'][0]['url'], URL)
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['lat'])
            self.assertFalse(row['publication_ready'])

    def test_fail_closed_on_wrong_or_truncated_section(self):
        for text in ('', PDF.replace('044. HUELMA', '044. OTRO'), PDF.split('MUNICIPIO:                   045.')[0],
                     PDF.replace('Estudio de Detalle', 'Ordenanza').replace('Proyecto', 'Ordenanza')):
            with self.assertRaises(ValueError):
                parse_inventory(text, URL)

    def test_inventory_discovery_current_link_and_ambiguity(self):
        html = '<a href="/new-2027.pdf">Desarrollo del Planeamiento de la Provincia</a>'
        self.assertEqual(inventory_url(html), 'https://www.dipujaen.es/new-2027.pdf')
        for value in ('', html.replace('/new-2027.pdf', 'https://example.org/file.pdf'),
                      html + html.replace('new-2027', 'other')):
            with self.assertRaises(ValueError):
                inventory_url(value)

    def test_manifest(self):
        manifest = load_manifest('huelma')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Jaén')
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.huelma:HuelmaAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
