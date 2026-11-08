import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from municipio.adapters.pinos_puente import PinosPuenteAyuntamientoAdapter, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def panel(title, folder, names):
    links = ''.join(f'<a href="/documentos/{folder}/{name}.pdf">{name}</a>' for name in names)
    return f'<div class="wgl-accordion_panel"><h4 class="wgl-accordion_header">{title}</h4><div class="wgl-accordion_content">{links}</div></div>'


class PinosPuenteTests(unittest.TestCase):
    def test_instruments_keep_documents_separate(self):
        html = '<main>' + panel('MODIFICACION DEL PLAN PARCIAL EL TURAN', '2024-3365-Turan', ['Acuerdo', 'Memoria', 'Planos']) + panel('ESTUDIO DETALLE Z-7', '2024_3866_Z7', ['Acuerdo', 'Memoria', 'Planos']) + '</main>'
        rows = parse_inventory(html, 'https://pinos-puente.org/ayuntamiento/instrumentos-de-ordenacion/', 'instrumentos-de-ordenacion')
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual([len(r['documentos']) for r in rows], [3, 3])
        self.assertTrue(all('/2024_3866_Z7/' in d['url'] for d in rows[1]['documentos']))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '18158')
            self.assertFalse(any(k in row for k in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase']))

    def test_pgou_is_one_instrument_with_section_provenance(self):
        html = '<main>' + panel('Memoria General', 'PGOU/MEMORIA GENERAL', ['Memoria General']) + panel('Pinos Puente', 'PGOU/PLANOS', ['Plano']) + '</main>'
        row, = parse_inventory(html, 'https://pinos-puente.org/ayuntamiento/plan-general-de-ordenacion-urbana/', 'plan-general-de-ordenacion-urbana')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][1]['seccion'], 'Pinos Puente')
        self.assertIn('MEMORIA%20GENERAL', row['documentos'][0]['url'])

    def test_empty_or_unrelated_content_fails(self):
        for html in ['<main>Sin datos</main>', '<main>' + panel('Formulario solicitud licencia', 'forms', ['Solicitud']) + '</main>', '<main>' + panel('ESTUDIO DETALLE Z-7', 'z7', []) + '</main>']:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, 'https://pinos-puente.org/', 'instrumentos-de-ordenacion')

    def test_foreign_document_rejected(self):
        html = '<main>' + panel('ESTUDIO DETALLE Z-7', 'z7', ['Memoria']).replace('/documentos/', 'https://example.org/documentos/') + '</main>'
        with self.assertRaises(ValueError):
            parse_inventory(html, 'https://pinos-puente.org/', 'instrumentos-de-ordenacion')

    def test_pagination_never_silently_truncated(self):
        for nav in ['<a rel="next" href="?page=2">Más</a>', '<a href="/page/2/">2</a>', '<div class="pagination"><a href="?p=2">2</a></div>']:
            with self.subTest(nav=nav), self.assertRaises(ValueError):
                parse_inventory('<main>' + panel('ESTUDIO DETALLE Z-7', 'z7', ['Memoria']) + nav + '</main>', 'https://pinos-puente.org/', 'instrumentos-de-ordenacion')

    def test_failure_preserves_previous_output_and_licences_disabled(self):
        adapter = PinosPuenteAyuntamientoAdapter('pinos-puente')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'proyectos.jsonl'
            output.write_text('previous\n')
            with patch.object(adapter, '_fetch', return_value=('<main></main>', 'https://pinos-puente.org/ayuntamiento/')):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous\n')
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')

    def test_manifest_loads_adapter_and_required_controls(self):
        manifest = load_manifest('pinos-puente')
        raw = load_yaml(manifest.path)
        self.assertIsInstance(load_portal_adapter(manifest), PinosPuenteAyuntamientoAdapter)
        self.assertEqual((raw['codigo_ine'], raw['provincia']), ('18158', 'Granada'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)

    def test_official_host_fallback_and_capture(self):
        failed = Mock()
        failed.raise_for_status.side_effect = requests.HTTPError('521')
        success = Mock(url='https://pinos-puente.org/ayuntamiento/', text='<main>Inventario</main>')
        with tempfile.TemporaryDirectory() as tmp:
            adapter = PinosPuenteAyuntamientoAdapter('pinos-puente', {'evidence_dir': tmp})
            with patch('municipio.adapters.pinos_puente.requests.get', side_effect=[failed, success]) as get:
                html, url = adapter._fetch('https://www.pinos-puente.org/ayuntamiento/', 'source.html')
            self.assertEqual(get.call_count, 2)
            self.assertEqual(url, 'https://pinos-puente.org/ayuntamiento/')
            self.assertEqual((Path(tmp) / 'source.html').read_text(), html)


if __name__ == '__main__':
    unittest.main()
