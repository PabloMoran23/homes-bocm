import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from municipio.adapters.moncofa import MoncofaAyuntamientoAdapter as Adapter
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter


def section(title='INFORMACIÓN PÚBLICA DEL PROYECTO FINALIZACIÓN URBANIZACIÓN BELCAIRE SUR'):
    docs = ''.join(f'<a href="/wp-content/uploads/2025/12/{name}.pdf">{name}</a>'
                   for name in ['MEMORIA', 'PLANOS', 'PRESUPUESTO'])
    return (f'<div class="elementor-toggle-item"><div class="elementor-tab-title">{title}</div>'
            f'<div class="elementor-tab-content">{docs}'
            '<a href="/wp-content/uploads/otra-cosa.pdf"><img alt="icono_pdf"></a>'
            f'{docs}</div></div>')


class MoncofaTests(unittest.TestCase):
    def test_grouping_and_semantics(self):
        html = section() + section('INFORMACIÓN PÚBLICA DE LA INICIATIVA DE PROGAMA DE ACTUACIÓN INTEGRADA MANZANAS 1 Y 2 SUELO URBANO INDUSTRIAL POLÍGONO CASABLANCA')
        rows = Adapter.parse_projects(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(set(r['id'] for r in rows)), 2)
        for row in rows:
            self.assertEqual(len(row['documentos']), 3)
            self.assertEqual(row['fase'], 'información pública')
            for field in ['fecha', 'fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob', 'lat', 'lon', 'geometry']:
                self.assertIsNone(row[field])

    def test_forms_are_not_projects(self):
        with self.assertRaises(ValueError):
            Adapter.parse_projects('<a href="licencia.pdf">SOLICITUD LICENCIA DE OBRAS</a>')

    def test_pagination_is_not_silently_truncated(self):
        for more in ['<a rel="next" href="/page/2">2</a>', '<button>Cargar más</button>']:
            with self.assertRaisesRegex(ValueError, 'pagination'):
                Adapter.parse_projects(section() + more)

    def test_changed_inventory_fails_closed(self):
        for html in [section().replace('MEMORIA', 'FORMULARIO'), section() + section(),
                     section('INFORMACIÓN PÚBLICA DE OTRO PROYECTO'),
                     section().replace('/wp-content/uploads/2025/12/MEMORIA.pdf', 'https://example.org/MEMORIA.pdf')]:
            with self.assertRaises(ValueError):
                Adapter.parse_projects(html)

    def test_manifest_and_refresh(self):
        manifest = load_manifest('moncofa')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, Adapter)
        self.assertFalse(manifest.licencias.enabled)
        adapter = Adapter('moncofa')
        with patch.object(adapter, 'backfill_proyectos', return_value={'rows': 2}) as refresh:
            self.assertEqual(adapter.update_proyectos(Path('unused'), Path('unused-state')), {'rows': 2})
            refresh.assert_called_once_with(Path('unused'))
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'licencias.jsonl'
            self.assertEqual(adapter.backfill_licencias(output)['status'], 'disabled')
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
