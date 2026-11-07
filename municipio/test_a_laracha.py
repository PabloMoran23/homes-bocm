import tempfile
import unittest
from pathlib import Path

from municipio.adapters.a_laracha import (
    ALarachaAyuntamientoAdapter, BASE, SOURCE, content, discover_instruments,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def link(url, label):
    return f'<a href="{url}">{label}</a>'


def page(title, body):
    return f'<div class="row"><h3 class="kopa-title">{title}</h3>{body}</div>'


def fixtures():
    roots = [BASE + '/gl/pagina/195/plan-xeral/', BASE + '/gl/pagina/200/equipamentos-educativos/']
    data = {SOURCE: link(roots[0], 'Plan xeral') * 2 + link(roots[1], 'Plan Especial Equipamentos Educativos')}
    sections = [
        ['PLANOS PDF - ESTRUTURA XERAL', 'PLANOS PDF - NÚCLEOS RURAIS', 'PLANOS PDF - NÚCLEOS URBANOS', 'NORMATIVA'],
        ['ANEXOS', 'INFORMACIÓN', 'ORDENACIÓN', 'PUBLICACIÓNS OFICIAIS'],
    ]
    for i, root in enumerate(roots):
        urls = [BASE + f'/gl/pagina/{i * 10 + j}/section/' for j in range(4)]
        data[root] = page(['Plan Xeral', 'Plan Especial Equipamentos Educativos'][i], ''.join(link(u, t) for u, t in zip(urls, sections[i])))
        for j, url in enumerate(urls):
            pdf = BASE + f'/panel/subido/documentos/{i}-{j}.pdf'
            title = ('ÍNDICE NORMATIVA PXOM' if i == 0 else 'ANUNCIO BOP APROBACIÓN INICIAL') if j == 3 else 'Plano'
            data[url] = page(sections[i][j], link(pdf, title) + link(pdf, title + ' segunda referencia'))
    return data, roots


class ALarachaTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ALarachaAyuntamientoAdapter('a-laracha')

    def test_grouping_provenance_and_unknown_dates(self):
        data, roots = fixtures()
        rows = self.adapter.extract(data.__getitem__)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(len(row['documentos']), 4)
            self.assertEqual(len(row['documentos'][0]['referencias']), 2)
            self.assertEqual(len(row['paginas_fuente']), 6)
            self.assertEqual(row['codigo_ine'], '15041')
            for key in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'geometry', 'lat', 'lon']:
                self.assertIsNone(row[key])
            self.assertFalse(row['publication_ready'])

    def test_no_document_limit_truncation(self):
        data, roots = fixtures()
        url = BASE + '/gl/pagina/1/section/'
        data[url] = page('Planos PDF - Núcleos Rurais', ''.join(
            link(BASE + f'/panel/subido/documentos/NR-{i}.pdf', str(i)) for i in range(350)))
        self.assertEqual(len(self.adapter.extract(data.__getitem__)[0]['documentos']), 353)

    def test_pagination_rejected(self):
        for html in [page('Plan', '<a rel="next" href="?page=2">2</a>'),
                     page('Plan', '<a href="?page=2">Seguinte</a>'),
                     page('Plan', '<div class="pagination">2</div>')]:
            with self.assertRaisesRegex(ValueError, 'Pagination'):
                content(html)

    def test_missing_sections_and_unexpected_links_rejected(self):
        data, roots = fixtures()
        data[roots[0]] = page('Plan Xeral', link(BASE + '/gl/pagina/3/section/', 'NORMATIVA'))
        with self.assertRaisesRegex(ValueError, 'sections'):
            self.adapter.extract(data.__getitem__)
        data, _ = fixtures()
        data[BASE + '/gl/pagina/1/section/'] = page('Plans', link('https://example.com/a.pdf', 'PDF'))
        with self.assertRaisesRegex(ValueError, 'URL'):
            self.adapter.extract(data.__getitem__)
        with self.assertRaises(ValueError):
            discover_instruments('<a href="form.pdf">Solicitud licencia</a>')

    def test_failure_preserves_existing_output_and_licences_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'projects.jsonl'
            out.write_text('previous snapshot')
            self.adapter._fetch = lambda url: '<html>broken</html>'
            with self.assertRaises(ValueError):
                self.adapter.backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous snapshot')
            self.assertEqual(self.adapter.backfill_licencias(out)['status'], 'disabled')
            self.assertEqual(out.read_text(), '')

    def test_manifest_loads_adapter(self):
        manifest = load_manifest('a-laracha')
        self.assertIsInstance(load_portal_adapter(manifest), ALarachaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        self.assertEqual(manifest.provincia, 'A Coruña')


if __name__ == '__main__':
    unittest.main()
