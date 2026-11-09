import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from municipio.adapters.valle_gran_rey import (
    DOCUMENT_PATH, SOURCE, ValleGranReyAyuntamientoAdapter, parse_inventory,
)
from municipio.manifest import load_manifest, load_yaml


def document(title, name, date='12 de Junio de 2026'):
    return (f'<tr><td>{title}</td><td><a href="{DOCUMENT_PATH}2025/{name}.pdf">PDF</a>'
            f'<a href="{DOCUMENT_PATH}2025/{name}.txt">TXT</a></td><td>{date}</td></tr>')


def inventory(rows, extra=''):
    return f'<main><table><tbody>{rows}</tbody></table>{extra}</main>'


class ValleGranReyTests(unittest.TestCase):
    def test_grouping_provenance_and_date_semantics(self):
        first = document('Certificado acuerdo plenario inicio estudio ambiental para PGO', 'certificado')
        html = inventory(first + document('Encargo a GESPLAN fase 3 PGO', 'encargo') + first
                         + document('PIOG 2011', 'insular')
                         + document('Modelo solicitud licencia PGO', 'modelo'))
        rows = parse_inventory(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['codigo_ine'], '38049')
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(len(row['documentos'][0]['formatos']), 2)
        self.assertEqual(row['documentos'][0]['ultima_actualizacion_texto'], '12 de Junio de 2026')
        self.assertEqual(row['documentos'][0]['inventory_url'], SOURCE)
        for key in ('fecha', 'fecha_publicacion', 'fecha_aprob', 'fecha_acuerdo', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)
        self.assertFalse(row['publication_ready'])

    def test_empty_or_unrelated_is_error(self):
        for html in ('<html></html>', inventory(''), inventory(document('PIOG 2011', 'insular'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_pagination_fails_instead_of_truncating(self):
        for extra in ('<a rel="next" href="?p=2">Más</a>', '<a href="?page=2">2</a>',
                      '<ul class="pagination"><li>2</li></ul>'):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'pagination'):
                parse_inventory(inventory(document('Encargo PGO', 'encargo'), extra))

    def test_invalid_document_and_missing_pdf_fail(self):
        for html in (inventory(document('Encargo PGO', 'encargo')).replace(
                DOCUMENT_PATH, 'https://example.org/'),
                inventory(document('Encargo PGO', 'encargo')).replace('.pdf', '.txt')):
            with self.assertRaises(ValueError):
                parse_inventory(html)

    def test_live_method_writes_snapshot_and_preserves_output_on_error(self):
        response = Mock(url=SOURCE, text=inventory(document('Encargo PGO', 'encargo')))
        adapter = ValleGranReyAyuntamientoAdapter('valle-gran-rey')
        with tempfile.TemporaryDirectory() as tmp, patch(
                'municipio.adapters.valle_gran_rey.requests.get', return_value=response):
            out = Path(tmp) / 'proyectos.jsonl'
            result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['written'], 1)
            self.assertEqual(json.loads(out.read_text())['id'], 'valle-gran-rey-pgo')
            previous = out.read_bytes()
            response.text = '<main></main>'
            with self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(out.read_bytes(), previous)
            response.url = 'https://example.org/'
            with self.assertRaisesRegex(ValueError, 'redirect'):
                adapter.backfill_proyectos(out)

    def test_manifest_and_disabled_licences(self):
        path = Path(__file__).resolve().parents[1] / 'data/municipios/valle-gran-rey/manifest.yaml'
        manifest = load_manifest(path)
        raw = load_yaml(path)
        self.assertEqual(raw['codigo_ine'], '38049')
        self.assertEqual(manifest.provincia, 'Santa Cruz de Tenerife')
        self.assertFalse(manifest.licencias.enabled)
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        with self.assertRaises(NotImplementedError):
            ValleGranReyAyuntamientoAdapter(manifest.slug).backfill_licencias(Path('/unused'))


if __name__ == '__main__':
    unittest.main()
