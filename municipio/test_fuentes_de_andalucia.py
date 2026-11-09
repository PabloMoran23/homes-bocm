import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.fuentes_de_andalucia import (
    SOURCE, PROVENANCE, FuentesDeAndaluciaAyuntamientoAdapter,
    parse_inventory, parse_provenance,
)

ARTICLE = f'''<article><h1>Plan Básico de Ordenación Municipal</h1>
<time datetime="2026-06-24"></time><a href="{SOURCE}">Web del PBOM</a></article>'''
INVENTORY = '''<title>PBOM de Fuentes de Andalucía</title>
<p>Plan Básico de Ordenación Municipal</p>
<div class="eb-progressbar-title">FASE ACTUAL: 3</div>
<h2>APROBACIÓN DEFINITIVA DEL PLAN</h2><p>Se dispondrán los documentos.</p>
<a href="/wp-content/uploads/2026/01/diagnostico.pdf">Diagnóstico previo</a>
<a href="/wp-content/uploads/2024/06/manual.pdf">Manual de participación</a>
<a href="/wp-content/uploads/2024/06/manual.pdf">Manual de participación</a>
<a href="https://we.tl/t-example">Planos</a>
<a href="https://otro-municipio.es/plan.pdf"><img src="logo.png"></a>
<a href="/licencia.pdf">Solicitud licencia</a>'''


class FuentesParserTests(unittest.TestCase):
    def test_one_instrument_groups_documents_and_preserves_date_meaning(self):
        rows = parse_inventory(INVENTORY, parse_provenance(ARTICLE))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['codigo_ine'], '41042')
        self.assertEqual(row['fase'], 'FASE ACTUAL: 3')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha_publicacion'])
        self.assertEqual(row['fuentes'][0]['fecha_publicacion'], '2026-06-24')
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])

    def test_missing_documents_identity_or_pagination_fail(self):
        for html in ('<p>Solicitud licencia</p>', INVENTORY.replace('Diagnóstico previo', 'Formulario'),
                     INVENTORY + '<a rel="next" href="/page/2">Next</a>',
                     INVENTORY.replace('PBOM de Fuentes de Andalucía', 'PBOM de otro municipio')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, {})

    def test_provenance_requires_article_endorsement(self):
        with self.assertRaises(ValueError):
            parse_provenance(f'<nav><a href="{SOURCE}">PBOM</a></nav><article>News</article>')

    def test_refresh_is_stable_and_licences_disabled(self):
        adapter = FuentesDeAndaluciaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=lambda url, name: ARTICLE if url == PROVENANCE else INVENTORY):
                adapter.backfill_proyectos(output)
                first = output.read_text()
                adapter.update_proyectos(output, Path(directory) / 'state.json')
                self.assertEqual(output.read_text(), first)
                self.assertEqual(len([json.loads(line) for line in first.splitlines()]), 1)
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
