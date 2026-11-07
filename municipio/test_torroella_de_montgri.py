"""Offline parser/contract tests; reduced fixtures model the reviewed HTML layout."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.torroella_de_montgri import TorroellaDeMontgriAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest

FIXTURE = '''<h1>Planejament, gestió i execució urbanística en tràmit</h1>
<div class="page_content"><div class="resum">
<p><strong>2.1. PLA GENERAL:</strong></p>
<p><a href="/pujades/files/excluded.pdf">Document fora de cobertura</a></p>
<p><strong>2.2. PLANEJAMENT DERIVAT:</strong></p>
<p><a href="/pujades/files/notice.pdf">Aprovació inicial Projecte urbanització polígon 1 zona Creu de la Rutlla. Exp. 135007K</a><br>
<a href="https://drive.torroella-estartit.cat:9090/s/example">Projecte urbanització</a></p>
<p>Aprovació definitiva del Projecte d’Estudi de Detall de la parcel·la 4 del conjunt Sol Ric de la urbanització Torre Vella<br>
<a href="/pujades/files/Certificat_16072026.pdf">Certificat acord</a><br>
<a href="/pujades/files/estudi.pdf">Text refós</a></p>
<p><strong>2.3. INSTRUMENTS DE GESTIÓ I EXECUCIÓ URBANÍSTICA:</strong></p>
<p><a href="/pujades/files/medes.pdf">Aprovació inicial de la modificació puntual del Pla General Municipal d'Ordenació de Torroella de Montgrí, en l'àmbit del càmping de les Medes. Exp. 115629X</a></p>
<p><strong>ALTRES DOCUMENTS DE CONSULTA:</strong></p>
<p><a href="/pujades/files/plater.pdf">PLATER</a></p>
</div></div>'''


class ParserTests(unittest.TestCase):
    def test_grouping_scope_and_semantics(self):
        rows = Adapter.parse_projects(FIXTURE)
        self.assertEqual(len(rows), 3)
        self.assertEqual([len(r['documentos']) for r in rows], [2, 2, 1])
        self.assertEqual(rows[0]['expediente'], '135007K')
        self.assertEqual(rows[1]['fase'], 'aprobación definitiva')
        self.assertEqual(rows[0]['tipo'], 'proyecto_urbanizacion')
        self.assertEqual(rows[1]['tipo'], 'estudio_detalle')
        self.assertEqual(rows[0]['documentos'][0]['url'], 'https://www.torroella-estartit.cat/pujades/files/notice.pdf')
        for row in rows:
            for field in ('fecha', 'fecha_acuerdo', 'fecha_aprob', 'fecha_publicacion', 'lat', 'lon', 'geometry'):
                self.assertIsNone(row[field])
            self.assertFalse(row['publication_ready'])
            self.assertEqual(row['codigo_ine'], '17199')

    def test_reordering_documents_does_not_change_identity(self):
        changed = FIXTURE.replace('Certificat_16072026.pdf', 'Certificat_20270101.pdf')
        self.assertEqual([r['id'] for r in Adapter.parse_projects(FIXTURE)],
                         [r['id'] for r in Adapter.parse_projects(changed)])

    def test_fail_closed_on_layout_loss_pagination_or_ambiguity(self):
        cases = [
            '<html>Login</html>',
            FIXTURE.replace('2.3. INSTRUMENTS', '3.3. INSTRUMENTS'),
            FIXTURE + '<a rel="next" href="?page=2">2</a>',
            FIXTURE + '<div class="pagination"><a href="?page=2">2</a></div>',
            FIXTURE.replace('https://drive.torroella-estartit.cat:9090', 'https://other.example'),
            FIXTURE.replace('Aprovació inicial Projecte urbanització', 'Formulari de llicència'),
            FIXTURE.replace('<p><strong>2.3.', '<p>Instrument sense documents</p><p><strong>2.3.'),
            FIXTURE.replace('Exp. 115629X', 'Exp. 135007K'),
        ]
        for html in cases:
            with self.subTest(html=html[-80:]), self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_load_and_disabled_licences_without_http(self):
        manifest = load_manifest('torroella-de-montgri')
        self.assertEqual(manifest.provincia, 'Girona')
        self.assertFalse(manifest.licencias.enabled)
        adapter = Adapter(manifest.slug, manifest.portal.config)
        with tempfile.TemporaryDirectory() as directory, patch('requests.get', side_effect=AssertionError('HTTP forbidden')):
            target = Path(directory) / 'licencias.jsonl'
            result = adapter.backfill_licencias(target)
            self.assertEqual(result['status'], 'disabled')
            self.assertEqual(target.read_text(), '')


if __name__ == '__main__':
    unittest.main()
