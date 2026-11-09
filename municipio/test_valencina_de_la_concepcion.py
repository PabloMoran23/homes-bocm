import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.valencina_de_la_concepcion import (
    SOURCE, ValencinaDeLaConcepcionAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest


def section(name, title, filename):
    return (f'<div class="download-block"><div class="title">{name}</div>'
            f'<table><tr><td><a href="/export/sites/valencina/.galleries/{filename}.pdf">'
            f'{title}</a></td></tr></table></div>')


FIXTURE = ('<p>Documentación disponible asociada al PGOM de Valencina de la Concepción</p>'
           + section('FASE III (AVANCE- MEMORIA)', '01 AVANCE PGOM_MEMORIA', 'memoria')
           + section('FASE III (DIE - PLANOS)', '1 DIE PLANIFICACIÓN URBANÍSTICA GENERAL', 'die'))


class ValencinaTests(unittest.TestCase):
    def test_groups_instrument_and_preserves_all_documents(self):
        rows = parse_inventory(FIXTURE + section('FASE IV', 'Anexo', 'anexo'))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 3)
        self.assertEqual(row['codigo_ine'], '41096')
        self.assertEqual(row['provincia'], 'Sevilla')
        self.assertEqual(row['documentos'][1]['secciones'], ['FASE III (DIE - PLANOS)'])
        for field in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertNotIn('fase', row)

    def test_duplicate_document_retains_sections(self):
        row = parse_inventory(FIXTURE + section('OTRA SECCIÓN', 'Memoria', 'memoria'))[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos'][0]['secciones']), 2)

    def test_no_silent_pagination(self):
        for pagination in ('<a rel="next" href="?page=2">2</a>',
                           '<ul class="pagination"><li>2</li></ul>',
                           '<a href="?page=2">Siguiente</a>'):
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(FIXTURE + pagination)

    def test_rejects_forms_empty_wrong_identity_and_document_origin(self):
        for html in ('', '<a href="form.pdf">Solicitud de licencia</a>',
                     FIXTURE.replace('Valencina de la Concepción', 'Otro municipio'),
                     FIXTURE.replace('01 AVANCE PGOM_MEMORIA', 'Solicitud de licencia'),
                     FIXTURE.replace('/export/sites/valencina/.galleries/memoria.pdf', 'https://example.org/memoria.pdf')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_adapter_refresh_and_manifest(self):
        manifest = load_manifest('valencina-de-la-concepcion')
        self.assertFalse(manifest.licencias.enabled)
        adapter = ValencinaDeLaConcepcionAyuntamientoAdapter(manifest.slug)
        response = Mock(url=SOURCE, text=FIXTURE)
        with tempfile.TemporaryDirectory() as tmp, patch(
            'municipio.adapters.valencina_de_la_concepcion.requests.get', return_value=response
        ):
            output = Path(tmp) / 'rows.jsonl'
            report = adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(report['count'], 1)
            self.assertEqual(len(json.loads(output.read_text())['documentos']), 2)
            self.assertTrue(adapter.backfill_licencias(output)['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
