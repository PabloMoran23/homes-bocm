import unittest
from municipio.adapters.malgrat_de_mar import parse_projects,SOURCE
class MalgratTests(unittest.TestCase):
    def test_generic_consolidated_norms_are_not_projects(self):
        def item(title):return '<li class="article-item"><a href="'+SOURCE+'/a.html">'+title+'</a></li>'
        self.assertEqual(parse_projects(item('Text Consolidat de la Normativa')),[])
        row=parse_projects(item('Modificació puntual del POUM Bon Pastor'))[0]
        self.assertIsNone(row['fecha_aprob'])
        self.assertFalse(row['publication_ready'])
