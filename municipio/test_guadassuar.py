import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.guadassuar import GuadassuarAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def document(name):
    return f'<a href="/wp-content/uploads/Urbanisme/{name}.pdf"><span class="filename">{name}.pdf</span></a>'


def accordion(title, body, anchor='docs'):
    return f'<div class="sek-accord-item"><span class="sek-inner-accord-title">{title}</span><div class="sek-accord-content" id="{anchor}">{body}</div></div>'


def fixture():
    return ('<section class="entry-content"><h1 class="sek-heading">01 – Planejament urbanístic en tramitació</h1>'
            + accordion('PLA DE REFORMA INTERIOR La Garrofera', document('PRI/anexo') + document('PRI/plano'), 'pri')
            + accordion('MODIFICACIÓ NUM 9 DEL PLA GENERAL', document('TRAMIT/MOD9/acord'))
            + '<h1 class="sek-heading">02 – Planejament urbanístic aprovat. (PGOU)</h1>'
            + accordion('ANUNCIS', document('PGOU/anunci'))
            + accordion('TOM I', document('PGOU/memoria') + document('PGOU/anunci'))
            + accordion('CORRECCIÓ ERRORS', document('PGOU/correccio'))
            + accordion('MODIFICACIONS', '<p>APROVADES</p><ol><li>MODIFICACIÓ 7 PGOU TRINQUET<ul><li>'
                        + document('MOD7/pla') + '</li><li>' + document('MOD7/bop')
                        + '</li></ul></li><li>MODIFICACIÓ 8 PGOU<ul><li>' + document('MOD8/acord')
                        + '</li><li>' + document('MOD8/correccio') + '</li></ul></li></ol>')
            + '<h1 class="sek-heading">03 – Informació pública de projectes</h1>'
            + '<a href="/llicencia-ambiental/">Llicència ambiental</a>'
            + document('formulari-llicencia') + '</section>')


class GuadassuarTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        rows = parse_inventory(fixture())
        self.assertEqual(len(rows), 5)
        by_id = {r['id']: r for r in rows}
        self.assertEqual(len(by_id['guadassuar-plan-pgou']['documentos']), 3)
        self.assertEqual(len(by_id['guadassuar-plan-mod-7']['documentos']), 2)
        self.assertTrue(all('MOD8/' in d['url'] for d in by_id['guadassuar-plan-mod-8']['documentos']))
        for row in rows:
            self.assertEqual(row['codigo_ine'], '46139')
            self.assertFalse(row['publication_ready'])
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
                self.assertNotIn(field, row)
            self.assertFalse(any('formulari' in d['url'] for d in row['documentos']))

    def test_missing_or_empty_inventory(self):
        for html in ('', '<section class="entry-content"></section>'):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_missing_documents(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture().replace(document('TRAMIT/MOD9/acord'), ''))

    def test_unknown_group_fails(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture().replace('TOM I', 'NOU INSTRUMENT'))

    def test_pagination_fails_without_partial_result(self):
        for marker in ('<a rel="next" href="/urbanisme/2/">Next</a>',
                       '<a href="?paged=2">2</a>', '<div class="load-more"></div>'):
            with self.assertRaises(ValueError):
                parse_inventory(fixture().replace('</section>', marker + '</section>'))

    def test_unexpected_document_origin(self):
        with self.assertRaises(ValueError):
            parse_inventory(fixture().replace('/wp-content/uploads/Urbanisme/PRI/anexo.pdf', 'https://example.org/a.pdf'))

    def test_backfill_update_and_disabled_licences(self):
        class Response:
            url = SOURCE
            text = fixture()
            def raise_for_status(self):
                pass
        adapter = GuadassuarAyuntamientoAdapter('guadassuar')
        with tempfile.TemporaryDirectory() as temp, patch('municipio.adapters.guadassuar.requests.get', return_value=Response()):
            path = Path(temp) / 'proyectos.jsonl'
            self.assertEqual(adapter.backfill_proyectos(path)['count'], 5)
            old = path.read_text()
            adapter.update_proyectos(path, Path(temp) / 'state.json')
            self.assertEqual(old, path.read_text())
            self.assertEqual(len([json.loads(line) for line in old.splitlines()]), 5)
            self.assertTrue(adapter.backfill_licencias(path)['disabled'])
            self.assertEqual(path.read_text(), '')

    def test_manifest(self):
        manifest = load_manifest('guadassuar')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Guadassuar', 'Valencia', '46139'))
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])


if __name__ == '__main__':
    unittest.main()
