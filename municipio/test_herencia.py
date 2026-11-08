"""Offline parser/contract tests: python -m unittest municipio.test_herencia -v."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from municipio.adapters.herencia import (
    HerenciaAyuntamientoAdapter, SOURCE, candidate, group_reports,
    parse_archive, parse_report,
)
from municipio.manifest import load_manifest


def report(title, date='2026-04-27', text='Se ejecutan las obras de ampliación de las aceras.'):
    return (f'<meta property="article:published_time" content="{date}T12:00:00+00:00">'
            f'<h2 class="entry-title">{title}</h2><div class="edgtf-post-text-inner">{text}'
            '<a href="/obra.pdf">Proyecto</a></div>')


def archive():
    return ('<div data-base="edgtf_post_layout_small" data-category_id="15" '
            'data-max_pages="2" data-paged="1"><div class="edgtf-post-item">'
            '<h5><a href="/obra">Se inician las obras</a></h5></div></div>')


class HerenciaTests(unittest.TestCase):
    def test_manifest(self):
        m = load_manifest('herencia')
        self.assertEqual(m.provincia, 'Ciudad Real')
        self.assertFalse(m.licencias.enabled)
        self.assertEqual(m.portal.adapter, 'municipio.adapters.herencia:HerenciaAyuntamientoAdapter')

    def test_archive_and_empty_fail(self):
        cards, params, pages = parse_archive(archive())
        self.assertEqual(cards, {'https://herencia.es/obra': 'Se inician las obras'})
        self.assertEqual(pages, 2)
        with self.assertRaises(ValueError):
            parse_archive('<html>Unavailable</html>')

    def test_excludes_procurement_and_unrelated_news(self):
        for title in ['Abierta la licitación para la construcción de viviendas',
                      'Solicitud de licencia de obras', 'Bases de bolsa de empleo',
                      'Se autoriza la instalación de placas solares',
                      'El Ayuntamiento adjudica la instalación de placas solares']:
            self.assertFalse(candidate(title), title)

    def test_publication_date_and_document_provenance(self):
        row = parse_report(report('Se inician las obras en el Paraje de la Pedriza'), 'https://herencia.es/pedriza')
        self.assertEqual(row['fecha_publicacion'], '2026-04-27')
        self.assertEqual(row['documentos'][1]['url'], 'https://herencia.es/obra.pdf')
        self.assertEqual(row['documentos'][1]['pagina_origen'], row['url'])
        self.assertNotIn('fecha_acuerdo', row)
        self.assertNotIn('lat', row)
        self.assertIsNone(parse_report(report('Se inician las obras', '2025-04-27'), 'https://herencia.es/old'))

    def test_groups_start_and_completion_without_losing_reports(self):
        rows = [parse_report(report('La calle Concepción se integra en la zona de semipeatonalización del centro urbano'), 'https://herencia.es/inicio'),
                parse_report(report('Se reabre al tráfico la calle Concepción', '2026-08-13'), 'https://herencia.es/fin'),
                parse_report(report('Se inician las obras en el Paraje de la Pedriza'), 'https://herencia.es/pedriza')]
        grouped = group_reports(rows)
        self.assertEqual(len(grouped), 2)
        concepcion = next(r for r in grouped if len(r['reportes']) == 2)
        self.assertEqual(concepcion['fecha_publicacion'], '2026-04-27')
        self.assertEqual(len(concepcion['documentos']), 3)
        self.assertFalse(concepcion['publication_ready'])

    def test_pagination_failure_preserves_output(self):
        class Response:
            url = SOURCE
            text = archive()
            def raise_for_status(self): pass
            def json(self): return {'showNextPage': True, 'html': self.text}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'records.jsonl'
            out.write_text('previous\n')
            with patch('municipio.adapters.herencia.requests.Session') as session:
                session.return_value.get.return_value = Response()
                session.return_value.post.return_value = Response()
                with self.assertRaisesRegex(ValueError, 'Repeated archive page'):
                    HerenciaAyuntamientoAdapter('herencia').backfill_proyectos(out)
            self.assertEqual(out.read_text(), 'previous\n')

    def test_procurement_body_excluded_and_copa_grouped(self):
        self.assertIsNone(parse_report(report('Se renueva la carretera', text='Se autoriza inversión para licitar las obras.'), 'https://herencia.es/carretera'))
        copa = parse_report(report('La emblemática Copa recupera su estado original tras los trabajos de restauración'), 'https://herencia.es/copa')
        pedriza = parse_report(report('Se inician las obras en el Paraje de la Pedriza'), 'https://herencia.es/pedriza')
        self.assertEqual(len(group_reports([copa, pedriza])), 1)

    def test_no_fake_licences(self):
        result = HerenciaAyuntamientoAdapter('herencia').backfill_licencias(Path('/unused'))
        self.assertTrue(result['disabled'])
        self.assertEqual(result['count'], 0)


if __name__ == '__main__':
    unittest.main()
