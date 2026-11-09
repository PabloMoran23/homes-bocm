import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.el_papiol import ElPapiolAyuntamientoAdapter, SOURCES, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest, load_yaml

PLAN, WORKS = list(SOURCES)
PDF = '/media/repository/Urbanisme/example/memoria.pdf'


def page(url=PLAN, sections=None, extra=''):
    sections = sections or [('Aprovar inicial de la Modificació puntual del PGM del Camí del Puigmadrona del Papiol.',
                              [('Memòria', PDF), ('Plànols', PDF.replace('memoria', 'planols'))])]
    content = ''.join('<div class="subtitle">' + title + '</div><br><div class="ddbbtext">' +
                      ''.join(f'<p><a href="{href}">{label}</a></p>' for label, href in docs) + '</div>'
                      for title, docs in sections)
    return (f'<a href="{PDF}">navigation</a><div id="readspeakerPage"><h1>{SOURCES[url]}</h1>'
            f'<div class="dinamic">{content}</div><span class="updated">Darrera actualització: 15.06.2026 | 09:02</span></div>' + extra)


class ElPapiolTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        rows = parse_inventory(page(), PLAN)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fase'], 'aprobación inicial')
        self.assertEqual(row['source_page_updated'], '2026-06-15')
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertEqual(row['documentos'][0]['source_url'], PLAN)
        self.assertEqual(row['codigo_ine'], '08158')
        self.assertFalse(row['publication_ready'])

    def test_multiple_dossiers_notice_and_deduplication(self):
        notice = 'https://tauler.seu-e.cat/detall?idEns=815800000&idEdicte=605673'
        sections = [('Pla General Metropolità PA06 DEL PAPIOL', [('aquí', notice)]),
                    ('Modificació puntual del PGM del Papiol', [('Memòria', PDF), ('duplicat', PDF)])]
        rows = parse_inventory(page(sections=sections), PLAN)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[1]['documentos']), 1)
        self.assertEqual(rows[0]['documentos'][0]['tipo_enlace'], 'edicto_externo')
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[0]['fase'], 'exposición pública')
        self.assertEqual(rows[1]['id'], parse_inventory(page(sections=list(reversed(sections))), PLAN)[0]['id'])

    def test_works_are_dossiers_not_attachments(self):
        rows = parse_inventory(page(WORKS, [("Projecte ordinari d'obres de la Sala Polivalent del Papiol",
                                            [('Memòria', PDF), ('Proposta Ple', PDF.replace('memoria', 'proposta'))])]), WORKS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['tipo'], 'proyecto_obra_publica')
        self.assertEqual(rows[0]['fase'], 'exposición pública')

    def test_fail_closed_on_pagination(self):
        for extra in ('<a rel="next" href="/next">més</a>', '<a href="?page=2">2</a>',
                      '<ul class="pagination"><li><a href="/second">2</a></li></ul>'):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(page(extra=extra), PLAN)

    def test_reject_forms_missing_docs_login_and_unknown_sections(self):
        for html in ('<h1>Login</h1>', page(sections=[('Formulari llicència', [('form', PDF)])]),
                     page(sections=[('Pla General Metropolità PA06 DEL PAPIOL', [])]),
                     page(sections=[('Pla General Metropolità PA06 DEL PAPIOL', [('bad', 'https://example.com/file.pdf')])])):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html, PLAN)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('el-papiol')
        self.assertIsInstance(load_portal_adapter(manifest), ElPapiolAyuntamientoAdapter)
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '08158')
        self.assertEqual(raw['provincia'], 'Barcelona')
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'licencias.jsonl'
            with patch('municipio.adapters.el_papiol.requests.get') as network:
                result = ElPapiolAyuntamientoAdapter().backfill_licencias(path)
            network.assert_not_called()
            self.assertEqual(path.read_text(), '')
            self.assertEqual(result['status'], 'disabled')

    def test_update_uses_full_snapshot(self):
        adapter = ElPapiolAyuntamientoAdapter()
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 5}) as full:
            self.assertEqual(adapter.update_proyectos(Path('out'), Path('state')), {'rows': 5})
            full.assert_called_once_with(Path('out'))


if __name__ == '__main__':
    unittest.main()
