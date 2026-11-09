"""Offline parser and adapter contract tests for the municipal PBOM inventory."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.constantina import (
    DOCUMENTS, ENTRY, HOME, ConstantinaAyuntamientoAdapter, parse_documents,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(links):
    return ('<html><title>DOCUMENTOS – PBOM CONSTANTINA</title><main>'
            + ''.join(f'<a href="{url}">{label}</a>' for url, label in links)
            + '</main></html>')


MEMORY = HOME + 'wp-content/uploads/2026/05/P07-F3_MEMORIA_DEF.pdf'
MAPS = HOME + 'wp-content/uploads/2026/05/P07-F3_PLANOS_DEF.pdf'
DIAGNOSIS = ('https://www.constantina.org/export/sites/constantina/.galleries/'
             'documentos-noticias/DOCUMENTO-DE-DIAGNOSTICO-PREVIO-PBOM-CONSTANTINA.pdf')
HTML = inventory([(MEMORY, ''), (MAPS, 'Planos'), (DIAGNOSIS, 'Diagnóstico'),
                  (MEMORY, 'Duplicado')])
HOME_HTML = ('<title>PBOM CONSTANTINA</title><main><a href="/documentos/">DOCUMENTOS</a>'
             '<p>Actualmente nos encontramos en la Fase 3</p></main>')


class ConstantinaTests(unittest.TestCase):
    def test_one_instrument_groups_documents_and_deduplicates(self):
        row = parse_documents(HTML)
        self.assertEqual(row['codigo_ine'], '41033')
        self.assertEqual([d['url'] for d in row['documentos']], [MEMORY, MAPS, DIAGNOSIS])
        self.assertEqual(row['documentos'][0]['titulo'], 'P07-F3_MEMORIA_DEF.pdf')
        self.assertTrue(all(d['inventory_url'] == DOCUMENTS for d in row['documentos']))
        self.assertEqual(row['id'], parse_documents(inventory([(MAPS, '')]))['id'])

    def test_no_dates_or_geometry_inferred_from_def_or_upload_folder(self):
        row = parse_documents(HTML)
        for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertNotIn('fase', row)
        self.assertFalse(row['publication_ready'])

    def test_foreign_files_forms_navigation_and_generic_news_excluded(self):
        row = parse_documents(inventory([
            (MEMORY, ''),
            ('https://losmolares.nuevoplan.es/wp-content/uploads/FASE1-DOC-B-DEF.pdf', ''),
            (HOME + 'wp-content/uploads/2024/06/P07-F2_CUESTIONARIO-Constantina.pdf', ''),
            (HOME + 'noticias/', 'Noticias'),
            ('https://www.constantina.org/formulario-licencia.pdf', 'Licencia'),
        ]))
        # Only plan-code files (P07-Fn_) in the DOCUMENTOS inventory belong here.
        self.assertEqual([d['url'] for d in row['documentos']], [MEMORY])

    def test_empty_wrong_municipality_and_forms_only_fail(self):
        for html in ('<html/>', HTML.replace('PBOM CONSTANTINA', 'PBOM OTRO'),
                     inventory([]), inventory([(HOME + 'licencia.pdf', 'Licencia')])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_documents(html)

    def test_pagination_never_silently_truncated(self):
        for link in ('<a rel="next" href="/documentos/page/2/">Más</a>',
                     '<a href="?page=2">2</a>',
                     '<nav class="pagination"><a href="?p=2">2</a></nav>'):
            with self.subTest(link=link), self.assertRaises(ValueError):
                parse_documents(HTML.replace('</main>', link + '</main>'))

    def test_real_adapter_path_and_snapshot_update(self):
        adapter = ConstantinaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            state = Path(directory) / 'state.json'
            with patch.object(adapter, '_fetch', side_effect=[HOME_HTML, HTML] * 2) as fetch:
                result = adapter.backfill_proyectos(out)
                first = out.read_bytes()
                adapter.update_proyectos(out, state)
                self.assertEqual(fetch.call_args_list[0].args[0], ENTRY)
            self.assertEqual(out.read_bytes(), first)
            self.assertEqual(result['count'], 1)
            self.assertEqual(json.loads(first)['etapas_publicadas'],
                             ['Actualmente nos encontramos en la Fase 3'])
            self.assertFalse(state.exists())

    def test_failed_refresh_preserves_previous_output(self):
        adapter = ConstantinaAyuntamientoAdapter()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            out.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[HOME_HTML, '<html/>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('constantina')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('41033', 'Sevilla'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with self.assertRaises(NotImplementedError):
            ConstantinaAyuntamientoAdapter().backfill_licencias(Path('unused.jsonl'))


if __name__ == '__main__':
    unittest.main()
