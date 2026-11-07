"""Offline semantic regressions for the municipal document inventory."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.ceuti import CeutiAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest


def fixture():
    sections = {
        'OBRAS': ['LICENCIA URBANÍSTICA (obra mayor)', 'SOLICITUD PRORROGA LICENCIA'],
        'AVANCE MODIFICACION PUNTUAL IX PGMO': [
            'Publicación BORM – Anuncio Información Pública.',
            'Proyecto modificación puntual PGMO de Ceutí',
            'Modelo solicitud inicio evaluación ambiental',
            'Documento inicial estratégico', 'Anuncio información pública',
        ],
        'PGMO': ['PLAN PARCIAL, USOS Y DESTINOS DEL SUELO', 'NORMAS URBANISTICAS',
                 'PG0903_02 MEMORIA MODIFICACION 2 v01d', 'PG0903_03 PLANOS MODIFICACION 2 V01',
                 'PLANO GENERAL', 'PLANOS_MOD_PUNTUAL_I',
                 'PUBLICACIÓN BORM modificación puntual I del PGMO',
                 'ORDENACIÓN ESTRUCTURAL MODIFICADA_V03 (pub. 13/03/2018)'],
    }
    html = '<div class="post-content"><h2>Urbanismo</h2>'
    for section, labels in sections.items():
        html += f'<h2><strong>{section}</strong></h2><ul>'
        for i, label in enumerate(labels):
            html += f'<li><a href="/wp-content/uploads/2026/10/{section[:4]}-{i}.pdf">{label}</a></li>'
        html += '</ul>'
    return html + '</div>'


class CeutiTests(unittest.TestCase):
    def test_grouping_excludes_forms_and_preserves_documents(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 5)
        self.assertEqual(sum(len(r['documentos']) for r in rows), 12)
        by_id = {r['id']: r for r in rows}
        self.assertEqual(len(by_id['ceuti-plan-mp-ix']['documentos']), 4)
        self.assertEqual(len(by_id['ceuti-plan-mp-ii']['documentos']), 2)
        self.assertNotIn('SOLICITUD', str(rows))
        self.assertNotIn('LICENCIA', str(rows))

    def test_no_inferred_dates_status_or_coordinates(self):
        for row in parse_inventory(fixture()):
            self.assertEqual(row['codigo_ine'], '30018')
            for field in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])

    def test_document_filename_changes_do_not_change_identity(self):
        first = parse_inventory(fixture())
        second = parse_inventory(fixture().replace('/2026/10/', '/2027/01/'))
        self.assertEqual([r['id'] for r in first], [r['id'] for r in second])

    def test_missing_content_or_group_fails(self):
        for html in ('<p>Login</p>', fixture().replace('MODIFICACION 2', 'UNRECOGNIZED')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_new_document_and_pagination_fail_instead_of_truncating(self):
        for extra in ('<a href="/new.pdf">Nuevo plan especial</a>', '<a rel="next" href="?page=2">2</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(fixture().replace('</div>', extra + '</div>'))

    def test_external_document_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture().replace('/wp-content/', 'https://other.example/wp-content/'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('ceuti')
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'Murcia')
        adapter = CeutiAyuntamientoAdapter('ceuti')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
