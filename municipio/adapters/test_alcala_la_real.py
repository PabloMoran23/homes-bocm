import json
import tempfile
import unittest
from pathlib import Path
from municipio.adapters.alcala_la_real import AlcalaLaRealAyuntamientoAdapter as Adapter


def panel(title, body, ident='proceeding'):
    return f'<div class="vc_tta-panel" id="{ident}"><h4 class="vc_tta-panel-title">{title}</h4><div class="vc_tta-panel-body">{body}</div></div>'


class AlcalaLaRealTests(unittest.TestCase):
    def test_named_proceeding_excludes_forms_and_retains_explicit_date(self):
        html = panel('Plan Parcial de Ordenación NS-2.1', '''
            Aprobación inicial sometida a información pública.
            Sesión ordinaria celebrada el día 08/04/2025.
            Ley de 01/12/2021.
            <a href="/wp-content/uploads/2026/05/plan.pdf">Plan</a>
            <a href="https://alcalalareal.sedelectronica.es/info.0">Instancia</a>
        ''') + panel('Urbanismo', '<a href="/form.pdf">Solicitud licencia de obras</a>')
        rows = Adapter.parse_projects(html, 'alcala-la-real')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['fecha_acuerdo'], '2025-04-08')
        self.assertIsNone(rows[0]['fecha'])
        self.assertNotIn('fecha_publicacion', rows[0])
        self.assertEqual(len(rows[0]['documentos']), 1)
        self.assertNotIn('lat', rows[0])
        self.assertNotIn('lon', rows[0])
        self.assertEqual(rows, Adapter.parse_projects(html, 'alcala-la-real'))

    def test_undated_proceeding_stays_undated(self):
        html = panel('Plan Especial Reforma Interior Sector UE-SA7', '''
            Someter a consulta el avance, conforme a Ley 7/2021 de 01/12/2021.
            <a href="/2025/06/plan.pdf">Avance</a>
        ''')
        row = Adapter.parse_projects(html, 'alcala-la-real')[0]
        self.assertNotIn('fecha_acuerdo', row)
        self.assertIsNone(row['fecha'])

    def test_layout_loss_does_not_succeed_as_empty_snapshot(self):
        with self.assertRaises(ValueError):
            Adapter.parse_projects('<html>Maintenance</html>', 'alcala-la-real')

    def test_no_licences_manufactured(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'licencias.jsonl'
            result = Adapter('alcala-la-real').backfill_licencias(path)
            self.assertEqual(result['rows'], 0)
            self.assertEqual(path.read_text(), '')


if __name__ == '__main__':
    unittest.main()
