import unittest
from municipio.adapters.villamediana_de_iregua import (
    BASE, SOURCE, collect_inventory, parse_page,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def page(title='PLAN GENERAL MUNICIPAL', docs=(), children=(), pages=()):
    return ('<div id="phoca-dl-category-box"><h3 class="pd-ctitle">' + title + '</h3>'
            + ''.join(f'<div class="pd-filebox"><div class="pd-title">{name}</div>'
                      f'<a href="?download={key}:file">Documento</a>'
                      f'<a href="?download={key}:file">DESCARGAR</a></div>' for key, name in docs)
            + ''.join(f'<div class="pd-subcategory"><a href="{url}">Categoría</a><small>({count})</small></div>' for url, count in children)
            + '<div class="pagination">' + ''.join(f'<a href="{url}">Siguiente</a>' for url in pages) + '</div></div>')


class VillamedianaTests(unittest.TestCase):
    def test_manifest_and_registry(self):
        m = load_manifest('villamediana-de-iregua')
        self.assertEqual(m.provincia, 'La Rioja')
        self.assertFalse(m.licencias.enabled)
        self.assertEqual(load_portal_adapter(m).slug, m.slug)

    def test_pagination_grouping_and_unknown_dates(self):
        child = BASE + '/index.php/normativa/category/42-documentacion-grafica'
        second = child + '?start=20'
        data = {SOURCE: page(docs=[(150, 'ANUNCIO APROBACIÓN DEFINITIVA')], children=[(child, 2)]),
                child: page(docs=[(161, 'Plano 1')], pages=[second]),
                second: page(docs=[(162, 'Plano 2')], pages=[child])}
        rows, urls = collect_inventory(data.__getitem__)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertEqual(set(urls), set(data))
        for key in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
            self.assertIsNone(rows[0][key])

    def test_incomplete_count_rejected(self):
        child = BASE + '/index.php/normativa/category/42-documentacion-grafica'
        data = {SOURCE: page(docs=[(150, 'Anuncio')], children=[(child, 46)]), child: page(docs=[(161, 'Plano')])}
        with self.assertRaisesRegex(ValueError, 'Incomplete category'):
            collect_inventory(data.__getitem__)

    def test_derived_group_and_multiple_instruments_rejected(self):
        child = BASE + '/index.php/normativa/category/45-modificaciones-del-plan-general'
        data = {SOURCE: page(docs=[(150, 'Anuncio')], children=[(child, 2)]),
                child: page(docs=[(239, 'MODIFICACIÓN PUNTUAL Nº2 P.G.M'), (256, 'ANUNCIO DE APROBACIÓN DEFINITVA')])}
        rows, _ = collect_inventory(data.__getitem__)
        self.assertEqual(len(rows), 2)
        derived = next(row for row in rows if row['id'].endswith('239'))
        self.assertEqual(len(derived['documentos']), 2)
        data[child] = page(docs=[(239, 'MODIFICACIÓN PUNTUAL Nº2 P.G.M'), (256, 'MODIFICACIÓN PUNTUAL Nº3 P.G.M')])
        with self.assertRaisesRegex(ValueError, 'grouping needs review'):
            collect_inventory(data.__getitem__)

    def test_login_and_navigation_rejected(self):
        with self.assertRaises(ValueError):
            parse_page('<a href="?download=1">Solicitud de licencia</a>', SOURCE)

    def test_external_pagination_rejected(self):
        with self.assertRaises(ValueError):
            parse_page(page(pages=['https://example.org/index.php/normativa/category/40-plan-general-municipal?start=20']), SOURCE)

    def test_conflicting_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting document'):
            parse_page(page(docs=[(1, 'Primero'), (1, 'Diferente')]), SOURCE)


if __name__ == '__main__':
    unittest.main()
