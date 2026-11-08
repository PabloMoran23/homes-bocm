import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, Mock

from municipio.adapters.olivares import SOURCES, OlivaresAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def gallery(title, *names):
    links = ''.join(f'<h4 class="title-element"><a href="/export/sites/olivares/es/transparencia/.galleries/IND-53-/{name}.pdf">{name}</a></h4>' for name in names)
    return f'<section class="gallery"><h4 class="gallery-title">{title}</h4>{links}</section>'


def article(content):
    return f'<article class="sg-indicador-trans">{content}</article>'


class OlivaresTests(unittest.TestCase):
    def test_grouping_and_exclusions(self):
        html = article(
            gallery('MODIFICACION Nº 14 PGOU', 'aprobacion-definitiva')
            + gallery('Modificación Nº 12 PGOU de Olivares', 'memoria', 'planos', 'ambiental')
            + gallery('MODIFICACIÓN DEL PROYECTO DE REPARCELACIÓN DE LA UR-10', 'inicial', 'definitiva')
            + gallery('DOCUMENTOS EN INFORMACIÓN PÚBLICA', 'ur-10', 'Planos')
            + gallery('EXPROPIACIÓN AVDA. ESTADIO 29', 'anuncio')
            + gallery('Solicitud de licencia de obras', 'formulario')
        )
        rows = parse_inventory(html, SOURCES[1])
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 3, 2])
        self.assertIn('/memoria.pdf', rows[1]['documentos'][0]['url'])
        self.assertTrue(all(r['codigo_ine'] == '41067' for r in rows))
        self.assertTrue(all(r['fecha_aprob'] is None and r['fecha_publicacion'] is None and r['fase'] is None and r['lat'] is None for r in rows))
        # Stable identity does not depend on document order or approval captions.
        changed = parse_inventory(article(gallery('Modificación Nº 12 PGOU de Olivares', 'nuevo')), SOURCES[1])
        self.assertEqual(changed[0]['id'], rows[1]['id'])

    def test_fail_closed(self):
        good = gallery('MODIFICACION Nº 14 PGOU', 'documento')
        for html in ('', article(gallery('Solicitud', 'formulario')), article(good + '<a rel="next" href="?page=2">2</a>'), article(good + '<a href="?searchPage=2">2</a>'), article(gallery('MODIFICACION Nº 14 PGOU')), article(good.replace('/export/sites/', 'https://example.org/export/sites/'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, SOURCES[1])

    def test_uz10b_and_pgou(self):
        row = parse_inventory(article(gallery('PROYECTO DE DELIMITACIÓN DE DOS UNIDADES DE EJECUCIÓN EN LA UNIDAD DE EJECUCIÓN UZ-10B DEL PGOU DE OLIVARES (SEVILLA).', 'delimitacion')), SOURCES[2])[0]
        self.assertEqual(row['tipo'], 'proyecto de delimitación')
        pgou = article('<section class="gallery"><h4 class="gallery-title">PLAN GENERAL DE ORDENACIÓN URBANÍSTICA DE OLIVARES</h4><h4 class="title-element"><a href="http://3web.dipusevilla.es/planeamiento/OlivaresPGOU/67PGad%20.htm">PGOU</a></h4></section>')
        self.assertEqual(parse_inventory(pgou, SOURCES[0])[0]['tipo'], 'PGOU')

    def test_adapter_snapshot_and_manifest(self):
        manifest = load_manifest('olivares')
        self.assertIsInstance(load_portal_adapter(manifest), OlivaresAyuntamientoAdapter)
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / 'rows.jsonl'
            def fetch(url, **kwargs):
                i = SOURCES.index(url)
                return Mock(url=url, text=article(gallery(f'MODIFICACION Nº {i + 12} PGOU', 'memoria')))
            adapter = OlivaresAyuntamientoAdapter('olivares')
            with patch('municipio.adapters.olivares.requests.get', side_effect=fetch) as get:
                result = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(get.call_count, 3)
            self.assertEqual(result['count'], 3)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 3)
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
