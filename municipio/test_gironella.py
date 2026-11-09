import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.gironella import GironellaAyuntamientoAdapter, SOURCE, parse_inventory
from municipio.manifest import load_manifest, load_yaml

PDF = 'https://gironella.cat/wp-content/uploads/2023/09/serreta.pdf'
RPUC = 'https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/86191/documents'


def card(title='Pla especial urbanístic de la casa rural la Serreta', links=None,
         category="Ordenances d'urbanisme"):
    links = links if links is not None else [(PDF, 'Veure ordenança')]
    return ('<div class="ordenanca"><div class="titol-ordenanca">' + title +
            '</div><div class="tipologia">' + category + '</div>' +
            ''.join(f'<a href="{url}">{label}</a>' for url, label in links) + '</div>')


def page(cards, **pager_changes):
    pager = dict(page=1, total_pages=1, total_rows=len(cards), total_rows_unfiltered=len(cards))
    pager.update(pager_changes)
    return ('<div class="facetwp-template" data-name="llista_normativa">' +
            ''.join(cards) + '</div><script>window.FWP_JSON = ' +
            json.dumps({'preload_data': {'settings': {'pager': pager}}}) + ';</script>')


class GironellaTests(unittest.TestCase):
    def test_group_nested_documents_and_preserve_labels(self):
        nested = card('Revisió pla general ordenació urbana municipal', [])
        nested = nested.replace('</div></div>', '</div><div class="documents">' +
                                f'<a href="{PDF}">Veure ordenança</a><a href="{RPUC}">Veure enllaç</a>' +
                                f'<a href="{PDF}">Memòria</a></div></div>')
        row, = parse_inventory(page([nested]))
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['labels'], ['Veure ordenança', 'Memòria'])
        self.assertEqual(row['documentos'][1]['url'], RPUC)

    def test_exclude_forms_taxes_subsidies_and_news(self):
        rows = parse_inventory(page([card(), card('Sol·licitud llicència urbanística'),
            card('Ordenança reguladora de subvencions de façanes'),
            card('Taxa per llicències urbanístiques', category='Ordenances fiscals'),
            card('Licitació de les obres'), card('Festa major')]))
        self.assertEqual(len(rows), 1)

    def test_no_dates_or_coordinates_inferred_from_urls(self):
        row, = parse_inventory(page([card()]))
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[field])
        self.assertFalse(row['publication_ready'])
        self.assertEqual(row['codigo_ine'], '08092')

    def test_refuse_incomplete_or_filtered_inventory(self):
        for pager in ({'total_pages': 2}, {'page': 2}, {'total_rows': 2},
                      {'total_rows_unfiltered': 9}):
            with self.subTest(pager=pager), self.assertRaises(ValueError):
                parse_inventory(page([card()], **pager))

    def test_refuse_changed_markup_empty_documents_and_foreign_links(self):
        for html in ('<html>Login</html>', page([card('Notícia')]), page([card(links=[])]),
                     page([card(links=[('https://example.org/project.pdf', 'Document')])]),
                     page([card()]).replace('window.FWP_JSON', 'window.OTHER')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_identity_independent_of_document_order(self):
        a, = parse_inventory(page([card(links=[(PDF, 'A'), (RPUC, 'B')])]))
        b, = parse_inventory(page([card(links=[(RPUC, 'B'), (PDF, 'A')])]))
        self.assertEqual(a['id'], b['id'])

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('gironella')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('08092', 'Barcelona'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'licencias.jsonl'
            with patch('municipio.adapters.gironella.requests.get') as get:
                result = GironellaAyuntamientoAdapter().backfill_licencias(output)
                get.assert_not_called()
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
