"""Offline parser and adapter safety regressions for Godelleta."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from municipio.adapters.godelleta import (
    GodelletaAyuntamientoAdapter, INVENTORIES, ROOT, group_documents, parse_inventory,
)
from municipio.manifest import load_manifest


def page(links, extra=''):
    return ('<title>Sede Electrónica de Godelleta</title><div id="content">7.1. 7.3.'
            '<table class="TransparencyListPanel">' + links + '</table>' + extra + '</div>')


def doc(uuid, label, title=''):
    return (f'<a class="gIconLink" href="https://godelleta.sedelectronica.es/preview-document/{uuid}" '
            f'title="{title}">{label}</a>')


class GodelletaTests(unittest.TestCase):
    def test_group_correction_and_generic_document_without_inventing_dates(self):
        a = doc('d10ead14-ba85-409c-a071-201b14c46a64', 'CERTIFICADO MODIFICACIÓN PUNTUAL Nº 5',
                'MODIFICACION PUNTUAL Nº 18 PGOU')
        b = doc('352d88fa-97a3-4e18-a09a-c0a930460738', 'CORRECION ERROR NUMERACION',
                'MODIFICACION PUNTUAL Nº 18 PGOU')
        c = doc('b7eaa165-227b-4778-be32-5cc3a992b053', 'Planos')
        docs = parse_inventory(page(a+b+c), INVENTORIES[0][0], '7.1.')
        rows = group_documents(docs+docs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(rows[0]['id'], 'godelleta-pgou-modificacion-18')
        self.assertIn('Nº 5', rows[0]['documentos'][0]['titulo'])
        for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(rows[0][field])
        self.assertFalse(rows[0]['publication_ready'])

    def test_reject_empty_login_and_non_project(self):
        for html in ('<html>Identifícate</html>', page(''), page(doc(
                'd10ead14-ba85-409c-a071-201b14c46a64', 'Solicitud de licencia'))):
            with self.assertRaises(ValueError):
                parse_inventory(html, INVENTORIES[0][0], '7.1.')

    def test_refuse_pagination_nested_folders_and_ambiguous_instruments(self):
        a = doc('d10ead14-ba85-409c-a071-201b14c46a64', 'Memoria', 'MODIFICACION PUNTUAL Nº 18 PGOU')
        b = doc('352d88fa-97a3-4e18-a09a-c0a930460738', 'Memoria', 'MODIFICACION PUNTUAL Nº 19 PGOU')
        for html in (page(a, '<a rel="next">Siguiente</a>'),
                     page(a+'<a class="exp" href="#">Subcarpeta</a>'), page(a+b)):
            with self.assertRaises(ValueError):
                parse_inventory(html, INVENTORIES[0][0], '7.1.')

    def test_parent_count_mismatch_does_not_overwrite_output(self):
        parent = page('<a class="exp">7.1. PLANEAMIENTO ( 2 )</a><a class="exp">7.3. NORMATIVA ( 1 )</a>')
        child = page(doc('d10ead14-ba85-409c-a071-201b14c46a64', 'Memoria', 'MODIFICACION PUNTUAL Nº 18 PGOU'))
        responses = [Mock(url=ROOT, text=parent, content=parent.encode()),
                     Mock(url=INVENTORIES[0][0], text=child, content=child.encode())]
        with TemporaryDirectory() as temp, patch('municipio.adapters.godelleta.requests.Session') as cls:
            cls.return_value.__enter__.return_value.get.side_effect = responses
            out = Path(temp)/'proyectos.jsonl'
            out.write_text('previous snapshot')
            with self.assertRaisesRegex(ValueError, 'count mismatch'):
                GodelletaAyuntamientoAdapter('godelleta').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('godelleta')
        self.assertEqual(manifest.provincia, 'Valencia')
        self.assertFalse(manifest.licencias.enabled)
        with TemporaryDirectory() as temp:
            out = Path(temp)/'licencias.jsonl'
            result = GodelletaAyuntamientoAdapter('godelleta').backfill_licencias(out)
            self.assertTrue(result['disabled'])
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
