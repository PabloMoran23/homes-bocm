import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.sant_antoni_de_vilamajor import (
    INDEX, INVENTORIES, SantAntoniDeVilamajorAyuntamientoAdapter as Adapter,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

APPROVED = 'projectes-municipals-aprovats'
PENDING = 'projectes-en-tramit-dinformacio-publica'
UNAPPROVED = 'projectes-municipals-no-aprovats'


def page(category, blocks, documents='', extra=''):
    return (f'<main><h1>{INVENTORIES[category]}</h1><div class="dinamic">{blocks}</div>'
            f'<section id="page-documents">{documents}</section>{extra}'
            '<span class="updated">Darrera actualització: 01.11.2026</span></main>')


def block(title, description):
    return f'<div class="ddbbtext"><h3>{title}</h3><p>{description}</p></div>'


def doc(title, filename):
    return f'<a href="/media/repository/{filename}.pdf">{title} (7.9MB)</a>'


class ParserTests(unittest.TestCase):
    def test_explicit_and_automatic_approval_and_document_grouping(self):
        a, b = 'Projecte de reforma de la plaça', 'Projecte de reparació del pont'
        html = page(APPROVED,
                    block(a, 'Per acord del Ple del dia 28 de maig de 2026, s’ha aprovat definitivament el projecte.')
                    + block(b, 'Per Decret en data 7 d’agost de 2026, va aprovar inicialment el projecte. '
                            'El termini finalitzava el 25 de setembre de 2026. El projecte es considera aprovat definitivament.'),
                    doc(b, 'bridge') + doc(a, 'square') + doc(a, 'square-annex'))
        rows = Adapter.parse_inventory(html, APPROVED)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 1])
        self.assertEqual(rows[0]['fecha_aprob_definitiva'], '2026-05-28')
        self.assertEqual(rows[1]['fecha_aprob_inicial'], '2026-08-07')
        self.assertIsNone(rows[1]['fecha_aprob_definitiva'])
        self.assertIsNone(rows[1]['fecha_aprob'])
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertIsNone(rows[0]['lat'])

    def test_initial_phase_despite_approved_category(self):
        title = 'Projecte executiu planta solar'
        html = page(APPROVED, block(title, 'Per acord del Ple del dia 12 de febrer de 2026, es va aprovar inicialment el projecte.'), doc(title, 'solar'))
        row = Adapter.parse_inventory(html, APPROVED)[0]
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertEqual(row['fecha_acuerdo'], '2026-02-12')
        self.assertEqual(row['fecha_aprob'], '2026-02-12')

    def test_publication_separate_from_agreement_and_deadline(self):
        title = 'Projecte per a la realització carril bici'
        html = page(APPROVED, block(title, 'Per Decret en data 13 d’octubre de 2025, es va aprovar inicialment el projecte. '
                    'Publicació al Butlletí (BOPB) del 20 d’octubre de 2025 fins a l’1 de desembre de 2025, '
                    'el projecte va quedar aprovat definitivament sense necessitat de cap acord exprés.'), doc(title, 'bici'))
        row = Adapter.parse_inventory(html, APPROVED)[0]
        self.assertEqual(row['fecha_publicacion'], '2025-10-20')
        self.assertEqual(row['fecha_acuerdo'], '2025-10-13')
        self.assertIsNone(row['fecha_aprob_definitiva'])

    def test_unapproved_document_is_project_with_unknown_dates(self):
        title = 'Projecte de pacificació del camí'
        row = Adapter.parse_inventory(page(UNAPPROVED, '<div class="ddbbtext">' + doc(title, 'cami') + '</div>'), UNAPPROVED)[0]
        self.assertEqual(row['fase'], 'no aprobado')
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_missing_content_unmatched_documents_and_pagination_fail(self):
        title = 'Projecte de reparació de voreres'
        html = page(PENDING, block(title, 'Per Decret en data 22 d’octubre de 2026, s’ha aprovat inicialment el projecte.'), doc(title, 'voreres'))
        for bad in [html.replace('<h1>', '<h2>').replace('</h1>', '</h2>'),
                    html.replace('voreres.pdf', 'voreres.html'),
                    html.replace('id="page-documents"', 'id="missing"'),
                    html.replace('</main>', '<a rel="next" href="?page=2">2</a></main>'),
                    page(PENDING, block(title, 'Formulari de llicència'), doc(title, 'form')),
                    html.replace('</section>', doc('Projecte diferent sense relació', 'other') + '</section>')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Adapter.parse_inventory(bad, PENDING)

    def test_manifest_loading_disabled_licences_and_no_partial_output(self):
        manifest = load_manifest('sant-antoni-de-vilamajor')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'proyectos.jsonl'
            target.write_text('previous snapshot')
            index = '<main><h1>Projectes municipals</h1>' + ''.join(f'<a href="{INDEX}/{x}">{x}</a>' for x in INVENTORIES) + '</main>'
            with patch.object(adapter, '_fetch', side_effect=[index, '<main>Login</main>']), self.assertRaises(ValueError):
                adapter.backfill_proyectos(target)
            self.assertEqual(target.read_text(), 'previous snapshot')
            result = adapter.backfill_licencias(Path(directory) / 'licencias.jsonl')
            self.assertEqual(result['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
