import tempfile
import unittest
from pathlib import Path

from municipio.adapters.collbato import CollbatoAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest


def page(title, content):
    return f'<div id="col-cont"><h2>{title}</h2><div id="col-cont-contingut">{content}</div></div>'


class CollbatoTests(unittest.TestCase):
    def test_groups_instrument_and_retains_notice_labels(self):
        html = page('Projectes', '''<ul>
          <li><a href="https://tauler.seu.cat/pagDetall.do?idEdicte=1&amp;idens=806920002">PROJECTE TANCAMENT DE LA PISTA POLIESPORTIVA</a></li>
          <li><a href="https://tauler.seu.cat/pagDetall.do?idEdicte=2&amp;idens=806920002">Esmena de l'edicte PROJECTE TANCAMENT DE LA PISTA POLIESPORTIVA</a></li>
          <li><a href="/files/doc1/edicte.pdf">Aprovacio definitiva del Projecte de tancament de la Pista Poliesportiva</a></li>
          <li>Aprovació inicial del projecte de rehabilitació del dipòsit d'aigua potable de Can Dalmases</li></ul>''')
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]['referencias']), 2)
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertEqual(len(rows[0]['provenance']['rotulos_originales']), 3)
        self.assertEqual(rows[1]['documentos'], [])
        for row in rows:
            for key in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry', 'fase'):
                self.assertIsNone(row[key])
        # Reordering source notices does not alter the grouped work identity.
        reordered = page('Projectes', '<li>Projecte de tancament de la Pista Poliesportiva</li>')
        self.assertEqual(rows[0]['id'], Adapter.parse_projects(reordered)[0]['id'])

    def test_pgou_is_one_record_with_all_documents(self):
        rows = Adapter.parse_pgou(page('Pla General Ordenació Urbana', '''
          <a href="/files/doc1/text.pdf">Text Refós complert (publicació DOGC)</a>
          <a href="/files/doc2/normativa.pdf">Normativa</a>
          <a href="/files/doc3/planol.pdf">Plànol</a>'''))
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['documentos']), 3)
        self.assertIsNone(rows[0]['fecha_publicacion'])

    def test_rejects_navigation_forms_procurement_and_empty(self):
        for html in ('<a href="/files/doc1/projecte.pdf">Projecte</a>', page('Projectes', ''),
                     page('Projectes', '<li>Sol·licitud de llicència per projecte</li>'),
                     page('Projectes', '<li>Licitació redacció projecte</li>')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_pagination_or_unknown_document_fails(self):
        for content in ('<a rel="next" href="?page=2">2</a>',
                        '<li><a href="https://other.example/projecte.pdf">Projecte de reforma</a></li>'):
            with self.assertRaises(ValueError):
                Adapter.parse_projects(page('Projectes', content))

    def test_manifest_and_disabled_licences(self):
        manifest = load_manifest('collbato')
        self.assertEqual(manifest.nombre, 'Collbató')
        self.assertEqual(manifest.provincia, 'Barcelona')
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'licencias.jsonl'
            result = Adapter('collbato').backfill_licencias(target)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(target.read_text(), '')


if __name__ == '__main__':
    unittest.main()
