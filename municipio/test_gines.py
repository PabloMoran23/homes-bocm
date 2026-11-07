import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.gines import (
    BASE_URL, GinesAyuntamientoAdapter, discover_inventories, parse_inventory,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

PGOU = BASE_URL + 'transparencia/indicadores-de-transparencia/indicador/P.G.O.U.-APROBADO-DEFINITIVAMENTE-2014.-00001/'
MOD = BASE_URL + 'transparencia/indicadores-de-transparencia/indicador/Modificaciones-al-P.G.O.U.-de-Gines-que-no-afectan-a-su-ordenacion-estructural./'
INDEX = f'<a href="{PGOU}">PGOU</a><a href="{MOD}">Modificaciones</a><a href="{PGOU}">duplicado</a>'


def gallery(title='P.G.O.U. de Gines', names=('Memoria', 'Planos')):
    links = ''.join(f'<a href="/export/sites/gines/es/transparencia/.galleries/IND-50-/{n}.pdf">{n}</a>' for n in names)
    return f'<h1>{title}</h1><div class="sg-download-gallery">{links}</div>'


class GinesTests(unittest.TestCase):
    def test_discovery_and_missing_sources(self):
        self.assertEqual(discover_inventories(INDEX), {'pgou': PGOU, 'modificaciones': MOD})
        with self.assertRaises(ValueError):
            discover_inventories('<a href="/solicitud.pdf">Licencia</a>')

    def test_grouping_deduplication_and_semantics(self):
        row = parse_inventory(gallery(names=('Memoria', 'Planos', 'Memoria')), PGOU, 'pgou')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '41047')
        self.assertTrue(all(d['source_url'] == PGOU for d in row['documentos']))
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, row)
        mod = parse_inventory(gallery('Modificaciones al P.G.O.U. de Gines', ('Modificacion',)), MOD, 'modificaciones')
        self.assertNotEqual(row['id'], mod['id'])
        self.assertEqual(len(mod['documentos']), 1)

    def test_source_changes_fail_loudly(self):
        for html in ('<h1>Formulario de licencia</h1>', gallery(names=()),
                     gallery() + '<div class="pagination"><a href="?page=2">2</a></div>',
                     gallery().replace('/export/sites/gines/', 'https://unrelated.example/')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, PGOU, 'pgou')

    def test_manifest_and_snapshot_integration(self):
        adapter = load_portal_adapter(load_manifest('gines'))
        self.assertIsInstance(adapter, GinesAyuntamientoAdapter)
        pages = [INDEX, gallery(), gallery('Modificaciones al P.G.O.U. de Gines')]
        responses = [Mock(content=p.encode(), url=u) for p, u in zip(pages, (BASE_URL, PGOU, MOD))]
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.gines.requests.Session') as session:
            session.return_value.__enter__.return_value.get.side_effect = responses
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(out)
            self.assertEqual(result['count'], 2)
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)
            self.assertEqual(session.return_value.__enter__.return_value.get.call_count, 3)


if __name__ == '__main__':
    unittest.main()
