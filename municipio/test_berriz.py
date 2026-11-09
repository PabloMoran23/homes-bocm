import tempfile
import unittest
from pathlib import Path

from municipio.adapters.berriz import BerrizAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def block(title, links):
    return '<div><div><h3 class="ms-WPTitle">' + title + '</h3></div><div class="ms-WPBody">' + ''.join(
        '<a href="/es-ES/Servicios/Urbanismo/Documents/' + name + '">' + label + '</a>'
        for name, label in links) + '</div></div>'


PROJECT = block('Anuncio de sometimiento a información pública de proyecto de rehabilitación', [
    ('20261019-project.pdf', '1. Proyecto básico Bifamiliarización del Caserío "Ejemplo" (PDF 1MB)'),
    ('plans.pdf', '2. Planos'), ('notice.pdf', '3. Anuncio')])
STUDY = block('Estudio de Detalle de las parcelas 36 y 38', [
    ('study.pdf', '1. Expediente Estudio de Detalle'), ('notice2.pdf', '2. Aprobación inicial')])
ORDINANCE = block('Ordenanza municipal de división de caseríos', [('ord.pdf', 'Aprobación definitiva')])


def page(body):
    return '<div id="main-content">Expedientes en exposición pública<div id="ProcedureZone">' + body + '</div></div>'


class BerrizTests(unittest.TestCase):
    def test_groups_documents_and_excludes_ordinance(self):
        rows = Adapter.parse_inventory(page(PROJECT + STUDY + ORDINANCE + PROJECT))
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [3, 2])
        self.assertIn('Caserío "Ejemplo"', rows[0]['titulo'])
        self.assertEqual(rows[0]['fase'], 'información pública')
        for row in rows:
            for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[key])
        self.assertEqual(rows[0]['id'], Adapter.parse_inventory(page(PROJECT))[0]['id'])

    def test_fails_closed_on_source_changes(self):
        for html in ['<html>error</html>', page(ORDINANCE),
                     page(PROJECT + '<a href="?page=2">Siguiente</a>'),
                     page(PROJECT.replace('Proyecto básico', 'Formulario de licencia')),
                     page(PROJECT.replace('plans.pdf', 'plans.html'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_inventory(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('berriz')
        self.assertEqual(manifest.provincia, 'Bizkaia')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(path)['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
