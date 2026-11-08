"""Offline parser regressions: grouping, provenance, pagination and wrong content."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.san_fulgencio import (
    SOURCE, SanFulgencioAyuntamientoAdapter, parse_inventory, parse_notice,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


def inventory(extra=''):
    links = ''.join(f'<a href="/wp-content/uploads/2024/05/{i}.pdf">{label}</a>' for i, label in enumerate(
        ['Memoria', 'Normativa', 'Ordenanza', 'Planos', 'Plano Ordenación', 'Impacto Ambiental']))
    return ('<h1>Urbanismo – Plan General</h1><div id="main-content"><div class="et_pb_post_content">' + links +
            '<a href="/wp-content/uploads/2016/10/plan-general.zip">Modificacion Puntual Nº 1 PGOU</a>' +
            '<a href="/wp-content/uploads/2021/10/mod3.pdf">Modificacion Puntual Nº 3 PGOU</a>' + extra + '</div></div>')


NOTICE = '''Boletín Oficial de la Provincia de Alicante Nº 50 de 12/03/2020
EXPTE. 04/20.- SAN FULGENCIO. Modificación Puntual n.º 3 del Plan General (PL-
15/0298)
La Comisión Territorial de Urbanismo, en sesión celebrada el día 4 de febrero de 2020, adoptó por unanimidad
El Pleno acordó aprobación provisional el 29 de enero de 2020.
Plan General aprobado definitivamente por resolución del Conseller competente en urbanismo de fecha 20 de mayo de 1998.
Aprobar definitivamente la Modificación Puntual n.º 3 del Plan General.'''


class SanFulgencioTests(unittest.TestCase):
    def test_documents_grouped_and_ambiguous_zip_excluded(self):
        docs, mod, excluded = parse_inventory(inventory())
        self.assertEqual(len(docs), 6)
        self.assertEqual(mod['titulo'], 'Modificacion Puntual Nº 3 PGOU')
        self.assertEqual(len(excluded), 1)
        self.assertTrue(all(d['source_url'] == SOURCE for d in docs))
        self.assertEqual(len(parse_inventory(inventory('<a href="/wp-content/uploads/2024/05/0.pdf">Memoria</a>'))[0]), 6)

    def test_explicit_dates_not_upload_or_provisional_dates(self):
        dates = parse_notice(NOTICE)
        self.assertEqual(dates['fecha_publicacion'], '2020-03-12')
        self.assertEqual(dates['fecha_acuerdo'], '2020-02-04')
        self.assertEqual(dates['base_fecha_aprob'], '1998-05-20')
        self.assertEqual(dates['expediente_planeamiento'], 'PL-15/0298')

    def test_fail_closed_content_and_pagination(self):
        for content in ['<h1>Login</h1>', '<a href="x.pdf">Solicitud de licencia</a>',
                        inventory('<a rel="next" href="?page=2">2</a>'),
                        inventory('<a href="/wp-content/uploads/2026/extra.pdf">Plan nuevo</a>'),
                        inventory().replace('>Normativa<', '>Otro<'),
                        inventory().replace('/wp-content/uploads/2024/05/0.pdf', 'https://example.org/0.pdf')]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                parse_inventory(content)
        for text in ['', NOTICE.replace('SAN FULGENCIO', 'OTRO MUNICIPIO'),
                     NOTICE.replace('Aprobar definitivamente', 'Proponer'),
                     NOTICE.replace('12/03/2020', '31/02/2020')]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_notice(text)

    def test_backfill_and_update_keep_two_instruments(self):
        adapter = SanFulgencioAyuntamientoAdapter('san-fulgencio')
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), b'%PDF-fixture'] * 2), patch(
                'municipio.adapters.san_fulgencio.subprocess.run'
            ) as process:
                process.return_value.stdout = NOTICE.encode()
                adapter.backfill_proyectos(out)
                original = out.read_bytes()
                adapter.update_proyectos(out, Path(folder) / 'state.json')
                self.assertEqual(original, out.read_bytes())
                rows = [json.loads(line) for line in out.read_text().splitlines()]
                self.assertEqual(len(rows), 2)
                self.assertEqual(len(rows[0]['documentos']), 6)
                self.assertIsNone(rows[0]['fecha_publicacion'])
                self.assertEqual(rows[1]['fecha_acuerdo'], '2020-02-04')
                self.assertEqual(rows[1]['fecha_publicacion'], '2020-03-12')
                self.assertTrue(all(r['geometry'] is None and r['lat'] is None and r['lon'] is None for r in rows))
                self.assertIn('notice', str(process.call_args).lower())
            with patch.object(adapter, '_fetch', return_value=b'<h1>Login</h1>'), self.assertRaises(ValueError):
                adapter.backfill_proyectos(out)
            self.assertEqual(original, out.read_bytes())

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('san-fulgencio')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.provincia), ('03118', 'Alicante'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'licences.jsonl'
            self.assertEqual(adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
