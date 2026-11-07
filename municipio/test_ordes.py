"""Offline parser/contract tests; fixtures model the reviewed municipal markup."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.ordes import (
    BASE, INVENTORY, OrdesAyuntamientoAdapter, discover_pages, parse_history, parse_plan,
)
from municipio.manifest import load_manifest, load_yaml

CURRENT = BASE + '/p/pxom-ad-en-vigor-16-04-2024-'
HISTORY = BASE + '/p/doc-tramitacion-pxom'
MENU = '''<li><a class="trigger">PLANEAMENTO URBANISTICO</a><ul>
<li><a href="/p/pxom-ad-en-vigor-16-04-2024-">PXOM AD (en vigor 16/04/2024)</a></li>
<li><a href="/p/doc-tramitacion-pxom">DOC. TRAMITACIÓN PXOM</a></li>
<li><a href="/p/nnss-1996-derogadas-">NNSS 1996 (derogadas)</a></li>
</ul></li>'''
# Dates and labels transcribed from the municipal document inventory.
LABELS = [
    ('https://www.ordes.gal/approval.pdf', 'ORDE APROBACIÓN DEFINITIVA (13/12/2023)'),
    ('https://www.xunta.gal/dog/Publicados/2023/20231226/notice.html',
     'RESOLUCIÓN DO 15 DE DECEMBRO DE 2023: PLAN XERAL DO CONCELLO DE ORDES (DOG Nº 243: 26/12/2023)'),
    ('https://www.ordes.gal/registration.pdf', 'INSCRICIÓN (29/01/2024)'),
    ('https://bop.dicoruna.es/ordinances.pdf', 'PUBLICACIÓN NORMATIVA (19/02/2024)'),
    ('https://www.ordes.gal/registration-correction.pdf', 'MODIFICACIÓN INSCRICIÓN (15/03/2024)'),
    ('https://www.ordes.gal/correction.pdf', 'CORRECCIÓN DE ERROS (22/03/2024)'),
    ('https://www.ordes.gal/sectors.pdf', 'PUBLICACIÓN S-01 e S-05 (22/03/2024)'),
]
PLAN = '<div class="content-wrapper"><h1>PXOM AD (en vigor 16/04/2024)</h1><ol>' + ''.join(
    f'<li><a href="{u}">{t}</a></li>' for u, t in LABELS) + '</ol></div>'
PROCESSING = '''<div class="content-wrapper"><h1>DOC. TRAMITACIÓN PXOM</h1>
<ol><li>DOCUMENTACIÓN PARA A TRAMITACIÓN DO PLAN XERAL DE ORDEACIÓN MUNICIPAL DE ORDES
<ol><li><a href="https://drive.google.com/drive/folders/test">
APROBACIÓN INICIAL (Pleno 16/03/2016)</a></li></ol></li></ol></div>'''


class OrdesTests(unittest.TestCase):
    def test_discovery_deduplicates_menu_and_excludes_repealed_rules(self):
        self.assertEqual(discover_pages(MENU + MENU), (CURRENT, HISTORY))
        with self.assertRaises(ValueError):
            discover_pages(MENU.replace('PXOM AD', 'Otro plan'))

    def test_dates_and_documents_are_one_instrument(self):
        row = parse_plan(PLAN.replace('</ol>', f'<li><a href="{LABELS[0][0]}">{LABELS[0][1]}</a></li></ol>'), CURRENT)
        self.assertEqual(len(row['documentos']), 7)
        self.assertEqual(row['codigo_ine'], '15059')
        self.assertEqual(row['fecha_aprob'], '2023-12-13')
        self.assertEqual(row['fecha_publicacion'], '2023-12-26')
        self.assertEqual(row['fecha_entrada_vigor'], '2024-04-16')
        self.assertIsNone(row['fecha'])
        self.assertIsNone(row['geometry'])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['provenance']['fecha_publicacion']['boletin'], 'DOG')

    def test_pagination_is_never_silently_ignored(self):
        for html in ['<a rel="next" href="?page=2">2</a>',
                     '<ul class="pagination"><li>2</li></ul>',
                     '<a href="?page=2">Seguinte</a>']:
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_plan(PLAN + html, CURRENT)
            with self.assertRaises(ValueError):
                discover_pages(MENU + html)

    def test_missing_or_ambiguous_plan_is_rejected(self):
        for html in [PLAN.replace('ORDE APROBACIÓN DEFINITIVA', 'Formulario de licenza'),
                     PLAN.replace('26/12/2023', '31/02/2023'),
                     PLAN.replace('13/12/2023', 'sin fecha'),
                     '<h1>Noticia o formulario</h1>']:
            with self.assertRaises(ValueError):
                parse_plan(html, CURRENT)

    def test_processing_documents_keep_provenance(self):
        docs = parse_history(PROCESSING, HISTORY)
        self.assertEqual(docs[0]['fecha_acuerdo'], '2016-03-16')
        self.assertEqual(docs[0]['source_url'], HISTORY)
        self.assertNotIn('fecha_publicacion', docs[0])
        with self.assertRaises(ValueError):
            parse_history(PROCESSING.replace('APROBACIÓN INICIAL', 'Anuncio de contratación'), HISTORY)

    def test_adapter_groups_processing_and_preserves_output_on_failure(self):
        adapter = OrdesAyuntamientoAdapter('ordes')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[MENU, PLAN, PROCESSING]):
                self.assertEqual(adapter.backfill_proyectos(output)['rows'], 1)
            previous = output.read_text()
            row = json.loads(previous)
            self.assertEqual(len(row['documentos']), 8)
            with patch.object(adapter, '_fetch', side_effect=[MENU, '<h1>Error</h1>']):
                with self.assertRaises(ValueError):
                    adapter.update_proyectos(output, Path(directory) / 'state.json')
            self.assertEqual(output.read_text(), previous)
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('ordes')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia), ('Ordes', 'A Coruña'))
        self.assertEqual(raw['codigo_ine'], '15059')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.ordes:OrdesAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
