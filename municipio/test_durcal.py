"""Offline semantic and completeness regressions for Dúrcal inventory parsing."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.durcal import (
    BASE, DurcalAyuntamientoAdapter, folder_action, make_record, parse_documents,
)
from municipio.manifest import load_manifest, load_yaml


def page(*titles):
    return 'Ayuntamiento de Dúrcal<table>' + ''.join(
        f'<tr><td class="class_name"><a href="{BASE}/preview-document/00000000-0000-0000-0000-{i:012d}">{title}</a></td></tr>'
        for i, title in enumerate(titles)
    ) + '</table>'


class DurcalParserTests(unittest.TestCase):
    def test_group_plan_documents_without_inventing_dates(self):
        docs = parse_documents(page('20240117_Anuncio BOP-1', '20230127_Certificado de acuerdos', 'PLANOS'), 3)
        row = make_record('PLAN PARCIAL SECTOR SUBS-I-D1 SAN BLAS', 'plan parcial', BASE + '/transparency/test/', docs)
        self.assertEqual(len(row['documentos']), 3)
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        reversed_row = make_record('PLAN PARCIAL SECTOR SUBS-I-D1 SAN BLAS', 'plan parcial', row['url'], list(reversed(docs)))
        self.assertEqual(row['id'], reversed_row['id'])

    def test_pgou_modification_is_one_instrument_and_search_is_reference(self):
        html = page('BOP MODIFICACION PUNTUAL Nº 1', 'MOD PUNTUAL Nº1 PGOU PLANO', 'MOD PUNTUAL Nº 1 PGOU')
        html += '<td class="class_name"><a href="https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf">PGOU</a></td>'
        row = make_record('PGOU', 'modificación puntual del PGOU', BASE + '/transparency/test/', parse_documents(html, 4))
        self.assertEqual(row['titulo'], 'Modificación puntual nº 1 del PGOU de Dúrcal')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(len(row['referencias']), 1)
        with self.assertRaises(ValueError):
            make_record('PGOU', 'modificación puntual del PGOU', row['url'], parse_documents(page('PGOU'), 1))

    def test_pagination_missing_duplicate_or_nested_documents_fail(self):
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_documents(page('Plano'), 9)
        with self.assertRaises(ValueError):
            parse_documents(page('Plano') + page('Mismo enlace'), 2)
        with self.assertRaises(ValueError):
            parse_documents(page('Plano') + '<td class="class_name"><a class="exp">Nueva carpeta</a></td>', 1)

    def test_public_folder_action_count_and_ambiguity(self):
        html = '''Ayuntamiento de Dúrcal<td class="class_name"><a class="exp"
            onclick="var wcall=wicketAjaxGet('../../?x=public-token',null);">PGOU ( 4 )</a></td>'''
        self.assertEqual(folder_action(html, 'PGOU'), ('../../?x=public-token', 4))
        with self.assertRaises(ValueError):
            folder_action(html + html, 'PGOU')
        with self.assertRaises(ValueError):
            folder_action(html, 'Otro plan')

    def test_forms_navigation_login_and_changed_pool_are_rejected(self):
        for html in ('Identifícate', 'Ayuntamiento de Dúrcal<a href="/form">Solicitud de obra</a>',
                     'Ayuntamiento de Dúrcal<td class="class_name"><a href="https://other.es/form">Solicitud</a></td>'):
            with self.assertRaises(ValueError):
                parse_documents(html, 1)
        with self.assertRaises(ValueError):
            make_record('7.4. OBRAS PÚBLICAS E INFRAESTRUCTURAS', 'estudio de viabilidad', BASE, parse_documents(page('Contratación'), 1))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('durcal')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('18071', 'Dúrcal', 'Granada'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            result = DurcalAyuntamientoAdapter().backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
