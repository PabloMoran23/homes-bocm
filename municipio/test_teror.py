import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.teror import (
    INSTRUMENT_PATHS, SOURCE, TerorAyuntamientoAdapter, parse_index, parse_instrument,
)
from municipio.manifest import load_manifest


def article(body):
    return '<article><div class="entry-content">' + body + '</div></article>'


PGO, PEPRI = ['https://teror.es' + path for path in INSTRUMENT_PATHS]
INDEX = article(''.join('<a href="' + url + '">planeamiento</a>' for url in (PGO, PEPRI)))
P = article('<p><strong>Plan General de Ordenación Supletorio de Teror<br>Aprobación definitiva</strong></p>'
            '<a href="/wp-content/uploads/2010/03/Normativa PGOS.pdf">Normativa</a>'
            '<a href="/wp-content/uploads/2010/03/Normativa PGOS.pdf">Duplicado</a>'
            '<a href="images/plan.pdf">Plano</a>')
E = article('<p><strong>PLAN ESPECIAL DE PROTECCIÓN Y REFORMA INTERIOR (PEPRI) DEL CENTRO HISTÓRICO DE TEROR</strong></p>'
            '<a href="/MEMORIA.pdf">Memoria</a>'
            '<a href="index.php?id=340">Catalogación de edificios protegidos</a>')


class TerorTests(unittest.TestCase):
    def test_grouping_and_provenance(self):
        row = parse_instrument(P, PGO)
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['documentos'][0]['source_page'], PGO)
        self.assertIn('Normativa%20PGOS.pdf', row['documentos'][0]['url'])
        self.assertEqual(row['documentos'][1]['url'], PGO + 'images/plan.pdf')
        self.assertEqual(row['estado_documental_fuente'], 'Aprobación definitiva')
        self.assertEqual(row['codigo_ine'], '35027')
        for key in ('fecha', 'fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion', 'lat', 'lon', 'fase'):
            self.assertNotIn(key, row)
        other = parse_instrument(E, PEPRI)
        self.assertEqual(len(other['documentos']), 1)
        self.assertEqual(len(other['enlaces_relacionados']), 1)
        self.assertNotEqual(other['id'], row['id'])
        self.assertNotIn('estado_documental_fuente', other)

    def test_fail_closed_and_pagination(self):
        for html in ('', article('<a href="/modelo.pdf">Solicitud de licencia</a>'), P.replace('.pdf', '.txt')):
            with self.assertRaises(ValueError):
                parse_instrument(html, PGO)
        for extra in ('<div class="page-links">2</div>', '<a href="?page=2">Siguiente</a>'):
            with self.assertRaises(ValueError):
                parse_index(INDEX.replace('</div>', extra + '</div>', 1))
        with self.assertRaises(ValueError):
            parse_index(article('<a href="' + PGO + '">PGO</a>'))
        self.assertEqual(parse_index(INDEX), [PGO, PEPRI])

    def test_no_truncation_and_no_partial_replacement(self):
        many = P.replace('</div>', ''.join(
            f'<a href="/plan-{i}.pdf">Plano {i}</a>' for i in range(120)) + '</div>')
        self.assertEqual(len(parse_instrument(many, PGO)['documentos']), 122)
        with self.assertRaises(ValueError):
            parse_instrument(P.replace('</div>', '<a rel="next" href="?page=2">2</a></div>'), PGO)
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / 'proyectos.jsonl'
            dest.write_text('previous snapshot')
            adapter = TerorAyuntamientoAdapter('teror')
            with patch.object(adapter, '_fetch', side_effect=[INDEX, P, '<html>Unavailable</html>']):
                with self.assertRaises(ValueError):
                    adapter.backfill_proyectos(dest)
            self.assertEqual(dest.read_text(), 'previous snapshot')

    def test_snapshot_and_disabled_licences(self):
        adapter = TerorAyuntamientoAdapter('teror')
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / 'proyectos.jsonl'
            with patch.object(adapter, '_fetch', side_effect=[INDEX, P, E]):
                result = adapter.update_proyectos(dest, Path(directory) / 'state.json')
            self.assertEqual(result['count'], 2)
            self.assertEqual(len([json.loads(line) for line in dest.read_text().splitlines()]), 2)
            adapter.backfill_licencias(dest)
            self.assertEqual(dest.read_text(), '')
        manifest = load_manifest('teror')
        self.assertEqual(manifest.provincia, 'Las Palmas')
        self.assertFalse(manifest.licencias.enabled)


if __name__ == '__main__':
    unittest.main()
