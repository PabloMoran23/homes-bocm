import unittest
from municipio.adapters.les_franqueses_del_valles import parse_projects
class FranquesesTests(unittest.TestCase):
    def test_article_publication_is_not_approval_date(self):
        html='<h1>Aprovada la modificació del planejament urbanístic de la música</h1><div class="date">Dimecres, 4 de febrer de 2026</div><div class="ddbbtext">La comissió ha aprovat la modificació.</div>'
        row=parse_projects(html)[0]
        self.assertEqual(row['fecha_publicacion'],'2026-02-04')
        self.assertIsNone(row['fecha_aprob'])
    def test_generic_service_not_project(self):
        self.assertEqual(parse_projects('<h1>Planificació</h1><div class="ddbbtext">Llicències</div>'),[])

    def test_listing_discovers_real_details_only(self):
        from municipio.adapters.les_franqueses_del_valles import LesFranquesesDelVallesAyuntamientoAdapter as A
        html='<a href="/actualitat/noticies/real.html">Aprovada la modificació del planejament urbanístic</a><a href="https://external.test/actualitat/noticies/fake.html">Aprovada la modificació del planejament urbanístic</a>'
        self.assertEqual(A.discover_projects(html),['https://www.lesfranqueses.cat/actualitat/noticies/real.html'])
