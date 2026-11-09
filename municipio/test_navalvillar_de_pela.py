"""Offline parser contract tests; run with python -m unittest municipio.test_navalvillar_de_pela."""
import tempfile
import unittest
from pathlib import Path

from municipio.adapters.navalvillar_de_pela import (
    NavalvillarDePelaAyuntamientoAdapter, candidate, group_documents,
    parse_detail, parse_inventory, spanish_date,
)
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

URL = 'https://doe.juntaex.es/otrosFormatos/html.php?xml=2025081129&anio=2025&doe=1320o'


def detail(title, body, published='10 de julio de 2025'):
    return f'''<div class="Contenido_principal"><div class="tablabordecolor">{title}</div>
    Fecha Publicación: jueves, {published} Apartado: IV ANUNCIOS
    Organismo: AYUNTAMIENTO DE NAVALVILLAR DE PELA Rango: ANUNCIO
    <a href="/pdfs/doe/2025/1320o/25081129.pdf">PDF</a>
    <a href="/otrosFormatos/xml/2025/1320o/2025081129.xml">XML</a>
    TEXTO ORIGINAL {body}</div>'''


class ParserTests(unittest.TestCase):
    def test_inventory_counts_and_canonical_deduplication(self):
        row = '''<tr><td class="justificado"><span class="DOE4">Anuncio del Programa de Ejecución de la UE3.
        <a href="../otrosFormatos/html.php?anio=2025&amp;doe=1320o&amp;xml=2025081129">HTML</a>
        </span></td></tr>'''
        html = 'Resultado de la búsqueda: 2 disposiciones<table>' + row * 2 + '</table>'
        entries = parse_inventory(html)
        self.assertEqual(entries[0]['url'], URL)
        self.assertEqual(len({e['url'] for e in entries}), 1)
        with self.assertRaisesRegex(ValueError, 'pagination/truncation'):
            parse_inventory(html.replace('2 disposiciones', '3 disposiciones'))
        with self.assertRaisesRegex(ValueError, 'pagination'):
            parse_inventory(html + '<a href="?page=2">Siguiente</a>')
        with self.assertRaises(ValueError):
            parse_inventory('<html>Service unavailable</html>')

    def test_agreement_is_not_publication_or_announcement(self):
        html = detail('ANUNCIO de 2 de junio de 2025 sobre aprobación definitiva del Programa de ejecución de la UE3.',
                      'En el Pleno ordinario de fecha 10 de abril de 2025 se aprobó definitivamente el Programa de Navalvillar de Pela.')
        key, doc = parse_detail(html, URL)
        self.assertEqual(key, 'ue3')
        self.assertEqual(doc['fecha_acuerdo'], '2025-04-10')
        self.assertEqual(doc['fecha_publicacion'], '2025-07-10')
        self.assertEqual(doc['fecha_documento'], '2025-06-02')
        self.assertIn('pdf', doc)
        self.assertIn('xml', doc)
        initial = dict(doc, url=URL + '&initial=1', fecha_publicacion='2025-02-28',
                       fecha_acuerdo='2025-02-13', fase='aprobacion_inicial')
        row = group_documents([(key, doc), (key, initial), (key, doc)])[0]
        self.assertEqual(len(row['documentos']), 2)
        self.assertEqual(row['fase'], 'aprobacion_definitiva')
        self.assertEqual(row['fecha_acuerdo'], '2025-04-10')
        self.assertNotIn('lat', row)
        self.assertNotIn('fecha', row)
        with self.assertRaises(ValueError):
            parse_detail(html.replace('10 de abril de 2025', 'fecha no disponible'), URL)
        with self.assertRaises(ValueError):
            parse_detail(html.replace('/pdfs/doe/', '/other/'), URL)
        with self.assertRaises(ValueError):
            parse_detail(html.replace('Navalvillar de Pela', 'Otro municipio').replace('NAVALVILLAR DE PELA', 'OTRO MUNICIPIO'), URL)

    def test_modification_and_environmental_report_grouping(self):
        html = detail('ACUERDO de 21 de octubre de 2025, de aprobación definitiva de la modificación puntual 1/2019 (n.º 20) de las Normas Subsidiarias de Navalvillar de Pela.',
                      'Acuerdo de la Comisión.', '18 de diciembre de 2025')
        key, doc = parse_detail(html, URL)
        self.assertEqual(doc['fecha_acuerdo'], '2025-10-21')
        report = detail('RESOLUCIÓN de 9 de mayo de 2024, informe ambiental estratégico de la modificación puntual de las Normas Subsidiarias de Navalvillar de Pela. Expte.: IA24/0077.',
                        'Manzana Cantarranas, Luis Chamizo, Velázquez y Adolfo Suárez.', '17 de mayo de 2024')
        report_key, report_doc = parse_detail(report, URL + '&environment=1')
        self.assertEqual(key, report_key)
        self.assertNotIn('fecha_acuerdo', report_doc)
        self.assertEqual(len(group_documents([(key, doc), (report_key, report_doc)])), 1)
        self.assertIsNone(parse_detail(report.replace('IA24/0077', 'IA24/9999'), URL))

    def test_exclusions_and_manifest_contract(self):
        for title in ('Solicitud de licencia de obras', 'Licitación de obras de pavimentación',
                      'Licitación del Programa de Ejecución de la UE3',
                      'Convocatoria de una plaza de oficial de construcción', 'Fiestas municipales'):
            self.assertFalse(candidate(title))
        self.assertEqual(spanish_date('14 de noviembre de 2024'), '2024-11-14')
        with self.assertRaises(ValueError):
            group_documents([])
        manifest = load_manifest('navalvillar-de-pela')
        adapter = load_portal_adapter(manifest)
        self.assertIsInstance(adapter, NavalvillarDePelaAyuntamientoAdapter)
        self.assertFalse(manifest.licencias.enabled)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'licencias.jsonl'
            self.assertTrue(adapter.backfill_licencias(target)['disabled'])
            self.assertEqual(target.read_text(), '')


if __name__ == '__main__':
    unittest.main()
