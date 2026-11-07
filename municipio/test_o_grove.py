import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.o_grove import OGroveAyuntamientoAdapter, parse_plans, parse_pxom
from municipio.manifest import load_manifest


PLANS = '''<main id="content"><article><div class="texto-longo">
<a href="/pxom/pxom.php">PXOM</a><a href="licencia.pdf">Formulario licencia</a>
<p><strong>Plan especial porto do Grove e da Illa da Toxa:</strong></p>
<ol><li><a href="memoria.pdf">Memoria</a></li><li><a href="plano.pdf">Plano</a></li>
<li><a href="memoria.pdf">Duplicado</a></li></ol></div></article></main>'''


def section(number, title, note, documents):
    return (f'<h2 id="s{number}"><button aria-controls="b{number}">{title}</button></h2>'
            f'<p>{note}</p><div id="b{number}">{documents}</div>')


PXOM = '<main id="contenido">' + ''.join([
    section(1, 'Normas Subsidiarias de Planeamento', 'Aprobadas 25-04-1996',
            '<a href="normas.pdf">Plano</a>'),
    section(2, 'PXOM 2014', 'Aprobado inicialmente no Pleno do 18 de setembro do 2014.',
            '<a href="old.pdf">Plano</a>'),
    section(3, 'PXOM 2020', 'Actualización 06/07/2021',
            '<area href="urban.pdf" title="NU1"><a href="folder/">Carpeta</a>'),
    section(4, 'PXOM 2026', 'Documento para aprobación definitiva (maio 2026). '
            'Aprobado provisionalmente polo Pleno do 15/06/2026.',
            '<li>SNR1 - Meloxo: <a href="new.pdf">Plano</a></li>'
            '<area href="urban26.pdf" title="NU1">'),
]) + '</main>'


class OGroveTests(unittest.TestCase):
    def test_documents_grouped_and_unrelated_material_excluded(self):
        port, url = parse_plans(PLANS)
        self.assertEqual(len(port['documentos']), 2)
        self.assertTrue(url.endswith('/pxom/pxom.php'))
        norms, pxom = parse_pxom(PXOM)
        self.assertEqual(norms['fecha_acuerdo'], '1996-04-25')
        self.assertEqual(len(pxom['versiones']), 3)
        self.assertEqual(len(pxom['documentos']), 5)
        self.assertEqual(pxom['documentos'][-1]['titulo'], 'NU1')
        self.assertIn('SNR1 - Meloxo', pxom['documentos'][-2]['titulo'])
        self.assertEqual(pxom['fecha_acuerdo'], '2026-06-15')
        self.assertEqual(pxom['fase'], 'aprobacion_provisional')
        self.assertNotIn('fecha_publicacion', pxom)
        self.assertNotIn('fecha_aprob', pxom)
        self.assertNotIn('lat', pxom)

    def test_fail_on_pagination_missing_or_unknown_sections(self):
        for html in ('<main/>', PXOM + '<a rel="next" href="?page=2">2</a>',
                     PXOM.replace('PXOM 2026', 'Otro instrumento'),
                     PXOM.replace('aria-controls="b4"', 'aria-controls="absent"')):
            with self.subTest(html=html[-100:]), self.assertRaises(ValueError):
                parse_pxom(html)
        with self.assertRaises(ValueError):
            parse_plans(PLANS.replace('<ol>', '<div>').replace('</ol>', '</div>'))

    def test_adapter_and_manifest(self):
        manifest = load_manifest('o-grove')
        self.assertEqual(manifest.provincia, 'Pontevedra')
        adapter = OGroveAyuntamientoAdapter('o-grove')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[PLANS, PXOM]):
                result = adapter.update_proyectos(out, Path(tmp) / 'state.json')
            self.assertEqual(result['count'], 3)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len({r['id'] for r in rows}), 3)
            self.assertTrue(all(r['codigo_ine'] == '36022' for r in rows))
            adapter.backfill_licencias(out)
            self.assertEqual(out.read_text(), '')


if __name__ == '__main__':
    unittest.main()
