import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cervera import (
    CerveraAyuntamientoAdapter, group_notices, parse_inventory, parse_notice,
)
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter

PDF = 'https://ebop.diputaciolleida.cat/aplicacions/bop/bopV1/fitxers/pdf/2025/54/20255402260.pdf'


def inventory(extra=''):
    return f'''<h1>Ajuntament de Cervera</h1>{extra}<table class="adjunts">
    <thead><tr><th>Data de publicació</th></tr></thead><tbody><tr>
    <td><time datetime="2025-03-19">19/03/2025</time></td><td>BOPL</td><td>54</td>
    <td>Aprovació definitiva<br>Pla especial urbanístic</td><td><a href="{PDF}">PDF</a></td>
    </tr><tr><td><time datetime="2023-06-02"></time></td><td>DOGC</td><td>8929</td>
    <td>Aprovació definitiva<br>Pla especial</td><td><a href="https://dogc.gencat.cat/">DOGC</a></td>
    </tr></tbody></table>'''


TEXT = '''Núm. BOP 54 · Data 19-03-2025 EDICTE
Aprovació provisional del Pla Especial Urbanístic.
Per acord del Ple en sessió celebrada el dia 20 de febrer de 2025,
s'ha aprovat provisionalment el Pla Especial Urbanístic de l'ampliació del dipòsit
controlat de residus municipals. Remetre per a la seva aprovació definitiva.
Cervera https://cervera.sedelectronica.es/ en data 14/03/2025'''


class CerveraTests(unittest.TestCase):
    def test_inventory_filters_are_reported(self):
        notices, excluded = parse_inventory(inventory())
        self.assertEqual(len(notices), 1)
        self.assertEqual(excluded, 1)
        self.assertEqual(notices[0]['fecha_publicacion'], '2025-03-19')

    def test_original_overrules_incorrect_summary(self):
        notice = parse_notice(TEXT, parse_inventory(inventory())[0][0])
        self.assertEqual(notice['fase'], 'aprobación provisional')
        self.assertEqual(notice['fase_inventario'], 'Aprovació definitiva')
        self.assertEqual(notice['fecha_acuerdo'], '2025-02-20')
        self.assertEqual(notice['fecha_publicacion'], '2025-03-19')

    def test_group_initial_and_provisional_preserving_documents(self):
        notice = parse_inventory(inventory())[0][0]
        final = parse_notice(TEXT, notice)
        initial = parse_notice(TEXT.replace('19-03-2025', '12-06-2024')
                              .replace('provisionalment', 'inicialment')
                              .replace('20 de febrer de 2025', '15 de maig de 2024'),
                              {**notice, 'fecha_publicacion': '2024-06-12', 'url': PDF + '?initial'})
        rows = group_notices([final, initial])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 2)
        self.assertEqual(rows[0]['fase'], 'aprobación provisional')
        self.assertIsNone(rows[0]['lat'])
        self.assertFalse(rows[0]['publication_ready'])
        self.assertEqual(rows[0]['id'], group_notices([initial])[0]['id'])

    def test_agreement_numeric_date_and_missing_date(self):
        notice = parse_inventory(inventory())[0][0]
        numeric = TEXT.replace('sessió celebrada el dia 20 de febrer de 2025', 'sessió del dia 23/10/2025')
        self.assertEqual(parse_notice(numeric, notice)['fecha_acuerdo'], '2025-10-23')
        self.assertIsNone(parse_notice(TEXT.replace('sessió celebrada el dia 20 de febrer de 2025', ''), notice)['fecha_acuerdo'])

    def test_changed_or_unusable_sources_fail(self):
        for html in [inventory('<nav class="pagination">2</nav>'), '<h1>Login</h1>',
                     inventory().replace('Ajuntament de Cervera', 'Other municipality')]:
            with self.assertRaises(ValueError):
                parse_inventory(html)
        notice = parse_inventory(inventory())[0][0]
        for text in [TEXT.replace('19-03-2025', '18-03-2025'), 'Formulari de llicència',
                     TEXT.replace('aprovat provisionalment', 'sol·licitat')]:
            with self.assertRaises(ValueError):
                parse_notice(text, notice)

    def test_failed_live_document_does_not_replace_snapshot(self):
        adapter = CerveraAyuntamientoAdapter('cervera')
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'proyectos.jsonl'
            output.write_text('previous snapshot')
            with patch.object(adapter, '_fetch', side_effect=[inventory().encode(), b'login page']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(output)
            self.assertEqual(output.read_text(), 'previous snapshot')
            result = adapter.backfill_licencias(output)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_manifest_and_loader(self):
        manifest = load_manifest('cervera')
        self.assertIsInstance(load_portal_adapter(manifest), CerveraAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], raw['nombre'], raw['provincia']), ('25072', 'Cervera', 'Lleida'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
