import unittest
from municipio.adapters.el_astillero import discover_sections, parse_documents, build_record, SETTINGS

class AstilleroTest(unittest.TestCase):
    def test_discover_linked_inventory_only(self):
        html = '<div class="field-name-body">' + ''.join('<a href="'+name+'">Section</a>' for name in ('normas-urbanismo','anexos-urbanismo','memoria-urbanismo')) + '<a href="https://example.org/form.pdf">Form</a></div>'
        self.assertEqual(len(discover_sections(html, SETTINGS['url'])), 3)
        with self.assertRaises(ValueError):
            discover_sections('<div class="field-name-body">Contacts</div>', SETTINGS['url'])

    def test_documents_scope_dedup_and_no_inferred_status(self):
        doc='<a href="/ckfinder/userfiles/files/MEMORIA.pdf">Memoria</a>'
        html='<div class="field-name-body">'+doc+doc+'<a href="https://example.org/form.pdf">Form</a><a href="/form.pdf">Licence</a></div>'
        docs=parse_documents(html, SETTINGS['url'])
        self.assertEqual(len(docs),1)
        record=build_record(docs)
        self.assertIn('Normas Subsidiarias',record['titulo'])
        self.assertFalse(record['publication_ready'])
        for name in ('fecha_aprob','fase','geometry','lat','lon'):
            self.assertNotIn(name,record)

    def test_missing_documents_fails(self):
        with self.assertRaises(ValueError):
            parse_documents('<div class="field-name-body">Contacts</div>', SETTINGS['url'])
