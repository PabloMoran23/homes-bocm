import unittest
from unittest.mock import Mock

from municipio.adapters.sant_sadurni_d_anoia import (
    LATER, SERVER_PREFIX, TREE, check_provenance, document_url,
    group_instruments, walk_inventory,
)


def leaf(key):
    return {"id": key, "text": key.rsplit("/", 1)[-1], "children": False}


def root(children):
    return [{"id": "/", "text": "POUM Sant Sadurní d'Anoia (aprovació definitiva)", "children": children}]


class PlanningTests(unittest.TestCase):
    def test_full_lazy_traversal(self):
        api = Mock(side_effect=[root([{"id": "folder", "text": "folder", "children": True}]),
                                [{"id": "nested", "text": "nested", "children": True}], [leaf("nested/plan.pdf")]])
        self.assertEqual(walk_inventory(api), [leaf("nested/plan.pdf")])
        self.assertEqual(api.call_count, 3)
        self.assertEqual(api.call_args.args, ("get_node", "nested"))

    def test_cycle_and_unrecognized_pagination_fail(self):
        for children in ([{"id": "/", "text": "loop", "children": True}],
                         [{"id": "x", "text": "x", "children": "next-page"}]):
            with self.subTest(children=children), self.assertRaises(ValueError):
                walk_inventory(Mock(return_value=root(children)))

    def test_wrong_municipality_and_empty_inventory_fail(self):
        for payload in ([], [{"text": "Other municipality"}], root([])):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                walk_inventory(Mock(return_value=payload))

    def test_group_documents_and_exclude_non_instruments(self):
        nodes = [leaf("1 Memòria POUM/part1.pdf"), leaf("2 Normes POUM/part2.pdf"),
                 leaf(LATER + "/1 Planejament general/03 2016 Mod POUM Caves Vilarnau.pdf"),
                 leaf(LATER + "/1 Planejament general/03 2016 Mod POUM Caves Vilarnau annex.pdf"),
                 leaf(LATER + "/2 Planejament derivat/07 2025 PE Ateneu.pdf"),
                 leaf(LATER + "/1 Planejament general/02 2015 Sentència TSJC.pdf"),
                 leaf(LATER + "/3 Convenis urbanístics/2 Altres/conveni.pdf")]
        groups, excluded = group_instruments(nodes)
        self.assertEqual(len(groups), 3)
        self.assertEqual(len(groups["poum"]["nodes"]), 2)
        modification = groups["1 Planejament general/03/2016"]
        self.assertEqual(len(modification["nodes"]), 2)
        self.assertEqual(modification["anio_etiqueta_documental"], "2016")
        self.assertNotIn("fecha_aprob", modification)
        self.assertEqual(len(excluded), 2)

    def test_unknown_planning_entry_fails(self):
        with self.assertRaises(ValueError):
            group_instruments([leaf("1 Memòria POUM/a.pdf"),
                               leaf(LATER + "/2 Planejament derivat/new unknown.pdf")])

    def test_document_pointer_provenance_and_encoding(self):
        url = document_url({"type": "pdf", "content": SERVER_PREFIX + "data/Pla d'Anoia/Memòria.pdf"})
        self.assertEqual(url, TREE + "data/Pla%20d%27Anoia/Mem%C3%B2ria.pdf")
        for payload in ({"type": "txt", "content": "https://example.org/form"},
                        {"type": "pdf", "content": "/other/plan.pdf"},
                        {"type": "pdf", "content": SERVER_PREFIX + "data/../secret.pdf"}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                document_url(payload)

    def test_official_link_and_viewer_disclaimer_required(self):
        municipal = '<a href="https://mapa.psig.es/ssa/">Planejament</a>'
        viewer = '<p>POUM sense valor normatiu</p><iframe src="normativas/"></iframe>'
        check_provenance(municipal, viewer)
        check_provenance(municipal.replace("https:", "http:"), viewer)
        for m, v in (("login", viewer), (municipal, "navigation only")):
            with self.assertRaises(ValueError):
                check_provenance(m, v)


if __name__ == "__main__":
    unittest.main()
