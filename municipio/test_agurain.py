"""Offline parser and adapter-contract tests; live evidence is stored separately."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.agurain import (
    AgurainAyuntamientoAdapter, parse_bulletin, parse_inventory, parse_registry,
)
from municipio.manifest import load_manifest, load_yaml


REG_URL = 'https://web.araba.eus/es/urbanismo/planeamiento-urbanistico/-/reg/2024-013'
PDF_URL = 'https://www.araba.eus/BOTHA/Boletines/2026/052/2026_052_01226_C.pdf'
ENTRY = {'titulo': 'Plan especial de ordenación urbana del AIU4 Educativo-Deportivo', 'url': REG_URL}
PDF_ENTRY = {'titulo': '1ª Modificación puntual del Plan Especial de Rehabilitación integrada del Casco Histórico de Agurain', 'url': PDF_URL}
CARD = '''<div class="content"><p class="title">Planeamiento de desarrollo</p>
<div class="content_basic"><p>Plan Especial de Rehabilitación</p><ul>
<li><a href="%s">%s</a></li><li><a href="%s">%s</a></li>
</ul></div></div>''' % (REG_URL, ENTRY['titulo'], PDF_URL, PDF_ENTRY['titulo'])
REGISTRY = '''<div class="container"><h2>PLAN ESPECIAL EDUCATIVO-DEPORTIVO</h2>
<dl><dt>Número de asiento</dt><dd>2024/013</dd>
<dt>Número de expediente</dt><dd>AHI-074/24-P08</dd>
<dt>Municipio</dt><dd>Salvatierra</dd></dl>
<h3>Aprobación definitiva</h3><dl><dt>Tipo de acuerdo</dt><dd>APROBACIÓN</dd>
<dt>Fecha de aprobación</dt><dd>27/06/2024</dd><dt>Estado</dt><dd>Vigente</dd></dl>
<a href="#" data-download="https://web.araba.eus/download?hash=abc">Memoria.pdf</a>
<a href="#" data-download="https://web.araba.eus/download?hash=abc">Memoria duplicada.pdf</a>
<a href="https://www.araba.eus/BOTHA/Boletines/2024/086/2024_086_02461_C.pdf">BOTHA Nº 86 (31/07/2024)</a>
</div>'''
BULLETIN = '''viernes, 8 de mayo de 2026 • Núm. 52
AYUNTAMIENTO DE AGURAIN
Aprobación definitiva de la modificación puntual del plan especial de rehabilitación
integrada del casco histórico de Agurain.
En sesión ordinaria celebrada por el pleno, en fecha 29 de enero de 2026, se acordó
lo siguiente: Aprobar definitivamente la modificación puntual.
número de asiento 2026/4, en fecha 6 de marzo de 2026.
En Agurain, a 24 de abril de 2026.'''


class AgurainTests(unittest.TestCase):
    def test_manifest_and_adapter(self):
        manifest = load_manifest('agurain')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '01051')
        self.assertEqual(manifest.provincia, 'Álava')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.agurain:AgurainAyuntamientoAdapter')

    def test_inventory_scope_and_deduplication(self):
        html = CARD.replace('</ul>', f'<li><a href="{REG_URL}">{ENTRY["titulo"]}</a></li></ul>')
        html += '<a href="/licencia">Solicitud de licencia</a><a href="/noticia">Fiestas</a>'
        entries = parse_inventory(html)
        self.assertEqual(len(entries), 2)
        self.assertEqual([e['kind'] for e in entries], ['registry', 'bulletin'])

    def test_no_silent_inventory_change_or_pagination(self):
        for html in ['<html>Login</html>', CARD + CARD,
                     CARD.replace('</ul>', '<a href="?page=2">Siguiente</a></ul>'),
                     CARD + '<link rel="next" href="?page=2">',
                     CARD.replace(REG_URL, 'https://example.org/plan'),
                     CARD.replace('</ul>', '<li><a href="/nuevo">Plan especial nuevo</a></li></ul>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_registry_groups_documents_and_separates_dates(self):
        row = parse_registry(REGISTRY, ENTRY)
        self.assertEqual(row['expediente'], 'AHI-074/24-P08')
        self.assertEqual(row['fecha_aprob'], '2024-06-27')
        self.assertIsNone(row['fecha_publicacion'])
        self.assertIsNone(row['fecha_acuerdo'])
        self.assertIsNone(row['fecha'])
        self.assertEqual(row['fase'], 'aprobación definitiva')
        self.assertEqual(len(row['documentos']), 2)
        self.assertIn('31/07/2024', row['referencias_publicacion_registro'][0]['titulo'])
        self.assertIsNone(row['lat'])
        self.assertIsNone(row['geometry'])

    def test_missing_registry_date_and_documents_are_not_invented(self):
        html = REGISTRY.replace('27/06/2024', '')
        html = html[:html.index('<a href=')] + '</div>'
        row = parse_registry(html, ENTRY)
        self.assertIsNone(row['fecha_aprob'])
        self.assertEqual(row['documentos'], [])

    def test_wrong_municipality_identity_and_invalid_date_fail(self):
        for html in [REGISTRY.replace('Salvatierra', 'Vitoria-Gasteiz'),
                     REGISTRY.replace('2024/013', '2024/014'),
                     REGISTRY.replace('27/06/2024', '31/02/2024'), '<html>Login</html>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_registry(html, ENTRY)

    def test_bulletin_agreement_is_not_signature_or_publication(self):
        row = parse_bulletin(BULLETIN, PDF_ENTRY)
        self.assertEqual(row['id'], 'agurain-plan-2026-004')
        self.assertEqual(row['fecha_acuerdo'], '2026-01-29')
        self.assertEqual(row['fecha_aprob'], '2026-01-29')
        self.assertEqual(row['fecha_publicacion'], '2026-05-08')
        self.assertEqual(len(row['documentos']), 1)

    def test_bulletin_requires_actual_act_and_explicit_dates(self):
        for text in [BULLETIN.replace('Aprobar definitivamente', 'Solicitar información'),
                     BULLETIN.replace('en fecha 29 de enero de 2026, se acordó', 'se informó'),
                     BULLETIN.replace('AYUNTAMIENTO DE AGURAIN', 'AYUNTAMIENTO DE OTRO')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_bulletin(text, PDF_ENTRY)

    def test_full_snapshot_failure_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            path.write_text('previous snapshot\n')
            adapter = AgurainAyuntamientoAdapter('agurain')
            with patch.object(adapter, '_fetch', side_effect=[CARD.encode(), REGISTRY.encode(), b'login']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(path)
            self.assertEqual(path.read_text(), 'previous snapshot\n')

    def test_disabled_licences_and_snapshot_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'records.jsonl'
            adapter = AgurainAyuntamientoAdapter('agurain')
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')
            single = CARD.replace(f'<li><a href="{PDF_URL}">{PDF_ENTRY["titulo"]}</a></li>', '')
            with patch.object(adapter, '_fetch', side_effect=[single.encode(), REGISTRY.encode()]):
                result = adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(path.read_text())['codigo_ine'], '01051')


if __name__ == '__main__':
    unittest.main()
