"""Offline parser and adapter contract checks (no network required)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.elorrio import ElorrioAyuntamientoAdapter, HOME, NOTICE
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

INVENTORY = '''<article><div class="field--name-body">
<p>Documentos disponibles</p><p>Fase 3: Exposición Pública del Avance</p>
<p><a href="/files/memoria.pdf">Memoria</a></p>
<p><a href="/files/resumen.pdf">Resumen ejecutivo</a></p>
<p><a href="/files/die.pdf">DIE(Documento Inicial Estratégico)</a></p>
<p><a href="/files/mapa.pdf">AA.2.2.A</a></p>
<p><a href="/files/mapa.pdf">AE.2.2.A</a></p>
<p>Fase 2: Redacción del avance</p>
<p><a href="https://d9.createlli.com/files/criterios.pdf">Criterios</a></p>
</div></article>'''
ANNOUNCEMENT = '''<h1>Arranca la fase de la exposición pública del Avance del PGOU de Elorrio</h1>
<span class="date">23/09/2026</span><a href="https://hapo-elorrio.eus/es">PGOU</a>'''
HOME_HTML = '<a href="/es/documentos">DOCUMENTOS</a><a href="/es/documentos">DOCUMENTOS</a>'


class ElorrioTests(unittest.TestCase):
    def test_one_plan_preserves_all_documents_phases_and_aliases(self):
        rows = ElorrioAyuntamientoAdapter.parse_inventory(INVENTORY, HOME + '/documentos')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '48032')
        self.assertEqual(len(row['documentos']), 5)
        self.assertEqual(len(row['documentos'][3]['referencias']), 2)
        self.assertEqual(row['documentos'][-1]['referencias'][0]['fase_documental'], 'Fase 2: Redacción del avance')
        for key in ['fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'geometry', 'lat', 'lon']:
            self.assertIsNone(row[key])
        # No historical fixed item cap: every link is retained.
        extra = ''.join(f'<p><a href="/files/{i}.pdf">Plano {i}</a></p>' for i in range(250))
        expanded = INVENTORY.replace('</div>', extra + '</div>')
        self.assertEqual(len(ElorrioAyuntamientoAdapter.parse_inventory(expanded, HOME)[0]['documentos']), 255)

    def test_rejects_pagination_or_missing_and_changed_sources(self):
        for suffix in ['<a rel="next" href="?page=1">2</a>', '<a href="/next">Siguiente</a>',
                       '<ul class="pager"><li><a href="/2">2</a></li></ul>']:
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                ElorrioAyuntamientoAdapter.parse_inventory(INVENTORY + suffix, HOME)
        for html in ['<p>Solicitud de licencia</p>', INVENTORY.replace('Memoria', 'Formulario'),
                     INVENTORY.replace('Fase 3:', 'Fase 5:')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                ElorrioAyuntamientoAdapter.parse_inventory(html, HOME)
        with self.assertRaises(ValueError):
            ElorrioAyuntamientoAdapter.discover_inventory('<a href="https://example.org">DOCUMENTOS</a>')
        with self.assertRaises(ValueError):
            ElorrioAyuntamientoAdapter.parse_provenance(ANNOUNCEMENT.replace(HOME, 'https://example.org'))

    def test_manifest_contract_live_pipeline_and_dates(self):
        manifest = load_manifest('elorrio')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], raw['nombre'], raw['provincia']), ('48032', 'Elorrio', 'Bizkaia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        pages = {NOTICE: ANNOUNCEMENT, HOME: HOME_HTML, HOME + '/es/documentos': INVENTORY}
        # urljoin(HOME, '/es/documentos') retains a single /es.
        pages[HOME + '/documentos'] = INVENTORY
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=pages.__getitem__):
                result = adapter.update_proyectos(output, Path(directory) / 'state.json')
            row = json.loads(output.read_text())
            self.assertEqual(result['rows'], 1)
            self.assertEqual(row['fecha_publicacion'], '2026-09-23')
            self.assertEqual(row['fecha_publicacion_source_url'], NOTICE)
            self.assertIsNone(row['fecha_aprob'])
            self.assertEqual(adapter.backfill_licencias(output)['rows'], 0)
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
