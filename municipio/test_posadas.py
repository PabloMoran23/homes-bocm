import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.posadas import PosadasAyuntamientoAdapter, parse_notice, parse_projects
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

NOTICE = '''Martes, 10 de Febrero de 2026 Nº 27
Ayuntamiento de Posadas BOP-A-2026-326
Por el Pleno, en sesión celebrada el día 29 de enero de 2026,
se ha acordado aprobar inicialmente la Modificación Puntual del PGOU de Posadas,
promovida por este Ayuntamiento, para la eliminación de la Actuación Aislada
AA-3 "La Estación" y su recalificación a Manzana Cerrada.
Conforme al artículo 78 se somete el expediente (GEX 9445/2025).
Posadas, 2 de febrero de 2026.'''


def link(name, title):
    return f'<p><a href="/wp-content/uploads/{name}.pdf">{title}</a></p>'


def fixture():
    return ('<div><h2 class="et_pb_toggle_title">Documentos PGOU</h2>'
            '<div class="et_pb_toggle_content">'
            + link('ANUNCIO-PUBLICADO-EN-EL-BOP-A-2026-326', 'Anuncio')
            + link('DOCUMENTO-TECNICO-DILIGENCIADO', 'Documento')
            + link('1405300AD2NU_NU', 'Normas urbanísticas')
            + link('1405300ad2po_pl11', 'Infraestructura eléctrica')
            + link('study', 'Estudio de detalle para la ampliación del Ayuntamiento')
            + link('form', 'Modelo de solicitud de licencia')
            + '</div></div><div><h2 class="et_pb_toggle_title">'
            'Plan de movilidad urbana sostenible del municipio de Posadas</h2>'
            + link('mobility1', '1') + link('mobility2', '2') + '</div>')


class PosadasTests(unittest.TestCase):
    def test_notice_dates_and_identity(self):
        row = parse_notice(NOTICE)
        self.assertEqual(row['fecha_acuerdo'], '2026-01-29')
        self.assertEqual(row['fecha_publicacion'], '2026-02-10')
        self.assertEqual(row['expediente'], '9445/2025')
        self.assertIn('La Estación', row['titulo'])
        self.assertEqual(row['fase'], 'aprobación inicial')
        for text in ('', NOTICE.replace('Posadas', 'Otra localidad'), NOTICE.replace('GEX', 'ref')):
            with self.assertRaises(ValueError):
                parse_notice(text)

    def test_grouping_and_exclusions(self):
        rows = parse_projects(fixture(), lambda url: NOTICE)
        self.assertEqual(len(rows), 4)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1, 2])
        self.assertNotIn('solicitud', json.dumps(rows))
        self.assertFalse(any('fecha_acuerdo' in r for r in rows[1:]))
        self.assertTrue(all(r['codigo_ine'] == '14053' and not r['publication_ready'] for r in rows))
        self.assertFalse(any('lat' in r or 'lon' in r for r in rows))
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in parse_projects(fixture(), lambda u: NOTICE)])

    def test_fail_closed(self):
        for html in ('<h1>Access denied</h1>', fixture() + '<a rel="next" href="?page=2">Next</a>',
                     fixture().replace('DOCUMENTO-TECNICO-DILIGENCIADO', 'unrelated')):
            with self.assertRaises(ValueError):
                parse_projects(html, lambda u: NOTICE)

    def test_manifest_and_snapshot(self):
        manifest = load_manifest('posadas')
        self.assertEqual(manifest.provincia, 'Córdoba')
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), PosadasAyuntamientoAdapter)
        adapter = PosadasAyuntamientoAdapter('posadas')
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, '_fetch', return_value=fixture().encode()), patch.object(adapter, '_notice', return_value=NOTICE):
            path = Path(tmp) / 'projects.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['count'], 4)
            initial = path.read_text()
            adapter.update_proyectos(path, Path(tmp) / 'state.json')
            self.assertEqual(initial, path.read_text())
            adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
