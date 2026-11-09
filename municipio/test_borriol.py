import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.borriol import (
    BorriolAyuntamientoAdapter, SEDE_HOST, SOURCE, discover_dossier, parse_dossier,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

DOSSIER = f'https://{SEDE_HOST}/transparency/823ff776-5ccb-4876-a22d-156749324698/'
DOC = f'https://{SEDE_HOST}/preview-document/c4d591cf-0dee-44fd-b73e-4ceaf1ffa3b8'
PAGE = f'<main>Proyecto de urbanización l’Abeller <a href="{DOSSIER}">Documentos</a></main>'


def dossier(extra=''):
    return f'''<div id="content"><span>7.7. PROYECTOS/1.- PROGRAMA DE ACTUACIÓN INTEGRADA L'ABELLER</span>
    <div><table class="TransparencyListPanel"><tr><td class="class_name">
    <a class="gIconLink" href="{DOC}" title="DOCUMENTO Nº 1 MEMORIA">Doc 1.1 Memoria</a>
    </td></tr>{extra}</table></div></div>'''


class BorriolTests(unittest.TestCase):
    def test_discovery_and_grouping_provenance(self):
        self.assertEqual(discover_dossier(PAGE), DOSSIER)
        other = DOC.replace('c4d591cf', 'a4d591cf')
        row = parse_dossier(dossier(f'<tr><td class="class_name"><a class="gIconLink" href="{other}">CERTIFICAT 2019-0072</a></td></tr>'), DOSSIER)[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['codigo_ine'], '12031')
        self.assertEqual(row['documentos'][0]['source_url'], DOSSIER)
        self.assertEqual(row['titulo'], "PROGRAMA DE ACTUACIÓN INTEGRADA L'ABELLER")
        for field in ('fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'fase'):
            self.assertNotIn(field, row)
        self.assertFalse(row['publication_ready'])

    def test_fail_closed(self):
        for html in ('<html>Login</html>', dossier().replace('Memoria', 'Solicitud'),
                     dossier().replace("L'ABELLER", 'OTRO'),
                     dossier('<tr><td class="class_name">Unparsed</td></tr>'),
                     dossier().replace('/preview-document/', '/transparency/'),
                     dossier().replace(SEDE_HOST, 'example.org')):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_dossier(html, DOSSIER)

    def test_pagination_and_expanded_inventory_are_not_truncated(self):
        for control in ('<a rel="next" href="?page=2">2</a>', '<div class="pagination">1 2</div>',
                        '<a onclick="wicketAjaxGet()">Siguiente</a>'):
            with self.assertRaises(ValueError):
                parse_dossier(dossier().replace('</table>', '</table>' + control), DOSSIER)
        with self.assertRaises(ValueError):
            discover_dossier(PAGE.replace('</main>', f'<a href="{DOSSIER.replace("823ff776", "123ff776")}">Otro</a></main>'))

    def test_manifest_and_live_path_without_network(self):
        manifest = load_manifest('borriol')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, BorriolAyuntamientoAdapter)
        class Response:
            def __init__(self, url, text):
                self.url, self.text = url, text
                self.content = text.encode()
                self.headers = {'Content-Type': 'text/html'}
            def raise_for_status(self):
                pass
        with tempfile.TemporaryDirectory() as directory, patch('municipio.adapters.borriol.requests.Session.get',
                side_effect=[Response(SOURCE, PAGE), Response(DOSSIER, dossier())]):
            output = Path(directory) / 'projects.jsonl'
            result = adapter.backfill_proyectos(output)
            self.assertEqual(result['count'], 1)
            self.assertEqual(len(output.read_text().splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
