"""Offline parser and complete snapshot tests; no network or local evidence needed."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.gorliz import (
    DEVELOPMENT, ROOT, STRUCTURAL, GorlizAyuntamientoAdapter,
    content, parse_development, parse_notice, pdf_documents,
)
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml


def page(body, region='ProcedureZone'):
    return f'<div id="main-content"><div id="{region}">{body}</div></div>'


def link(path, label):
    return f'<a href="{ROOT}{path}">{label}</a>'


TOURISM = '''BOLETÍN OFICIAL DE BIZKAIA Núm. 119 Martes, 24 de junio de 2025 Pág. 1
Ayuntamiento de Gorliz El pleno de la Corporación, en sesión ordinaria celebrada el 5 de junio de 2025,
adoptó entre otros, el siguiente Acuerdo: Primera: Formular el Plan Especial de regulación de las viviendas turísticas
En Gorliz, a 16 de junio de 2025. cve: BOB-2025a119-(II-3784)'''
PAU = '''BOLETÍN OFICIAL DE BIZKAIA Núm. 226 Martes, 25 de noviembre de 2025 Pág. 1
Ayuntamiento de Gorliz La Junta de Gobierno Local, en sesión ordinaria celebrada el 11 de noviembre de 2025,
adoptó entre otros, el siguiente acuerdo: Primera: Aprobar definitivamente el PAU de la AIE 09
Dicho plan fue publicado en su integridad con fecha 13 de junio de 2025.
En Gorliz, a 13 de noviembre de 2025. cve: BOB-2025a226-(II-6823)'''


class GorlizTests(unittest.TestCase):
    def test_manifest_and_registry(self):
        manifest = load_manifest('gorliz')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('48043', 'Gorliz', 'Bizkaia'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        self.assertIsInstance(load_portal_adapter(manifest), GorlizAyuntamientoAdapter)

    def test_dates_are_distinct_and_formulation_is_not_approval(self):
        tourist = parse_notice(TOURISM, 'especial')
        self.assertEqual(tourist['fecha_publicacion'], '2025-06-24')
        self.assertEqual(tourist['fecha_acuerdo'], '2025-06-05')
        self.assertIsNone(tourist['fecha_aprob'])
        self.assertEqual(tourist['fase'], 'formulación')
        pau = parse_notice(PAU, 'PAU')
        self.assertEqual(pau['fecha_publicacion'], '2025-11-25')
        self.assertEqual(pau['fecha_aprob'], '2025-11-11')
        with self.assertRaises(ValueError):
            parse_notice('Solicitud de licencia de obras en Gorliz', 'PAU')
        with self.assertRaises(ValueError):
            parse_notice(TOURISM.replace('Ayuntamiento de Gorliz', 'Ayuntamiento de Bilbao'), 'especial')

    def test_inventory_groups_documents_and_excludes_history(self):
        html = page('<h3>Planeamiento y desarrollo PGOU</h3>' +
                    link('plan_viviendas_turisiticas/bob.pdf', 'Plan especial de regulación de las viviendas turísticas') +
                    link('plan_viviendas_turisiticas/plano.pdf', 'Plano') +
                    link('Paginas/pau-aie-09.aspx', 'PAU A.I.E. 09'), 'centerColumn')
        html += '<div id="rightColumn">' + link('Paginas/plan-des_pp-old.aspx', 'P.P histórico') + '</div>'
        groups, pages = parse_development(html)
        self.assertEqual([len(x) for x in groups], [2])
        self.assertEqual(len(pages), 1)
        with self.assertRaises(ValueError):
            parse_development(html.replace('PAU A.I.E. 09', 'Solicitud de licencia'))
        with self.assertRaises(ValueError):
            parse_development(html.replace('PAU A.I.E. 09', 'Anuncio de contratación'))

    def test_fail_closed_on_pagination_missing_content_and_non_documents(self):
        for html in [page('<a href="?page=2">2</a>'), page('<a rel="next" href="next.aspx">Más</a>')]:
            with self.assertRaises(ValueError):
                content(html)
        with self.assertRaises(ValueError):
            pdf_documents('<html>Sign in</html>', DEVELOPMENT)
        with self.assertRaises(ValueError):
            pdf_documents(page(link('Paginas/form.aspx', 'Formulario')), DEVELOPMENT)
        with self.assertRaises(ValueError):
            pdf_documents(page('<a href="https://unrelated.invalid/doc.pdf">PDF</a>'), DEVELOPMENT)

    def test_complete_dossier_is_one_record_and_failed_refresh_is_atomic(self):
        pgou = ROOT + 'Paginas/pgou-vigor.aspx'
        sections = ['Memoria', 'Planos', 'Memoria EAE', 'Planos EAE']
        sources = {STRUCTURAL: page(link('Paginas/pgou-vigor.aspx', 'PGOU en Vigor')),
                   pgou: page(''.join(link(f'Paginas/s{i}.aspx', label) for i, label in enumerate(sections))),
                   DEVELOPMENT: page('<h3>Planeamiento y desarrollo PGOU</h3>' +
                                     link('Paginas/pau-aie-09.aspx', 'PAU A.I.E. 09'), 'centerColumn'),
                   ROOT + 'Paginas/pau-aie-09.aspx': page(link('pauaie09/bob.pdf', 'Aprobación definitiva'))}
        for i in range(4):
            doc = link(f'docs/s{i}.pdf', 'Documento')
            sources[ROOT + f'Paginas/s{i}.aspx'] = page(doc + doc)
        adapter = GorlizAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as tmp, patch.object(adapter, 'fetch', side_effect=sources.__getitem__), patch.object(adapter, 'notice', return_value=parse_notice(PAU, 'PAU')):
            target = Path(tmp) / 'proyectos.jsonl'
            result = adapter.backfill_proyectos(target)
            rows = [json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual(result['rows'], 2)
            self.assertEqual(len(rows[0]['documentos']), 4)
            self.assertIsNone(rows[0]['fecha_aprob'])
            self.assertTrue(all(r['geometry'] is None for r in rows))
            before = target.read_bytes()
            sources[pgou] = page('no documents')
            with self.assertRaises(ValueError):
                adapter.update_proyectos(target, Path(tmp) / 'state.json')
            self.assertEqual(target.read_bytes(), before)
            adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')


if __name__ == '__main__':
    unittest.main()
