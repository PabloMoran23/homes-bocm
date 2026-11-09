import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.boqueixon import BoqueixonAyuntamientoAdapter, parse_inventory
from municipio.adapters.registry import load_portal_adapter
from municipio.manifest import load_manifest

NOTICE = '<h2>Informamos de que o PXOM está anulado por sentencia xudicial, a nova normativa en vigor son as NNSS 1996.</h2>'
DOCUMENTS = '''<article class="bqx-serv-urbanismo-gl"><section id="urbanismo-gl-documentos">
<a href="http://siotuga.xunta.gal/siotuga/inventario?inv=1&amp;idconcello=15012">NORMAS SUBSIDIARIAS DE PLANEAMENTO DO CONCELLO DE BOQUEIXÓN 1996 (ENLACE)</a>
<a href="/wp-content/uploads/2021/11/certificate.pdf">Modificación puntual Nº 4 das NNSS de 1996: "Regulación das condicións de posición con respecto ó viario". Aprobación inicial (PDF)</a>
<a href="/wp-content/uploads/2021/11/Anexo-9-Declaracion-responsable-concello_signed.pdf">ANEXO 9 - DECLARACIÓN RESPONSABLE CONCELLO (PDF)</a>
<a href="/zips/15012_MP04NNSSPP_202105_AI_01PDF.zip">Non editable (PDF)</a>
<a href="/zips/15012_MP04NNSSPP_202105_AI_02EDIT.zip">Editable (DOC)</a>
</section></article>'''


class BoqueixonTests(unittest.TestCase):
    def test_grouping_provenance_and_unknown_dates(self):
        rows = parse_inventory(DOCUMENTS + '<a href="/news">Proxecto dunha festa</a>', NOTICE)
        self.assertEqual(len(rows), 2)
        base, modification = rows
        self.assertEqual(len(base['documentos']), 1)
        self.assertEqual(len(modification['documentos']), 4)
        self.assertEqual(modification['fase'], 'aprobación inicial')
        self.assertIn('en vigor', base['fase'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '15012')
            for field in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])

    def test_wrong_municipality_rejected(self):
        with self.assertRaises(ValueError):
            parse_inventory(DOCUMENTS.replace('idconcello=15012', 'idconcello=15013'), NOTICE)

    def test_missing_content_or_notice_rejected(self):
        for html, notice in [('<p>Login</p>', NOTICE), (DOCUMENTS, '<p>PXOM</p>')]:
            with self.subTest(html=html[:20]), self.assertRaises(ValueError):
                parse_inventory(html, notice)

    def test_pagination_and_new_documents_fail_visibly(self):
        for html in [DOCUMENTS + '<a rel="next" href="?page=2">Next</a>',
                     DOCUMENTS.replace('</section>', '<a href="/new.pdf">Plan especial novo</a></section>')]:
            with self.assertRaises(ValueError):
                parse_inventory(html, NOTICE)

    def test_dedup_and_stable_identity(self):
        doubled = DOCUMENTS.replace('</section>', DOCUMENTS.split('<section id="urbanismo-gl-documentos">')[1])
        self.assertEqual(parse_inventory(doubled, NOTICE), parse_inventory(DOCUMENTS, NOTICE))
        changed = DOCUMENTS.replace('certificate.pdf', 'certificate-v2.pdf')
        self.assertEqual([r['id'] for r in parse_inventory(changed, NOTICE)],
                         [r['id'] for r in parse_inventory(DOCUMENTS, NOTICE)])

    def test_manifest_and_snapshot_update(self):
        adapter = load_portal_adapter(load_manifest('boqueixon'))
        self.assertIsInstance(adapter, BoqueixonAyuntamientoAdapter)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'projects.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[DOCUMENTS, NOTICE]):
                adapter.update_proyectos(out, Path(folder) / 'state.json')
            self.assertEqual(len([json.loads(line) for line in out.read_text().splitlines()]), 2)
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
