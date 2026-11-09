"""Parser regressions; synthetic fixtures do not claim live records."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.moral_de_calatrava import (
    INVENTORY, NORMAS, SECTOR8, MoralDeCalatravaAyuntamientoAdapter,
    group_projects, parse_inventory, parse_sector8_agreement,
)
from municipio.manifest import load_manifest


def page(labels=(), folders=(), extra=''):
    docs = ''.join(f'<a class="gIconLink" href="/preview-document/00000000-0000-0000-0000-{i:012d}">{label}</a>' for i, label in enumerate(labels))
    dirs = ''.join(f'<a class="gIconLink exp" href="#">{label} ( {count} )</a>' for label, count in folders)
    return '<div id="content">7.1. PLANEAMIENTO URBANÍSTICO' + docs + dirs + extra + '</div>'


AGREEMENT = '''Ayuntamiento de Moral de Calatrava Expte.: 2932/2023
sesión ordinaria celebrada el día 10 de septiembre de 2026
ningún voto en contra), ACUERDA: Primero. - Aprobar definitivamente el Plan parcial de mejora del sector 8 industrial.
Fecha Firma: 11/09/2026. En Moral de Calatrava, a 15 de septiembre de 2026.'''


class PlanningTests(unittest.TestCase):
    def fixtures(self):
        main = parse_inventory(page([
            'SECTOR RA', 'Trámite de consulta pública',
            'MP_1_2021_Moral_2021_08_01_completo', 'MODIFICACION_PUNTUAL_1_2021_DEFINITIVA',
        ], [('NORMAS SUBSIDIARIAS', 1), ('Plan parcial de mejora. SECTOR 8 INDUSTRIAL', 2)]), INVENTORY)
        normas = parse_inventory(page(['NORMATIVA']), NORMAS)
        sector = parse_inventory(page(['Certficado acuerdo plenario', 'Anuncio aprobación definitiva']), SECTOR8)
        return main, normas, sector

    def test_grouping_and_date_semantics(self):
        rows = group_projects(*self.fixtures(), AGREEMENT)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [1, 2, 2])
        self.assertEqual(rows[2]['fecha_acuerdo'], '2026-09-10')
        self.assertEqual(rows[2]['expediente'], '2932/2023')
        self.assertTrue(all(r['fecha_publicacion'] is None for r in rows))
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertTrue(all(r['lat'] is None and not r['publication_ready'] for r in rows))
        self.assertFalse(any(r['titulo'].startswith(('SECTOR RA', 'Trámite', 'Anuncio')) for r in rows))

    def test_missing_document_fails_closed(self):
        main, normas, sector = self.fixtures()
        sector[0].pop()
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            group_projects(main, normas, sector, AGREEMENT)

    def test_new_instrument_requires_review(self):
        main, normas, sector = self.fixtures()
        main[0].append({'titulo': 'Plan Especial nuevo', 'url': INVENTORY})
        with self.assertRaisesRegex(ValueError, 'changed'):
            group_projects(main, normas, sector, AGREEMENT)

    def test_pagination_not_silently_truncated(self):
        with self.assertRaisesRegex(ValueError, 'Pagination'):
            parse_inventory(page(['NORMATIVA'], extra='<button>Mostrar más</button>'), NORMAS)

    def test_rejects_foreign_provenance_and_login(self):
        with self.assertRaises(ValueError):
            parse_inventory(page(['NORMATIVA']).replace('/preview-document/', 'https://example.org/preview-document/'), NORMAS)
        with self.assertRaises(ValueError):
            parse_inventory('<div id="content">Identifícate</div>', INVENTORY)

    def test_proposal_or_signature_does_not_establish_approval(self):
        with self.assertRaises(ValueError):
            parse_sector8_agreement(AGREEMENT.replace('Aprobar definitivamente', 'Proponer'))
        with self.assertRaises(ValueError):
            parse_sector8_agreement(AGREEMENT.replace('ACUERDA:', 'PROPONE:'))
        self.assertEqual(parse_sector8_agreement(AGREEMENT)[1], '2026-09-10')

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('moral-de-calatrava')
        self.assertEqual(manifest.provincia, 'Ciudad Real')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'licencias.jsonl'
            result = MoralDeCalatravaAyuntamientoAdapter(manifest.slug).backfill_licencias(output)
            self.assertTrue(result['disabled'])
            self.assertEqual(output.read_text(), '')


if __name__ == '__main__':
    unittest.main()
