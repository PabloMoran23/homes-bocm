# POC: BOCM → CSV de proyectos de vivienda

Pipeline local para extraer proyectos de construcción de vivienda del BOCM (Madrid).

## Flujo

```
0_quick_test.py       → descarga ~6 PDFs de muestra directamente
1_collect_bocm.py     → descarga todos los PDFs de urbanismo de los últimos 20 boletines
2_extract_text.py     → convierte PDFs a .txt (pdftotext)
3_llm_parse.py        → llama a GPT-4o-mini, estructura datos → proyectos.csv
```

## Uso rápido (POC)

```bash
# 1. Descargar PDFs de muestra
python3 0_quick_test.py

# 2. Extraer texto
python3 2_extract_text.py

# 3. Parsear con LLM (necesitas OPENAI_API_KEY)
OPENAI_API_KEY=sk-... python3 3_llm_parse.py
```

## Salidas

```
pdfs/                   PDFs descargados del BOCM
output/
  *.txt                 Texto extraído de cada PDF
  index.json            Índice con metadatos de cada documento
  *_parsed.json         Resultado LLM individual por documento
  proyectos.csv         CSV final con todos los proyectos estructurados
```

## Campos del CSV

| Campo | Descripción |
|---|---|
| municipio | Nombre del municipio |
| tipo_instrumento | Plan Parcial / Plan Especial / Mod. PGOU / Estudio de Detalle / ... |
| nombre_sector | Nombre o ID del sector |
| estado_tramitacion | Aprobación Inicial / Provisional / Definitiva |
| fecha_acuerdo | Fecha del acuerdo |
| organo_aprobador | Quién aprueba el plan |
| num_viviendas_max | Número máximo de viviendas |
| sup_total_m2 | Superficie total del ámbito |
| sup_edificable_m2 | Edificabilidad máxima |
| tipo_vivienda | libre / protegida / mixta / unifamiliar / colectiva |
| promotor_o_propietario | Promotor si aparece |
| municipio_provincia | Municipio y provincia |
| resumen | Resumen del proyecto |
| pdf_file | Nombre del PDF fuente |

## Web (portal)

En la carpeta [`web/`](./web/) hay una aplicación Next.js para consultar el histórico parseado en mapa, listado y estadísticas.

```bash
cd web && npm install && npm run build-data && npm run dev
```

Los datos se generan desde `output/history_parsed_incremental.csv` y `output/municipios_coords_cache.json`. Ver `web/README.md`.

**Producción:** despliegue en Vercel, refresco de datos y checklist en [`docs/production-web.md`](docs/production-web.md).
