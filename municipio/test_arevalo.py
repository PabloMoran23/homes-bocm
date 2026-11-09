import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.arevalo import ArevaloAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def panel(number, phase, docs):
    links = ''.join(
        f'<a class="pgd-doc-link" href="/wp-content/uploads/{filename}.pdf">'
        f'<span class="pgd-doc-name">{title}</span></a>'
        for title, filename in docs)
    return (f'<button id="tab-{number}">Modificación puntual n.º {number} - {phase}</button>'
            f'<div class="pgd-tabpanel" aria-labelledby="tab-{number}">{links}</div>')


FIXTURE = '<h1>Normativa&nbsp;tramitación</h1>' + panel('28', 'Aprobación provisional', [
    ('Modificación puntual nº 28 - Aprobación provisional', 'mp28')]) + panel(
    '27', 'Aprobación inicial', [('Textos Modificación Puntual Nº 27', 'textos27'),
                               ('Planos Modificación Puntual Nº 27', 'planos27')])


class ArevaloTests(unittest.TestCase):
    def test_grouping_provenance_and_semantics(self):
        rows = parse_inventory(FIXTURE)
        self.assertEqual(len(rows), 2)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2])
        self.assertEqual(rows[1]['fase_documental'], 'aprobación inicial')
        self.assertEqual(rows[1]['documentos'][1]['url'],
                         'https://arevalo.es/wp-content/uploads/planos27.pdf')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '05016')
            self.assertEqual(row['url'], SOURCE)
            self.assertFalse(row['estado_actual_verificado'])
            self.assertFalse(row['publication_ready'])
            self.assertIsNone(row['fecha_publicacion'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertNotIn('fase', row)
            self.assertNotIn('lat', row)
            self.assertNotIn('lon', row)

    def test_forms_and_unrelated_links_not_records(self):
        unrelated = '<a href="/licencia.pdf">Licencia de obra mayor</a>'
        rows = parse_inventory(FIXTURE + unrelated)
        self.assertEqual(len(rows), 2)
        with self.assertRaises(ValueError):
            parse_inventory('<h1>Normativa tramitación</h1>' + unrelated)

    def test_changes_fail_instead_of_silent_partial_results(self):
        for html in ('', FIXTURE.replace('mp28.pdf', 'mp28.html'),
                     FIXTURE.replace('Textos Modificación Puntual Nº 27', 'Textos Modificación Puntual Nº 99'),
                     FIXTURE + '<a rel="next" href="?page=2">Siguiente</a>',
                     FIXTURE.replace(
                         '/wp-content/uploads/mp28.pdf', 'https://example.org/foreign.pdf'),
                     FIXTURE.replace('aria-labelledby="tab-27"', 'aria-labelledby="missing"')):
            with self.subTest(html=html[:60]), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_stable_ids_and_duplicate_document_links(self):
        rows = parse_inventory(FIXTURE)
        changed = parse_inventory(FIXTURE.replace('mp28.pdf', 'mp28-revised.pdf'))
        self.assertEqual(rows[0]['id'], changed[0]['id'])
        extra = panel('30', 'Aprobación inicial', [
            ('Textos Modificación Puntual Nº 30', 'mp30'),
            ('Textos Modificación Puntual Nº 30', 'mp30')])
        self.assertEqual(len(parse_inventory(FIXTURE + extra)[2]['documentos']), 1)

    def test_manifest_load_and_refresh(self):
        manifest = load_manifest('arevalo')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia),
                         ('05016', 'Arévalo', 'Ávila'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        response = Mock(url=SOURCE, text=FIXTURE)
        with tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.arevalo.requests.get', return_value=response):
            adapter = ArevaloAyuntamientoAdapter()
            out = Path(tmp) / 'proyectos.jsonl'
            self.assertEqual(adapter.update_proyectos(out, Path(tmp) / 'state.json')['written'], 2)
            self.assertEqual(len([json.loads(s) for s in out.read_text().splitlines()]), 2)
            adapter.backfill_licencias(Path(tmp) / 'licencias.jsonl')
            self.assertEqual((Path(tmp) / 'licencias.jsonl').read_text(), '')
            response.url = 'https://example.org/'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)


if __name__ == '__main__':
    unittest.main()
