from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from municipio.adapters.aielo_de_malferit import (
    ACTUACIONES_URL, PGOU_URL, AieloDeMalferitAyuntamientoAdapter,
    parse_actuaciones, parse_pgou,
)
from municipio.manifest import load_manifest, load_yaml


PGOU = """
<a href='/files/320/navigation.pdf'>Unrelated navigation</a>
<div id='preview'><div class='box'><h3>Descripció</h3>
<div class='contenido'><strong>Pla General d'Ordenació Urbana</strong></div></div></div>
<div id='preview'><div class='box'><h3>DOCUMENTS Descarregables</h3>
<div class='contenido'><a href='http://aielodemalferit.es/files/320/normes.pdf'><img></a>
<a href='https://aielodemalferit.es/files/320/normes.pdf'>Normes</a>
<h3>MODIFICACIÓ 1 PGOU: Revisió d'usos</h3>
<a href='/files/320/memoria.pdf'>Memòria (15/11/2021)</a>
<a href='/files/320/edicte.pdf'>Informació pública aprovació inicial (17/12/2021)</a>
<h3>MODIFICACIÓ 2 PGOU: Altres usos</h3>
<a href='/files/320/mod2.pdf'>Text</a>
</div></div></div>
"""
ACTUACIONES = """
<div id='preview'><div class='box'>
<h3>Programa actuació aïllada Carrer Font de la Figuera</h3>
<div class='contenido'><h2>PROJECTE D'URBANITZACIÓ</h2>
<a href='/files/259/1.pdf'>Memòria</a><a href='/files/259/2.pdf'>Plànol</a>
<h2>PROGRAMA D'ACTUACIÓ AÏLLADA</h2><a href='/files/259/8.pdf'>Programa</a>
<h2>ACORD D'APROVACIÓ DE LA JUNTA DE GOVERN LOCAL</h2>
<a href='/files/259/9.pdf'>Certificat de l'acord</a></div></div>
<div class='box'><h3>Sol·licitud de llicència</h3><div class='contenido'>
<a href='/files/259/form.pdf'>Imprès</a></div></div></div>
"""


class AieloParserTests(unittest.TestCase):
    def test_group_documents_by_instrument_not_by_pdf(self):
        rows = parse_pgou(PGOU)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2, 1])
        self.assertEqual(rows[0]['titulo'], "Pla General d'Ordenació Urbana")
        self.assertEqual(rows[1]['documentos'][0]['titulo'], 'Memòria (15/11/2021)')
        self.assertTrue(rows[2]['documentos'][0]['url'].endswith('/mod2.pdf'))
        self.assertEqual(len({r['id'] for r in rows}), 3)
        self.assertEqual(rows, parse_pgou(PGOU))

    def test_programme_keeps_project_and_agreement_together(self):
        rows = parse_actuaciones(ACTUACIONES)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 4)
        self.assertEqual(rows[0]['documentos'][-1]['seccion'],
                         "ACORD D'APROVACIÓ DE LA JUNTA DE GOVERN LOCAL")
        self.assertFalse(any('form.pdf' in d['url'] for d in rows[0]['documentos']))

    def test_provenance_and_no_inferred_dates_or_location(self):
        rows = parse_pgou(PGOU) + parse_actuaciones(ACTUACIONES)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '46042')
            self.assertFalse(row['publication_ready'])
            for field in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion',
                          'lat', 'lon', 'geometry', 'fase']:
                self.assertNotIn(field, row)
            for doc in row['documentos']:
                self.assertIn(doc['inventory_url'], (PGOU_URL, ACTUACIONES_URL))
                self.assertTrue(doc['url'].startswith('https://'))
                self.assertIn('source_url', doc)

    def test_image_link_has_filename_fallback_and_original_http(self):
        row = parse_pgou(PGOU.replace(
            "<a href='https://aielodemalferit.es/files/320/normes.pdf'>Normes</a>", ''))[0]
        doc = row['documentos'][0]
        self.assertEqual(doc['titulo'], 'normes.pdf')
        self.assertEqual(doc['titulo_origen'], 'filename')
        self.assertTrue(doc['source_url'].startswith('http://'))

    def test_layout_empty_groups_pagination_and_foreign_documents_fail(self):
        invalid = [
            '<html>Unavailable</html>',
            PGOU.replace('DOCUMENTS Descarregables', 'Unknown'),
            PGOU.replace("<a href='/files/320/mod2.pdf'>Text</a>", ''),
            PGOU + '<a rel="next" href="?page=2">Next</a>',
            PGOU + '<a href="?offset=10">More</a>',
            PGOU + '<div class="pagination">2</div>',
            PGOU.replace('/files/320/mod2.pdf', 'https://example.org/other.pdf'),
            PGOU.replace('MODIFICACIÓ 2 PGOU: Altres usos', 'Unknown grouping'),
        ]
        for html in invalid:
            with self.subTest(html=html[-100:]), self.assertRaises(ValueError):
                parse_pgou(html)
        with self.assertRaises(ValueError):
            parse_actuaciones(ACTUACIONES.replace('Programa actuació aïllada', 'Imprès'))

    def test_manifest_identity_and_disabled_features(self):
        manifest = load_manifest('aielo-de-malferit')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '46042')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertEqual(manifest.portal.adapter,
                         'municipio.adapters.aielo_de_malferit:AieloDeMalferitAyuntamientoAdapter')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)

    @patch('municipio.adapters.aielo_de_malferit.requests.Session')
    def test_adapter_live_path_and_update_snapshot(self, session_cls):
        session = session_cls.return_value.__enter__.return_value
        def get(url, **kwargs):
            self.assertEqual(kwargs['timeout'], 45)
            html = PGOU if url == PGOU_URL else ACTUACIONES
            return Mock(url=url, text=html, content=html.encode())
        session.get.side_effect = get
        adapter = AieloDeMalferitAyuntamientoAdapter(slug='aielo-de-malferit')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'rows.jsonl'
            summary = adapter.backfill_proyectos(out)
            self.assertEqual(summary['count'], 4)
            before = out.read_text()
            self.assertEqual(len([json.loads(line) for line in before.splitlines()]), 4)
            adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(out.read_text(), before)
            # A failure in the second source must not write a partial snapshot.
            session.get.side_effect = [get(PGOU_URL, timeout=45), requests.Timeout('unavailable')]
            with self.assertRaises(requests.Timeout):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), before)
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
