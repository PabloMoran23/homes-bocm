import unittest
from municipio.adapters.felanitx import parse_projects,SOURCE
class FelanitxTests(unittest.TestCase):
    def test_only_inventory_articles(self):
        html='<article class="node--type-file-or-document"><h2><a href="'+SOURCE+'/pol4">POL4</a></h2><a href="'+SOURCE+'/pol4">Readmore</a></article>'
        rows=parse_projects(html);self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['fecha_aprob'])
        self.assertEqual(parse_projects('<a href="'+SOURCE+'/pol4">POL4</a>'),[])
