import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.villanueva_del_trabuco import (
    BASE, ROOT, VillanuevaDelTrabucoAyuntamientoAdapter, group_documents, parse_page,
)
from municipio.manifest import load_manifest


def doc(title, description=None, identifier='one'):
    return {'titulo': title, 'descripcion': description,
            'url': BASE + '/preview-document/' + identifier, 'inventory_url': ROOT}


def page(path, documents):
    return {'path': path, 'url': ROOT, 'documents': documents}


class ParserTests(unittest.TestCase):
    def test_inventory_links_and_folder_counts(self):
        html = '''<table class="TransparencyListPanel"><tr><td>
        <a class="gIconLink exp" onclick="wicketAjaxGet('?x=fresh',null)">SECTOR UR-3 ( 2 )</a>
        <a class="gIconLink" href="/preview-document/abc" title="Plan Parcial UR-3">Certificado</a>
        </td></tr></table>'''
        folders, docs = parse_page(html, ROOT)
        self.assertEqual(folders[0]['count'], 2)
        self.assertEqual(docs[0]['descripcion'], 'Plan Parcial UR-3')
        self.assertEqual(docs[0]['url'], BASE + '/preview-document/abc')

    def test_merge_plan_documents_across_folders(self):
        rows = group_documents([
            page(['PLANES PARCIALES'], [doc('Aprobación Provisional Plan Parcial UR-3')]),
            page(['PLANES PARCIALES', 'SECTOR UR-3'], [doc('certificado aprobacion definitiva pleno 26.1.2023', identifier='two')]),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(rows[0][key])
        self.assertFalse(rows[0]['publication_ready'])

    def test_split_mixed_modifications_and_ur4(self):
        rows = group_documents([
            page(['MODIFICACIONES'], [doc('FORMULACION NNSS USO INDUSTRIAL'), doc('NNSS Art123.2.a', identifier='two')]),
            page(['ESTUDIOS DETALLES', 'SECTOR UR-4'], [doc('Estudio Detalle Vivienda UR-4', identifier='three'), doc('Modificación Estudio Detalle Vivienda UR-4', identifier='four')]),
        ])
        self.assertEqual(len(rows), 4)
        self.assertEqual(len({r['id'] for r in rows}), 4)

    def test_loua_documents_grouped_across_sections(self):
        rows = group_documents([
            page(['ADAPTACIÓN NORMAS A LOUA'], [doc('Consulta popular')]),
            page(['6.7 ADAPTACIÓN PARCIAL A LOUA'], [doc('Documento diligenciado', identifier='two')]),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)

    def test_source_accented_folder(self):
        rows = group_documents([page(['ESTUDIOS DETALLES', 'SECTOR CALLE CAÑAS'],
                                    [doc('MEMORIA_ESTUDIO DE DETALLE_PROLONGACION CALLE LAS CAÑAS')])])
        self.assertIn('Las Cañas', rows[0]['titulo'])

    def test_reject_forms_unknown_sources_and_pagination(self):
        for html in ('<h1>Identifícate</h1>', '<table class="TransparencyListPanel"></table><div class="pagination">2</div>',
                     '<table class="TransparencyListPanel"><a class="gIconLink" href="https://example.org/a">Plan</a></table>'):
            with self.assertRaises(ValueError):
                parse_page(html, ROOT)
        with self.assertRaises(ValueError):
            group_documents([page(['MODIFICACIONES'], [doc('Solicitud licencia obra')])])
        with self.assertRaises(ValueError):
            group_documents([])

    def test_count_mismatch_aborts_before_writing(self):
        adapter = VillanuevaDelTrabucoAyuntamientoAdapter('villanueva-del-trabuco')
        folders = [{'title': '6.1. PLANEAMIENTO', 'count': 2, 'url': ROOT + '?x=a'},
                   {'title': '6.7 ADAPTACIÓN', 'count': 0, 'url': ROOT + '?x=b'}]
        response = unittest.mock.Mock(url=ROOT, text='unused')
        with tempfile.TemporaryDirectory() as tmp, patch('municipio.adapters.villanueva_del_trabuco.requests.Session.get', return_value=response), patch('municipio.adapters.villanueva_del_trabuco.parse_page', side_effect=[(folders, []), ([], [])]):
            output = Path(tmp) / 'out.jsonl'
            with self.assertRaisesRegex(ValueError, 'Incomplete inventory'):
                adapter.backfill_proyectos(output)
            self.assertFalse(output.exists())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('villanueva-del-trabuco')
        self.assertEqual(manifest.provincia, 'Málaga')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            result = VillanuevaDelTrabucoAyuntamientoAdapter(manifest.slug).backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
