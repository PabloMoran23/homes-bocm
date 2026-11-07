import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.cassa_de_la_selva import CassaDeLaSelvaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest


def section(title="Projecte de reforma de la piscina", labels=None, expediente='X2025004777'):
    labels = labels or ['Projecte tècnic', 'Decret aprovació definitiva']
    return '<h2>' + title + '</h2><ul>' + ''.join(
        f'<li><a href="./04_{expediente} {i} piscina.pdf">{label}</a></li>'
        for i, label in enumerate(labels)) + '</ul>'


def page(body):
    return '<h1 id="titol">Projectes d\'obra</h1>' + body


class CassaTests(unittest.TestCase):
    def test_groups_documents_and_preserves_unknown_dates(self):
        row, = Adapter.parse_projects(page(section()))
        self.assertEqual(row['codigo_ine'], '17044')
        self.assertEqual(row['expediente'], 'X2025004777')
        self.assertEqual(len(row['documentos']), 2)
        for key in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'fase', 'lat', 'lon', 'geometry'):
            self.assertIsNone(row[key])
        self.assertIn('%20', row['documentos'][0]['url'])

    def test_bop_date_belongs_to_document_only(self):
        row, = Adapter.parse_projects(page(section(labels=[
            "BOP núm 205 de data 23 d'octubre de 2026 d'aprovació definitiva",
            'Certificat_Ple_19_juny_2025',
            'BOP núm. 56 de data 21 de març de 2023 d’aprovació definitiva'])))
        self.assertEqual([d['fecha_publicacion'] for d in row['documentos']], ['2026-10-23', None, '2023-03-21'])
        self.assertIsNone(row['fecha_aprob'])
        self.assertIsNone(row['fecha_publicacion'])

    def test_excludes_cost_structure(self):
        rows = Adapter.parse_projects(page(section() + section('Anunci aprovació definitiva d’Estructura de costos del servei', expediente='X2025000562')))
        self.assertEqual(len(rows), 1)

    def test_duplicate_expediente_merges_document_groups(self):
        rows = Adapter.parse_projects(page(section() + section('Projecte de reforma ampliat', ['Plànols'])))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['titulos_fuente']), 2)
        self.assertEqual(len(rows[0]['documentos']), 2)

    def test_rejects_pagination(self):
        for extra in ['<a rel="next" href="2.html">2</a>', '<div class="pagination">2</div>', '<a href="?start=20">20</a>', '<a href="2.html">Següent</a>']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Adapter.parse_projects(page(section() + extra))

    def test_rejects_forms_news_and_procurement(self):
        for title in ['Sol·licitud de llicència', 'Licitació de manteniment', 'Notícies']:
            with self.subTest(title=title), self.assertRaises(ValueError):
                Adapter.parse_projects(page(section(title)))

    def test_rejects_missing_or_changed_inventory(self):
        for html in ['<h1>Login</h1>', page(''), page('<h2>Projecte de reforma</h2>'), page(section(expediente='unknown')),
                     page(section().replace('repo.cassa.cat', 'bad.example').replace('./04_', 'https://bad.example/04_'))]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('cassa-de-la-selva')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'licencias.jsonl'
            self.assertEqual(Adapter(manifest.slug).backfill_licencias(output)['status'], 'disabled')
            self.assertEqual(output.read_text(), '')

    def test_snapshot_update(self):
        adapter = Adapter('cassa-de-la-selva')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 25}) as refresh:
            self.assertEqual(adapter.update_proyectos(Path('out'), Path('state')), {'rows': 25})
            refresh.assert_called_once_with(Path('out'))

    def test_atomic_jsonl_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'proyectos.jsonl'
            rows = Adapter.parse_projects(page(section()))
            Adapter._write(path, rows)
            self.assertEqual(json.loads(path.read_text())['id'], rows[0]['id'])
            self.assertFalse(path.with_suffix('.jsonl.tmp').exists())


if __name__ == '__main__':
    unittest.main()
