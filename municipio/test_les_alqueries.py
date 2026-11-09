import unittest

from municipio.adapters.les_alqueries import LesAlqueriesAyuntamientoAdapter as Adapter


def section(title, *docs):
    return '<h3>' + title + '</h3>' + ''.join(
        f'<p><a href="https://drive.google.com/file/d/{key}/view?usp=sharing">{label}</a></p>'
        for key, label in docs)


def page(body):
    return '<main><div class="cuerpo-taxo">' + body + '</div></main>'


class ParserTests(unittest.TestCase):
    def test_grouping_and_exclusions(self):
        html = page(
            section('1. Convenio Camí la Ratlla', ('convenio', 'Convenio')) +
            section('2. San Ramón - Rehabilitación de edificio municipal para usos socio-culturales',
                    ('electric', 'Instalación eléctrica'), ('basico', 'Proyecto básico')) +
            section('3. PGOU 2015', ('anuncio', 'Información pública'), ('memoria', 'Memoria')) +
            section('4. Proyecto de reparcelación unidad Joan Fuster', ('parcelas', 'Fichas parcelas')) +
            section('5. Licencia Ambiental', ('licencia', 'Industria')) +
            section('6. PAI Golf Subirana', ('pai', 'Plan parcial')))
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 4)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1, 1])
        self.assertEqual(rows[1]['titulo'], 'PGOU 2015')
        self.assertEqual(rows[2]['documentos'][0]['titulo'], 'Fichas parcelas')
        for row in rows:
            self.assertEqual(row['codigo_ine'], '12901')
            for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'fase', 'lat', 'lon'):
                self.assertIsNone(row[key])
            self.assertFalse(row['publication_ready'])
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in Adapter.parse_projects(html)])

    def test_fail_closed(self):
        for html in ('<main>PGOU 2015</main>', page(section('Modelo licencia')), page(section('PGOU 2015'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_pagination_rejected(self):
        html = page(section('PGOU 2015', ('pgou', 'Memoria')))
        for navigation in ('<nav class="pager"></nav>', '<a rel="next" href="?page=1">2</a>',
                           '<a href="?page=1">Siguiente</a>'):
            with self.subTest(navigation=navigation), self.assertRaisesRegex(ValueError, 'pagination'):
                Adapter.parse_projects(html + navigation)

    def test_duplicate_links_and_heading(self):
        body = section('PGOU 2015', ('memoria', 'Memoria'), ('memoria', 'Memoria repetida'))
        self.assertEqual(len(Adapter.parse_projects(page(body))[0]['documentos']), 1)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            Adapter.parse_projects(page(body + body))


if __name__ == '__main__':
    unittest.main()
