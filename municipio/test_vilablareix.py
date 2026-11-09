import unittest
from municipio.adapters.vilablareix import GROUPS, SOURCE, VilablareixAyuntamientoAdapter
from municipio.manifest import load_manifest


def inventory():
    blocks = []
    for _, _, names in GROUPS.values():
        for name in names:
            link = f'<a href="/sites/default/files/{name}">Veure</a>'
            blocks.append('<div class="views-row"><div class="content-tax">'
                          f'<div class="content-title-tax">{name}</div>'
                          f'<div class="content-enllacos-tax">{link}{link}</div></div></div>')
    return '<main>' + ''.join(blocks) + '</main>'


class VilablareixTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        rows = VilablareixAyuntamientoAdapter.parse_projects(inventory())
        self.assertEqual(len(rows), 4)
        self.assertEqual(sum(len(r['documentos']) for r in rows), 30)
        marroc = next(r for r in rows if r['id'].endswith('marroc-ii'))
        self.assertEqual(len(marroc['documentos']), 12)
        for row in rows:
            self.assertEqual(row['codigo_ine'], '17215')
            for field in ('fecha', 'fecha_acuerdo', 'fecha_publicacion', 'fecha_aprob', 'fase', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])
            self.assertTrue(all(d['source_url'] == SOURCE for d in row['documentos']))

    def test_repeated_inventory_rows_deduplicated(self):
        self.assertEqual(VilablareixAyuntamientoAdapter.parse_projects(inventory().replace('</main>', inventory()[6:-7] + '</main>')),
                         VilablareixAyuntamientoAdapter.parse_projects(inventory()))

    def test_rejects_missing_or_non_inventory(self):
        for html in ('<main>Login / formulari de llicència</main>', inventory().replace('2013_Mod_NNSS_c16.pdf', 'new.pdf'),
                     inventory().replace('class="content-title-tax"', 'class="changed"'),
                     inventory().replace('2013_Mod_NNSS_c16.pdf', 'UA3_Memoria.pdf')):
            with self.subTest(html=html[:80]), self.assertRaises(ValueError):
                VilablareixAyuntamientoAdapter.parse_projects(html)

    def test_rejects_pagination(self):
        for pager in ('<nav class="pager">2</nav>', '<a href="?page=1">2</a>', '<a rel="next" href="/other">Next</a>'):
            with self.assertRaises(ValueError):
                VilablareixAyuntamientoAdapter.parse_projects(inventory().replace('</main>', pager + '</main>'))

    def test_manifest_and_disabled_licences(self):
        m = load_manifest('vilablareix')
        self.assertEqual(m.provincia, 'Girona')
        self.assertFalse(m.licencias.enabled)
        adapter = VilablareixAyuntamientoAdapter(m.slug)
        self.assertEqual(adapter.backfill_licencias(None)['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
