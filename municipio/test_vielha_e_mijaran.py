import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.vielha_e_mijaran import (
    BASE, SOURCE, VielhaEMijaranAyuntamientoAdapter,
    build_records, parse_documents, parse_inventory,
)
from municipio.manifest import load_manifest


def block(title, *numbers):
    return '<div class="contenidoFichas"><h1>' + title + '</h1>' + ''.join(
        f'<div class="itemServicio"><a href="/fitxaUrbanisme/{n}">veir mès</a></div>' for n in numbers
    ) + '</div>'


def table(*labels):
    return '<table><tbody>' + ''.join(
        f'<tr><td>{label}</td><td><a href="/public/vielha/ftp/urbanismoarchivos/doc-{i}.pdf">PDF</a></td></tr>'
        for i, label in enumerate(labels)
    ) + '</tbody></table>'


class VielhaParserTests(unittest.TestCase):
    def test_group_four_documents_and_preserve_unknown_dates(self):
        html = block('Modificacion des Nòrmes en relacion damb es abitatges d’us toristic', 63, 64, 65, 66)
        labels = ['DOCUMENT COMPRENSIU', 'DOCUMENT UNITARI', 'Anonci aprobacion provisionau', 'Tèxte rehonut diligenciat']
        details = {BASE + '/fitxaUrbanisme/' + str(n): table(label) for n, label in zip(range(63, 67), labels)}
        rows = build_records(parse_inventory(html), details.__getitem__)
        self.assertEqual(len(rows), 1)
        self.assertEqual([d['titulo'] for d in rows[0]['documentos']], labels)
        self.assertEqual(len(rows[0]['source_urls']), 4)
        for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry']:
            self.assertIsNone(rows[0][key])
        self.assertEqual(rows[0]['codigo_ine'], '25243')
        self.assertFalse(rows[0]['publication_ready'])

    def test_split_bundled_modifications(self):
        groups = parse_inventory(block('Modificacions des NNSS nombre 71 - 72', 12))
        rows = build_records(groups, lambda _: table('Comprensiu 71', 'Comprensiu 72', 'Mod. 71', 'Mod. 72'))
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        for row, number in zip(rows, ['71', '72']):
            self.assertEqual(len(row['documentos']), 2)
            self.assertTrue(all(number in d['titulo'] for d in row['documentos']))
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            build_records(groups, lambda _: table('Mod. 71', 'Mod. 72', 'unassigned'))

    def test_reject_forms_maps_navigation_and_news(self):
        html = ''.join(block(t, i) for i, t in enumerate([
            'Mapa Acostic', 'Teishut urban assolidat deth nuclèu', 'Sollicitud de llicència', 'Notícies',
        ]))
        with self.assertRaises(ValueError):
            parse_inventory(html)
        with self.assertRaises(ValueError):
            parse_documents('<h1>Login</h1>', BASE + '/fitxaUrbanisme/63')

    def test_pagination_fails_instead_of_truncating(self):
        for paginator in ['<a rel="next" href="?page=2">2</a>', '<div class="pagination">1 2</div>']:
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                parse_inventory(block('Modificacion des NNSS', 12) + paginator)

    def test_document_provenance_and_unexpected_host(self):
        url = BASE + '/fitxaUrbanisme/12'
        docs = parse_documents(table('Mod. 71'), url)
        self.assertEqual(docs[0]['source_url'], url)
        with self.assertRaises(ValueError):
            parse_documents(table('Mod. 71').replace('/public/vielha/', 'https://example.org/public/vielha/'), url)

    def test_stable_identity_when_documents_change(self):
        groups = parse_inventory(block('Modificacion des NNSS', 12))
        a = build_records(groups, lambda _: table('Document'))
        b = build_records(groups, lambda _: table('Document', 'Annex'))
        self.assertEqual(a[0]['id'], b[0]['id'])
        self.assertEqual(len(b[0]['documentos']), 2)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('vielha-e-mijaran')
        self.assertEqual(manifest.provincia, 'Lleida')
        self.assertFalse(manifest.licencias.enabled)
        adapter = VielhaEMijaranAyuntamientoAdapter(manifest.slug)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 13}) as backfill:
            self.assertEqual(adapter.update_proyectos(Path('unused'), Path('unused-state')), {'rows': 13})
            backfill.assert_called_once()


if __name__ == '__main__':
    unittest.main()
