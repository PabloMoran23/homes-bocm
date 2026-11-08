import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.palomares_del_rio import (
    PGOM, TRANSPARENCIA, PalomaresDelRioAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest

PREFIX = '/export/sites/palomaresdelrio/es/transparencia/.galleries/IND-53-/'


def block(title, *files):
    return '<div class="contentblock"><h3>' + title + '</h3>' + ''.join(
        '<a href="' + PREFIX + f + '">' + f + '</a>' for f in files) + '</div>'


class ParserTests(unittest.TestCase):
    def test_merge_stages_keep_instruments_separate(self):
        html = block('APROBACIÓN INICIAL PROYECTOS "CASA ALEGRE"', 'CASA/ANUNCIO.pdf')
        html += block('APROBACIÓN DEFINITIVA Modificación Ficha 10',
                      'CERT._PLENO_CASA_ALEGRE.pdf', 'APROB._ATU_CASA.pdf',
                      'APROB._MODF._FICHA_10.pdf')
        html += block('APROBACIÓN INICIAL INNOVACIÓN DÉCIMA', 'INICIAL/inicio.pdf')
        html += block('APROBACIÓN DEFINITIVA MODIFICACIÓN Nº 10', 'FINAL/final.pdf')
        rows = {r['id']: r for r in parse_inventory(html)}
        self.assertEqual(len(rows), 3)
        atu = rows['palomares-del-rio-casa-alegre-atu']
        ficha = rows['palomares-del-rio-casa-alegre-ficha-10']
        self.assertEqual(len(atu['documentos']), 3)
        self.assertFalse(any('MODF._FICHA' in d['url'] for d in atu['documentos']))
        self.assertFalse(any('_ATU_' in d['url'] for d in ficha['documentos']))
        self.assertEqual(len(rows['palomares-del-rio-innovacion-10']['documentos']), 2)
        for row in rows.values():
            for invented in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'fase'):
                self.assertNotIn(invented, row)

    def test_excludes_regulation_external_and_forms(self):
        html = block('CONSULTAS PREVIAS CREACION DE REGISTRO DE ENTIDADES URBANISTICAS', 'registro.pdf')
        html += block('APROBACIÓN ESTUDIO DETALLE EL VILLAREJO', 'VILLAREJO/plan.pdf')
        html += '<a href="https://example.org/plan.pdf">Plan</a>'
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 1)
        with self.assertRaises(ValueError):
            parse_inventory('<a href="formulario.pdf">Solicitud de licencia</a>')

    def test_fail_closed(self):
        for html in ('', block('NUEVO PLAN SIN REVISAR', 'nuevo.pdf'),
                     block('APROBACIÓN ESTUDIO DETALLE EL VILLAREJO'),
                     '<a rel="next" href="?p=2">2</a>',
                     '<a href="?page-inventario=2">2</a>',
                     '<div class="sg-download-gallery"><!-- resultSize: 11 --></div>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pgom_and_collector_total(self):
        html = ('<table><!-- listResultSize:1 --><a href="/export/sites/palomaresdelrio/'
                '.galleries/documentos-pgom/info.pdf">Plan General de Ordenación Municipal</a></table>')
        row = parse_inventory(html, PGOM)[0]
        self.assertEqual(row['id'], 'palomares-del-rio-pgom')
        with self.assertRaises(ValueError):
            parse_inventory(html.replace('Size:1', 'Size:2'), PGOM)

    def test_manifest_and_live_adapter_path(self):
        manifest = load_manifest('palomares-del-rio')
        self.assertEqual(manifest.provincia, 'Sevilla')
        self.assertFalse(manifest.licencias.enabled)
        responses = [Mock(url=TRANSPARENCIA, text=block('ESTUDIO DETALLE EL VILLAREJO', 'V/plan.pdf')),
                     Mock(url=PGOM, text='<table><a href="/export/sites/palomaresdelrio/.galleries/documentos-pgom/a.pdf">PGOM</a></table>')]
        with tempfile.TemporaryDirectory() as directory, patch(
                'municipio.adapters.palomares_del_rio.requests.Session') as session:
            session.return_value.__enter__.return_value.get.side_effect = responses
            path = Path(directory) / 'proyectos.jsonl'
            result = PalomaresDelRioAyuntamientoAdapter('palomares-del-rio').backfill_proyectos(path)
            self.assertEqual(result['count'], 2)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 2)


if __name__ == '__main__':
    unittest.main()
