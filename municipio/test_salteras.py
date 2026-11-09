import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.salteras import SalterasAyuntamientoAdapter, parse_inventory
from municipio.manifest import load_manifest, load_yaml


def inventory(links, extra=''):
    return ('<h1>7.3. NORMATIVA URBANÍSTICA</h1>'
            '<table class="TransparencyListPanel">' + links + '</table>' + extra)


def link(name, ident, title=''):
    return f'<tr><td><a href="/preview-document/{ident}" title="{title}">{name}</a></td></tr>'


ADAPTATION = (link('Planos_Adaptacion_LOUA_Salteras-1-20', 'plans1') +
              link('Planos_Adaptacion_LOUA_Salteras-21-51', 'plans2') +
              link('documento_adaptacion_loua_salteras', 'text'))
MODIFICATION = link('ANUNCIO BOP 243 19_10_20 MODIF NNSS', 'mod',
                    'MODIFICACIÓN DE LAS NORMAS SUBSIDIARIAS DEL MUNICIPIO DE SALTERAS Artículo 4.9')


class SalterasTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        rows = parse_inventory(inventory(ADAPTATION + MODIFICATION + ADAPTATION))
        self.assertEqual([len(r['documentos']) for r in rows], [3, 1])
        self.assertIn('Artículo 4.9', rows[1]['titulo'])
        for row in rows:
            self.assertEqual(row['codigo_ine'], '41085')
            for field in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
                self.assertNotIn(field, row)
        self.assertEqual(rows, parse_inventory(inventory(ADAPTATION + MODIFICATION)))

    def test_failures(self):
        for html in ('<html>unavailable</html>', inventory(''),
                     inventory(link('Solicitud licencia obras', 'form')),
                     inventory(link('Planos_Adaptacion_LOUA_Salteras-1-20', 'plan')),
                     inventory(ADAPTATION, '<a rel="next" href="?page=2">2</a>'),
                     inventory(ADAPTATION, '<a title="Siguiente" href="?x=wicket">&gt;</a>'),
                     inventory(ADAPTATION.replace('/preview-document/', 'https://example.org/preview-document/'))):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_inventory(html)

    def test_live_path_with_mock_http_and_atomic_failure(self):
        adapter = SalterasAyuntamientoAdapter('salteras')
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[inventory(ADAPTATION),
                              '<iframe src="/preview/pdf/a.pdf"></iframe>',
                              '<iframe src="/preview/pdf/b.pdf"></iframe>', '<html>error</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(out)
            self.assertFalse(out.exists())

    def test_manifest(self):
        manifest = load_manifest('salteras')
        self.assertEqual(manifest.provincia, 'Sevilla')
        raw = load_yaml(manifest.path)
        self.assertEqual(raw['codigo_ine'], '41085')
        for section, flag in [('schedule', 'enabled'), ('geocode', 'jitter_missing'), ('licencias', 'enabled')]:
            self.assertIs(raw[section][flag], False)


if __name__ == '__main__':
    unittest.main()
