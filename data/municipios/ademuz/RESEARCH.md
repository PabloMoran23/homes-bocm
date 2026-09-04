# Ademuz — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `ademuz` |
| INE | 46001 |
| Provincia | Valencia (exclave Rincón de Ademuz) |
| CCAA | comunitat-valenciana |
| Boletín | DOGV (`dogv`) |

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.ademuz.es | Operativa — Drupal 10 portalesmunicipales.es (digital_value) |
| PGOU en tramitación | https://www.ademuz.es/es/noticia-pagina/plan-general-ordenacion-urbana | Operativa — consulta pública PGE/POP (feb 2024) |
| Documentación PGE/POP | https://drive.google.com/drive/folders/11-LvX-ZdNqcgV4F9E_Ljv21eQIWOVhfh | Google Drive municipal |
| Descargas / licencias | https://www.ademuz.es/es/pagina/descargas-e-impresos | Operativa — PDFs solicitud licencia obra/apertura |
| Sede electrónica | https://ademuz.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://ademuz.sedelectronica.es/board | Operativa — 3 anuncios (ninguno urbanístico, sep 2026) |
| Transparencia sede | https://ademuz.sedelectronica.es/transparency | Operativa — sección 7 urbanismo (5 docs, Wicket AJAX) |
| Catálogo trámites | https://ademuz.sedelectronica.es/dossier | Lento en CI |
| Consulta expedientes | https://ademuz.sedelectronica.es/expedientes | Requiere autenticación |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Operativo (referencia) |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Planeamiento | Noticia Drupal PGOU + Google Drive + ICV WFS zonificación |
| Licencias | Formularios PDF en web (presentación presencial); sin dataset histórico |
| Transparencia | Portal transparencia sede (carpeta urbanismo, 5 documentos) |
| Tablón | HTML tabla preview-document (sin licencias urbanísticas actualmente) |

### PGOU en tramitación (2024)

- Aprobación trámite participación pública PGE y POP (pleno 21-dic-2023)
- Suspensión licencias parcelación/edificación 2 años (art. 68 TRLOTUP)
- Formulario alegaciones PDF en web + carpeta Google Drive con documentación

## Cómo se publican licencias

- **No hay listado público** de licencias concedidas con coordenadas
- Modelos descargables: licencia obra menor/mayor, licencia apertura, gestión residuos
- Tramitación presencial en el ayuntamiento (Plaza Elvira Lindo, 1)
- Tablón sede disponible para futuros edictos

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - TypeName: `Planeamiento.Zonificacion`
  - Filtro municipio: `cod_ine_mun=46001` (1 instrumento con polígonos)
  - Sin visor urbanístico municipal propio identificado
- **Estrategia:** escaneo paginado WFS GeoJSON (~40 páginas); matching textual título↔`denominaci`
- **Limitaciones:**
  - Solo 1 instrumento ICV (normas subsidiarias 1990); PGE/POP en tramitación sin geometría en ICV aún
  - Geometría ICV es zonificación PGOU, no parcela ni licencia individual
  - Tablón sin anuncios urbanísticos; transparencia con carpetas Wicket AJAX
  - Sede con certificado SSL caducado (`insecure_ssl: true`)

### Instrumentos ICV (cod_ine_mun=46001)

| Expediente | Denominación | Clasificación |
|------------|--------------|---------------|
| 19900573 | Normas subsidiarias | SU |

## Limitaciones generales

- Municipio pequeño (exclave): datos urbanísticos limitados en portales
- Sin API REST ni JSON:API Drupal pública
- Google Drive no scrapeable de forma determinista (solo enlace informativo)
- Escaneo ICV WFS completo ~2,5 min; cache en memoria por ejecución
- Provincia en `queue.yaml` incorrecta (`Ademuz`); manifest usa `Valencia`

## Adapter implementado

- `municipio.adapters.ademuz:AdemuzAyuntamientoAdapter`
- Fuentes: PGOU Drupal + ICV WFS + transparencia sede + formularios licencias + tablón
