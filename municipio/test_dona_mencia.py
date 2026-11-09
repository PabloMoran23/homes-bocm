import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.dona_mencia import SOURCE, DonaMenciaAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest


def fixture():
    return '''<div class="entry-content"><div class="et_pb_tabs">
    <ul class="et_pb_tabs_controls"><li>PGOU</li><li>Modificación puntual 1 PGOU</li></ul>
    <div class="et_pb_all_tabs"><div class="et_pb_tab">
    <a href="/normas/">Normas texto refundido</a><a href="/memoria/">Memoria</a>
    <a href="/memoria/">Memoria repetida</a></div><div class="et_pb_tab">
    <a href="/wp-content/uploads/mod.pdf">Modificación puntual 1</a>
    <a href="/wp-content/uploads/resumen.pdf">Resumen ejecutivo</a>
    <a href="/wp-content/uploads/propuesta.pdf">Propuesta de aprobación definitiva</a>
    </div></div></div></div><footer><a href="/licencia.pdf">Formulario licencia</a></footer>'''


class DonaMenciaTests(unittest.TestCase):
    def test_groups_documents_and_retains_provenance(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 3])
        self.assertEqual(rows[1]['documentos'][2]['titulo'], 'Propuesta de aprobación definitiva')
        self.assertEqual(rows[0]['documentos'][1]['url'], 'https://donamencia.es/memoria/')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '14022')
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['geometry_status'], 'unavailable')
            self.assertFalse({'fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'} & row.keys())
            self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        self.assertEqual(rows[0]['id'], parse_inventory(fixture().replace('Memoria repetida', 'Otro rótulo'))[0]['id'])

    def test_fail_closed_on_empty_changed_or_paginated_inventory(self):
        for html in ['', '<p>Noticias y solicitudes de licencia</p>',
                     fixture().replace('<li>PGOU</li>', ''),
                     fixture().replace('Modificación puntual 1 PGOU', 'Solicitudes de licencia'),
                     fixture().replace('href="/normas/"', 'href="https://otro.es/a.pdf"'),
                     fixture().replace('href="/normas/"', 'href="#"'),
                     fixture() + '<a rel="next" href="?page=2">2</a>',
                     fixture() + '<div class="page-links"><a href="/2/">2</a></div>',
                     fixture() + '<a href="?page=2">Siguiente</a>']:
            with self.subTest(html=html[-120:]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_live_path_refresh_and_manifest(self):
        manifest = load_manifest('dona-mencia')
        self.assertEqual(manifest.provincia, 'Córdoba')
        self.assertFalse(manifest.licencias.enabled)
        adapter = DonaMenciaAyuntamientoAdapter('dona-mencia')
        response = Mock(url=SOURCE, text=fixture())
        with tempfile.TemporaryDirectory() as td, patch('municipio.adapters.dona_mencia.requests.get', return_value=response) as get:
            path = Path(td) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['count'], 2)
            self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 2)
            self.assertEqual(adapter.update_proyectos(path, Path(td) / 'state.json')['written'], 2)
            self.assertEqual(get.call_count, 2)
            adapter.backfill_licencias(Path(td) / 'licencias.jsonl')
            self.assertEqual((Path(td) / 'licencias.jsonl').read_text(), '')
            response.url = 'https://otro.es/'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(path)
            self.assertEqual(len(path.read_text().splitlines()), 2)


if __name__ == '__main__':
    unittest.main()
