import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.carbajosa_de_la_sagrada import (
    SOURCE, CarbajosaDeLaSagradaAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def page(body):
    return '<div class="margin-bottom-30"><h2>PLAN GENERAL DE ORDENACIÓN URBANA</h2>' + body + '</div>'


def link(title, path):
    return f'<p><a href="/docs/{path}.pdf">{title}</a></p>'


FIXTURE = page('''
<p>APROBADO DEFINITIVAMENTE POR ORDEN FYM/181/2017, DE 1 DE MARZO (BOCYL Nº 54 DE 20-03-2017)</p>
<ul><li><a href="https://drive.google.com/open?id=icon"><img src="icon.png"></a>
<a href="https://drive.google.com/file/d/memoria/view">TOMO I Memoria Vinculante</a></li></ul>
<p>PLAN PARCIAL DEL SECTOR SUR-I-1 (Aprobado definitivamente por Acuerdo de Pleno de 30/11/2017 y publicado en el BOCyL de 14/12/2017)</p>
''' + link('TOMO I. Información', 'plan1') + link('TOMO II. Normativa', 'plan2') + '''
<p>ESTUDIO DE DETALLE ASOCIADO A PROYECTO DE GASOLINERA C/ NEWTON, 15</p>
''' + link('Estudio Detalle', 'estudio') + '''
<p>ANUNCIO APROBACIÓN INICIAL ESTUDIO DE DETALLE ASOCIADO A PROYECTO DE GASOLINERA C/ NEWTON, 15 (Publicado en BOCyL nº 108 de 7/06/2019)</p>
''' + link('Anuncio inicial', 'inicial') + '''
<p>ANUNCIO APROBACIÓN DEFINITIVA ESTUDIO DE DETALLE ASOCIADO A PROYECTO DE GASOLINERA C/ NEWTON, 15 (Publicado en BOCyL nº 184 de 24/09/2019)</p>
''' + link('Acuerdo definitivo', 'definitivo') + '''
<p>ANUNCIO APROBACIÓN DEFINITIVA CONVENIO URBANÍSTICO DE GESTIÓN AANU-16</p>
''' + link('Convenio', 'convenio') + '''
<p>APROBACIÓN DEFINITIVA PROYECTO DE NORMALIZACIÓN SUR-AE-PAS-1 LOS PAÚLES:</p>
''' + link('Proyecto Los Paúles', 'paules'))


class ParserTests(unittest.TestCase):
    def test_groups_instruments_and_retains_documents(self):
        rows = parse_inventory(FIXTURE)
        self.assertEqual(len(rows), 4)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2, 3, 1])
        self.assertEqual(len({r['id'] for r in rows}), 4)
        docs = [d for r in rows for d in r['documentos']]
        self.assertFalse(any('icon' in d['url'] or 'convenio' in d['url'] for d in docs))
        self.assertTrue(all(d['provenance_url'] == SOURCE for d in docs))
        self.assertTrue(all('https://' in d['url'] for d in docs))

    def test_date_semantics(self):
        rows = parse_inventory(FIXTURE)
        self.assertEqual(rows[0]['fecha_publicacion'], '2017-03-20')
        self.assertIsNone(rows[0]['fecha_aprob'])  # textual March date not guessed
        self.assertEqual(rows[1]['fecha_acuerdo'], '2017-11-30')
        self.assertEqual(rows[1]['fecha_publicacion'], '2017-12-14')
        self.assertEqual(rows[2]['fecha_publicacion'], '2019-09-24')
        self.assertIsNone(rows[2]['fecha_aprob'])
        self.assertEqual(rows[2]['fase'], 'aprobación definitiva')
        self.assertIn('7/06/2019', rows[2]['documentos'][1]['contexto'])
        self.assertIsNone(rows[3]['fecha_publicacion'])
        self.assertTrue(all(r['lat'] is None and r['lon'] is None for r in rows))

    def test_fail_closed(self):
        for html in ('<p>Solicitud de licencia</p>', page(''),
                     FIXTURE + '<a rel="next" href="?page=2">Next</a>',
                     FIXTURE.replace('/docs/plan1.pdf', 'https://untrusted.example/a.pdf')):
            with self.subTest(html=html[:100]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_adapter_contract_and_manifest(self):
        manifest = load_manifest('carbajosa-de-la-sagrada')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, CarbajosaDeLaSagradaAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '37085')
        self.assertEqual(raw['provincia'], 'Salamanca')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(raw['licencias']['enabled'])
        response = Mock(url=SOURCE, text=FIXTURE)
        direct = CarbajosaDeLaSagradaAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as directory, patch(
                'municipio.adapters.carbajosa_de_la_sagrada.requests.get', return_value=response):
            output = Path(directory) / 'proyectos.jsonl'
            result = direct.backfill_proyectos(output)
            first = output.read_text()
            self.assertEqual(result['count'], 4)
            self.assertEqual(len([json.loads(r) for r in first.splitlines()]), 4)
            direct.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(output.read_text(), first)
            direct.backfill_licencias(output)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
