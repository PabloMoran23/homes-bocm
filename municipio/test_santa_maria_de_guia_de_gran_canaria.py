import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.santa_maria_de_guia_de_gran_canaria import (
    SOURCE, SantaMariaDeGuiaDeGranCanariaAdapter, enrich_pgo, parse_inventory,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def tr(a='', b='', c='', d=''):
    return '<tr>' + ''.join('<td>' + x + '</td>' for x in (a, b, c, d)) + '</tr>'


def pdf(name):
    return '<a href="/wp-content/uploads/' + name + '.pdf">' + name + '</a>'


INVENTORY = '<table>' + ''.join([
    tr('Planeamiento en Trámite', '', 'Solicitud', pdf('no-licencia')),
    tr('Planeamiento Aprobado', '<a href="http://www.plangeneralguiagc.es/PGO2017/inicio.html">Plan General en Vigor</a>'),
    tr('', 'Planes Especiales', 'Peri La Atalaya', pdf('normas')),
    tr('', '', '', pdf('plano') + pdf('plano')),
    tr('', '', 'Pepri Guía', pdf('catalogo')),
    tr('', '', '', pdf('ordenanzas')),
    tr('Normas y Ordenanzas Municipales en Vigor', '', '', pdf('general')),
]) + '</table>'
PGO = '''<p>El Plan General de Ordenación de Santa María de Guía fue aprobado definitivamente
 en sesión celebrada el 8 de mayo de 2017 y tras la publicación íntegra de su normativa
 en el Boletín Oficial de la Provincia de 30 de Junio de 2017, tuvo su entrada en vigor
 el día 21 de Julio de 2017.</p><a href="ESTRUCTURA DOCUMENTO.pdf">Índice</a>
 <a href="ANEXOS\\correccion.pdf">Corrección</a>'''


class PlanningTests(unittest.TestCase):
    def test_grouping_boundaries_and_deduplication(self):
        rows = parse_inventory(INVENTORY)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [0, 2, 2])
        self.assertEqual(rows[1]['titulo'], 'Peri La Atalaya')
        self.assertTrue(all(r['fecha_aprob'] is None for r in rows))
        self.assertNotIn('no-licencia', json.dumps(rows))
        self.assertNotIn('general.pdf', json.dumps(rows))
        self.assertEqual(rows, parse_inventory(INVENTORY))

    def test_semantic_dates_and_document_provenance(self):
        row = parse_inventory(INVENTORY)[0]
        enrich_pgo(row, PGO)
        self.assertEqual(row['fecha_acuerdo'], '2017-05-08')
        self.assertEqual(row['fecha_publicacion'], '2017-06-30')
        self.assertEqual(row['fecha_entrada_vigor'], '2017-07-21')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertIn('ESTRUCTURA%20DOCUMENTO.pdf', row['documentos'][0]['url'])
        self.assertIn('/ANEXOS/correccion.pdf', row['documentos'][1]['url'])
        self.assertEqual(row['documentos'][0]['source_url'], row['url'])
        with self.assertRaises(ValueError):
            enrich_pgo(copy.deepcopy(row), PGO.replace('fue aprobado definitivamente', 'en tramitación'))

    def test_fail_closed_on_changed_inventory_or_pagination(self):
        for html in ['', INVENTORY.replace('Pepri Guía', 'Plan Nuevo'),
                     INVENTORY + '<a rel="next" href="?page=2">2</a>',
                     INVENTORY + '<div class="pagination">2</div>',
                     INVENTORY.replace('Peri La Atalaya', '')]:
            with self.subTest(html=html[-80:]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_manifest_and_adapter_output(self):
        manifest = load_manifest('santa-maria-de-guia-de-gran-canaria')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '35023')
        self.assertEqual(manifest.provincia, 'Las Palmas')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INVENTORY, PGO]):
                result = adapter.backfill_proyectos(output)
            self.assertEqual(result['rows'], 3)
            self.assertEqual(len(output.read_text().splitlines()), 3)
            adapter.backfill_licencias(Path(td) / 'licencias.jsonl')
            self.assertEqual((Path(td) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
