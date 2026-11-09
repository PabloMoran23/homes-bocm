import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.pinseque import (
    GENERAL_TITLE, INVENTORY_URL, PinsequeAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def fixture():
    return f'''<div><h2>{GENERAL_TITLE}</h2>
    <a href="/pgou.pdf">PGOU Pinseque.</a><a href="/pgou.pdf"></a>
    <p><strong>Modificación puntual nº 1 del PGOU de Pinseque.</strong> Planillas</p>
    <ul><li><a href="/boa.pdf">BOA 18.09.2002</a></li>
    <li><a href="/acuerdo.pdf">Documento Acuerdo 2002-06-28</a></li></ul>
    <p><strong>Modificación puntual nº 2 del PGOU de Pinseque.</strong></p>
    <p><strong>MPGOU nº 3.</strong> UE-2</p>
    <a href="/ue2.pdf">Plano UE-2</a>
    <p><strong>Solicitud de licencia</strong></p><a href="/licencia.pdf">Formulario</a>
    <h2>Noticias</h2><a href="/noticia.pdf">Fiestas</a></div>'''


class PinsequeTests(unittest.TestCase):
    def test_grouping_boundaries_and_semantics(self):
        rows, missing = parse_inventory(fixture())
        self.assertEqual([r['id'] for r in rows], ['pinseque-plan-pgou', 'pinseque-plan-mpgou-1', 'pinseque-plan-mpgou-3'])
        self.assertEqual(len(missing), 1)
        self.assertIn('nº 2', missing[0])
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2, 1])
        self.assertEqual(rows[2]['documentos'][0]['url'], 'https://pinseque.es/ue2.pdf')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '50209')
            self.assertFalse(row['publication_ready'])
            self.assertFalse(any(k in row for k in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'geometry', 'fase']))

    def test_fail_closed(self):
        for html in ['', '<h2>Noticias</h2>', fixture().replace('pgou.pdf', 'pgou.html'),
                     fixture().replace('/boa.pdf', 'https://example.org/boa.pdf'),
                     fixture().replace('</div>', '<a rel="next" href="?page=2">Next</a></div>')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_fetch_update_and_disabled_licences(self):
        adapter = PinsequeAyuntamientoAdapter('pinseque')
        response = Mock(text=fixture(), url=INVENTORY_URL)
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.pinseque.requests.get', return_value=response) as get:
            output = Path(tmp) / 'proyectos.jsonl'
            stats = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(stats['count'], 3)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 3)
            get.assert_called_once()
            response.raise_for_status.assert_called_once()
            adapter.update_licencias(output, Path(tmp) / 'state.json')
            self.assertEqual(output.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('pinseque')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '50209')
        self.assertEqual(manifest.provincia, 'Zaragoza')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.pinseque:PinsequeAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
