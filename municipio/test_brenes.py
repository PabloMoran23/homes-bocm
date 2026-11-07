"""Offline parser/contract tests; live captures are kept separately in evidence/."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.brenes import BrenesAyuntamientoAdapter, SOURCE, parse_article, parse_inventory
from municipio.manifest import load_manifest, load_yaml

ARTICLE = '''<main><div class="pm-noticia-content">
<h2 class="detail-t">Inversiones municipales</h2><div class="detail-date">21/11/2024</div>
<div class="detail-p"><p>El Ayuntamiento presenta proyectos que ejecutará con Sevilla 107.</p>
<p>Se prevé la remodelación del Parque del Bodegón, junto al arroyo Buenavista.</p>
<p>El antiguo Mercado de Abastos de la calle Cuadra y González: se pretende rehabilitarlo.</p>
<p>Se acometerá la primera fase de reforma y rehabilitación.</p>
<a href="/docs/mercado.pdf">Memoria</a></div></div></main>'''


def listing(*names):
    return '<main><div class="listado-simple">' + ''.join(
        f'<div class="item"><h3><a href="{name}/?urlBack=">{name}</a></h3></div>' for name in names
    ) + '</div></main>'


class BrenesTests(unittest.TestCase):
    def test_inventory_deduplicates_and_removes_tracking(self):
        self.assertEqual(list(parse_inventory(listing('obra', 'obra'))), [SOURCE + 'obra/'])

    def test_empty_or_changed_inventory_fails(self):
        for html in ('<main/>', listing()):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_instead_of_truncating(self):
        for control in ('<nav class="pagination">2</nav>', '<a href="?page=2" rel="next">2</a>', '<a href="?page=2">Siguiente</a>'):
            with self.assertRaises(ValueError):
                parse_inventory(listing('obra').replace('</main>', control + '</main>'))

    def test_two_physical_proposals_with_separate_descriptions(self):
        rows = parse_article(ARTICLE, SOURCE + 'obra/')
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertNotIn('Mercado', rows[0]['descripcion'])
        self.assertNotIn('Parque', rows[1]['descripcion'])
        for row in rows:
            self.assertEqual(row['fecha_publicacion'], '2024-11-21')
            self.assertEqual(row['codigo_ine'], '41018')
            self.assertEqual(len(row['documentos']), 2)
            self.assertFalse(row['publication_ready'])
            for forbidden in ('fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'coordinates', 'fase'):
                self.assertNotIn(forbidden, row)

    def test_forms_procurement_and_unrelated_news_excluded(self):
        for text in ('Solicitud de licencia de obras', 'Anuncio de licitación del mercado', 'Reivindicación de mejora de carreteras'):
            html = '<main><div class="pm-noticia-content"><h2 class="detail-t">' + text + '</h2><div class="detail-p"><p>' + text + '</p></div></div></main>'
            self.assertEqual(parse_article(html, SOURCE + 'otra/'), [])

    def test_missing_date_is_not_fabricated(self):
        html = ARTICLE.replace('<div class="detail-date">21/11/2024</div>', '')
        self.assertNotIn('fecha_publicacion', parse_article(html, SOURCE + 'obra/')[0])

    def test_unexpected_host_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory(listing('https://example.org/news'))

    def test_refresh_groups_documents_and_preserves_output_on_failure(self):
        adapter = BrenesAyuntamientoAdapter('brenes')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[listing('one', 'two'), ARTICLE, ARTICLE.replace('Inversiones municipales', 'Segundo documento')]):
                result = adapter.backfill_proyectos(output)
            self.assertEqual(result['count'], 2)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(rows[0]['documentos']), 3)
            original = output.read_bytes()
            with patch.object(adapter, '_fetch', return_value='<main/>'):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_bytes(), original)

    def test_manifest_contract(self):
        manifest = load_manifest('brenes')
        raw = load_yaml(manifest.path)
        self.assertEqual((manifest.nombre, manifest.provincia, raw['codigo_ine']), ('Brenes', 'Sevilla', '41018'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
