import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from municipio.adapters.daimiel import (
    DaimielAyuntamientoAdapter, SOURCES, merge_instruments, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def inventory(sections):
    body = ''
    for title, docs in sections:
        body += '<div class="field__item"><div class="paragraph paragraph--type--text">' + title + '</div></div>'
        body += '<div class="field__item"><div class="paragraph paragraph--type--archivos-asociados">'
        for label, path in docs:
            body += f'<span class="file"><a href="/sites/default/files/{path}.pdf">{label}</a></span>'
        body += '</div></div>'
    return '<div class="field--name-field-paragraphs">' + body + '</div>'


POM = inventory([
    ('Plan de Ordenación Municipal 2009', [('Normas urbanísticas', 'normas'), ('Plano 1', 'plano')]),
    ('Modificaciones al Plan de Ordenación Municipal 2009', [
        ('Modificación puntual nº9 - Aprobación definitiva', 'mod9'),
        ('Modificación puntual nº9 - Documento ambiental estratégico', 'ambiental9'),
        ('Modificación puntual nº10', 'mod10'),
        ('Modificaciones al Plan de Ordenación Municipal', 'resumen')]),
    ('Planes de emergencia y protección civil', [('Convocatoria', 'emergencia')]),
])
PENDING = inventory([('Normativa y documentos en tramitación', [
    ('Modificación puntual 9 delimitación área suelo rústico', 'inicio9'),
    ('Modificación / innovación puntual nº 6 al POM Daimiel 2009', 'mod6'),
    ('Modelo de solicitud de licencia de obra urbanística', 'licencia'),
    ('Ordenanza de vertido', 'ordenanza'),
])])


class DaimielTests(unittest.TestCase):
    def test_grouping_provenance_and_semantics(self):
        rows = merge_instruments([parse_inventory(POM, SOURCES[0]), parse_inventory(PENDING, SOURCES[1])])
        self.assertEqual(len(rows), 4)
        mod9 = next(row for row in rows if row['id'].endswith('mod-9'))
        self.assertEqual(len(mod9['documentos']), 3)
        self.assertEqual(mod9['source_urls'], list(SOURCES))
        pom = next(row for row in rows if row['id'] == 'daimiel-pom-2009')
        self.assertEqual(len(pom['documentos']), 3)
        mod10 = next(row for row in rows if row['id'].endswith('mod-10'))
        self.assertEqual(len(mod10['documentos']), 1)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '13039')
            self.assertFalse(row['publication_ready'])
            for forbidden in ['fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase']:
                self.assertNotIn(forbidden, row)

    def test_fail_closed(self):
        for html in ['', inventory([('Ordenanzas', [('Ordenanza', 'o')])]),
                     POM + '<nav class="pager">2</nav>',
                     POM + '<a rel="next" href="?page=1">Next</a>',
                     POM.replace('/sites/default/files/normas.pdf', 'https://example.org/a.pdf')]:
            with self.subTest(html=html[:50]), self.assertRaises(ValueError):
                parse_inventory(html, SOURCES[0])

    def test_live_method_writes_only_after_both_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'rows.jsonl'
            adapter = DaimielAyuntamientoAdapter('daimiel')
            responses = [Mock(text=POM, url=SOURCES[0]), Mock(text=PENDING, url=SOURCES[1])]
            with patch('municipio.adapters.daimiel.requests.get', side_effect=responses):
                result = adapter.backfill_proyectos(output)
            self.assertEqual(result['live_records'], 4)
            self.assertEqual(len([json.loads(line) for line in output.read_text().splitlines()]), 4)
            output.write_text('previous')
            with patch('municipio.adapters.daimiel.requests.get', side_effect=[responses[0], RuntimeError('offline')]):
                with self.assertRaises(RuntimeError):
                    adapter.update_proyectos(output, Path(tmp) / 'state.json')
            self.assertEqual(output.read_text(), 'previous')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('daimiel')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('13039', 'Ciudad Real'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with self.assertRaises(NotImplementedError):
            DaimielAyuntamientoAdapter('daimiel').backfill_licencias(Path('unused'))


if __name__ == '__main__':
    unittest.main()
