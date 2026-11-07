"""Offline semantic and inventory completeness checks; no network required."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.el_casar import ElCasarAyuntamientoAdapter as Adapter, HEADING, SOURCE
from municipio.manifest import load_manifest, load_yaml
from municipio.adapters.registry import load_portal_adapter


BASE = f'''<div class="cuerpoInterior"><h2>{HEADING}</h2>
<p>MEMORIA: <a href="/media/a/memoria.pdf">DOCUMENTO I. MEMORIA AD</a></p>
<p><a href="/media/b/normas.pdf">DOCUMENTO III. NORMAS URBANÍSTICAS AD</a></p>
<p><a href="/media/c/planos.pdf">DOCUMENTO II VOLUMEN 1 Planos</a></p>
{{extra}}
<p><a href="/media/d/modificacion.pdf">MODIFICACIÓN N.º 1 DEL PLAN DE ORDENACIÓN MUNICIPAL DE EL CASAR</a></p>
<p>(BOP de Guadalajara de 23 de julio de 2014)</p>
<p>INTERPRETACIÓN DEL POM RESPECTO DEL ACABADO DE LAS CUBIERTAS (Acuerdo del Pleno 30/03/2016)</p>
</div>'''


class ElCasarTests(unittest.TestCase):
    def test_grouping_dates_and_provenance(self):
        rows = Adapter.parse_projects(BASE.format(extra=''))
        self.assertEqual([len(r['documentos']) for r in rows], [3, 1])
        self.assertEqual(rows[1]['fecha_publicacion'], '2014-07-23')
        self.assertIsNone(rows[0]['fecha_publicacion'])
        self.assertEqual(rows[0]['acuerdos_vinculados'][0]['fecha_acuerdo'], '2016-03-30')
        for row in rows:
            self.assertIsNone(row['fecha_aprob'])
            self.assertIsNone(row['fecha_acuerdo'])
            self.assertIsNone(row['lat'])
            self.assertEqual(row['codigo_ine'], '19071')
            self.assertTrue(all(d['url_fuente'] == SOURCE for d in row['documentos']))

    def test_all_documents_and_stable_ids(self):
        extra = ''.join(f'<p><a href="/media/x/plan-{i}.pdf">Plano {i}</a></p>' for i in range(130))
        rows = Adapter.parse_projects(BASE.format(extra=extra))
        original = Adapter.parse_projects(BASE.format(extra=''))
        self.assertEqual(len(rows[0]['documentos']), 133)
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in original])

    def test_deduplicates_documents_within_instrument(self):
        rows = Adapter.parse_projects(BASE.format(extra='<p><a href="/media/a/memoria.pdf">Copia</a></p>'))
        self.assertEqual(len(rows[0]['documentos']), 3)

    def test_missing_publication_is_not_inferred(self):
        html = BASE.format(extra='').replace('(BOP de Guadalajara de 23 de julio de 2014)', '')
        self.assertIsNone(Adapter.parse_projects(html)[1]['fecha_publicacion'])

    def test_rejects_navigation_or_form(self):
        for html in ('<h1>Login</h1>', '<a href="/form.pdf">Solicitud licencia de obras</a>',
                     f'<div class="cuerpoInterior"><h2>{HEADING}</h2></div>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_rejects_pagination(self):
        for extra in ('<a href="?page=2" rel="next">2</a>', '<div class="pagination">2</div>',
                      '<p><a href="?page=2">Siguiente</a></p>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Adapter.parse_projects(BASE.format(extra=extra))

    def test_rejects_unrecognized_links_or_duplicate_instruments(self):
        for extra in ('<p><a href="https://example.org/doc.pdf">Proyecto</a></p>',
                      '<p><a href="/media/z/doc.pdf">MODIFICACIÓN NUEVA</a></p>',
                      '<p><a href="/media/d/modificacion.pdf">MODIFICACIÓN N.º 1 DEL PLAN DE ORDENACIÓN MUNICIPAL DE EL CASAR</a></p>'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                Adapter.parse_projects(BASE.format(extra=extra))

    def test_rejects_nested_documents_in_changed_markup(self):
        with self.assertRaises(ValueError):
            Adapter.parse_projects(BASE.format(extra='<section><a href="/media/x/new.pdf">Nuevo plano</a></section>'))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('el-casar')
        raw = load_yaml(manifest.path)
        self.assertEqual((raw['codigo_ine'], manifest.nombre, manifest.provincia), ('19071', 'El Casar', 'Guadalajara'))
        self.assertFalse(raw['schedule']['enabled'])
        self.assertFalse(raw['geocode']['jitter_missing'])
        self.assertFalse(manifest.licencias.enabled)
        adapter = load_portal_adapter(manifest)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'licencias.jsonl'
            result = adapter.backfill_licencias(path)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(path.read_text(), '')

    def test_update_refreshes_entire_snapshot(self):
        adapter = Adapter('el-casar')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as method:
            self.assertEqual(adapter.update_proyectos(Path('unused'), Path('unused-state')), {'rows': 2})
            method.assert_called_once_with(Path('unused'))


if __name__ == '__main__':
    unittest.main()
