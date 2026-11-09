"""Offline contract/parser tests. Run: python -m unittest municipio.test_ares -v."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from municipio.adapters.ares import AresAyuntamientoAdapter, SOURCE, parse_projects
from municipio.manifest import load_manifest, load_yaml


def fixture():
    return '''<main><div class="page-content"><div class="elementor-text-editor">
<h5>APROBACIÓN DEFINITIVA PXOM 2020</h5><h5>PLAN XERAL DE ORDENACIÓN MUNICIPAL DE ARES</h5>
<p>Documento refundido do PGOM de Ares conforme á orde de aprobación definitiva da Consellería de Medio Ambiente, Territorio e Vivenda do 05/02/2020</p>
<h5>ÍNDICE DOCUMENTOS:</h5><p><a href="/wp-content/uploads/2021/08/00_PGOM_ARES_2020_INDICE.pdf">Índice</a></p>
<h5>DOCUMENTO III: MEMORIA XUSTIFICATIVA</h5><p><a href="/wp-content/uploads/2021/10/03_PGOM_ARES_2020_MEMORIA_XUSTIFICATIVA.pdf">Memoria</a></p>
<h5>DOCUMENTO V: NORMATIVA URBANÍSTICA</h5><p><a href="/wp-content/uploads/2021/10/05_PGOM_ARES_2020_NORMATIVA.pdf">Normativa</a></p>
</div></div></main>'''


class AresTests(unittest.TestCase):
    def test_group_documents_and_preserve_provenance(self):
        rows = parse_projects(fixture())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '15004')
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['documentos'][2]['seccion'], 'DOCUMENTO V: NORMATIVA URBANÍSTICA')
        self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))
        self.assertEqual(row['fecha_aprob'], '2020-02-05')
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        self.assertIn('Cobertura parcial', row['limitations'][0])

    def test_no_navigation_news_or_forms_as_projects(self):
        for html in ('', '<main>Noticias de Ares</main>',
                     fixture().replace('05_PGOM_ARES_2020_NORMATIVA.pdf', 'solicitud_licencia.pdf')):
            with self.subTest(html=html[:30]), self.assertRaises(ValueError):
                parse_projects(html)

    def test_deduplicate_docs_and_ignore_outside_widget(self):
        extra = '<a href="/wp-content/uploads/2021/08/00_PGOM_ARES_2020_INDICE.pdf">Índice</a>'
        html = fixture().replace('</div></div>', extra + '</div></div>')
        html += '<footer><a href="/modelo.pdf">Solicitud licencia</a></footer>'
        row = parse_projects(html)[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['id'], parse_projects(fixture())[0]['id'])

    def test_pagination_fails_instead_of_truncating(self):
        for markup in ('<a rel="next" href="?page=2">Más</a>', '<div class="page-numbers">2</div>'):
            with self.subTest(markup=markup), self.assertRaisesRegex(ValueError, 'pagination'):
                parse_projects(fixture() + markup)

    def test_ambiguous_new_instrument_and_changed_version_fail(self):
        for html in (fixture() + fixture(), fixture().replace('PXOM 2020', 'PXOM 2026'),
                     fixture().replace('</div></div>', '<h5>OUTRO PLAN</h5></div></div>')):
            with self.assertRaises(ValueError):
                parse_projects(html)

    def test_foreign_pdf_and_foreign_origin_rejected(self):
        with self.assertRaises(ValueError):
            parse_projects(fixture().replace('href="/wp-content', 'href="https://example.org/wp-content'))
        with self.assertRaises(ValueError):
            parse_projects(fixture(), 'https://example.org/es/planes/')

    def test_missing_and_invalid_order_date_rejected(self):
        for replacement in ('', '31/02/2020', '05/02/2020 e 06/02/2020'):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                parse_projects(fixture().replace('05/02/2020', replacement))

    @patch('municipio.adapters.ares.requests.get')
    def test_refresh_and_capture(self, get):
        get.return_value = Mock(url=SOURCE, text=fixture(), content=fixture().encode())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adapter = AresAyuntamientoAdapter(config={'capture_dir': temp})
            out = root / 'proyectos.jsonl'
            result = adapter.update_proyectos(out, root / 'state.json')
            self.assertEqual(result['rows'], 1)
            self.assertEqual(json.loads(out.read_text())['id'], 'ares-pxom-2020')
            self.assertEqual((root / 'planes.html').read_text(), fixture())
            self.assertFalse((root / 'state.json').exists())
            adapter.backfill_licencias(root / 'licencias.jsonl')
            self.assertEqual((root / 'licencias.jsonl').read_text(), '')

    @patch('municipio.adapters.ares.requests.get')
    def test_failure_preserves_existing_snapshot(self, get):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'records.jsonl'
            out.write_text('previous snapshot')
            get.return_value = Mock(url=SOURCE, text='<main>unavailable</main>')
            with self.assertRaises(ValueError):
                AresAyuntamientoAdapter().backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')
            get.return_value.raise_for_status.side_effect = requests.HTTPError('503')
            with self.assertRaises(requests.HTTPError):
                AresAyuntamientoAdapter().backfill_proyectos(out)
            get.return_value = Mock(url='https://example.org/es/planes/', text=fixture())
            with self.assertRaises(ValueError):
                AresAyuntamientoAdapter().backfill_proyectos(out)

    def test_manifest(self):
        manifest = load_manifest('ares')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia), ('Ares', 'A Coruña'))
        self.assertEqual(raw['codigo_ine'], '15004')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertEqual(manifest.portal.adapter, 'municipio.adapters.ares:AresAyuntamientoAdapter')


if __name__ == '__main__':
    unittest.main()
