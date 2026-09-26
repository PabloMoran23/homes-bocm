# Martos — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `martos` |
| INE | 23050 |
| Provincia | Jaén |
| CCAA | andalucia |
| Boletín | BOJA (`boja`) |

## Fuentes

### Web municipal (WordPress + WP File Download)

- Base: https://martos.es
- Urbanismo y Obras: https://martos.es/urbanismo-y-obras/
- Instrumentos PGOU (interpretaciones): https://martos.es/urbanismo-y-obras/instrumentos-de-ordenacion-urbanistica-general
- Ordenanzas urbanismo: https://martos.es/urbanismo-y-obras/ordenanzas/
- Modelos y solicitudes (licencias/obras): https://martos.es/urbanismo-y-obras/modelos-y-solicitudes/
- Plan Especial Casco Antiguo: https://martos.es/tu-ciudad/plan-especial-del-casco-antiguo/
- Descargas vía plugin WP File Download (`/download/{cat}/{slug}/{id}/{file}.pdf`)

### Sede electrónica propia (add4u / SemiColonWeb)

- Base: https://sedeelectronica.martos.es
- Tablón de anuncios: https://sedeelectronica.martos.es/eAdmin/Tablon.do?action=verAnuncios
  - HTML tabla con título, periodo y enlace a PDF (`abrirOriginal`) + ficha (`verAnuncio&id=…`)
  - Codificación ISO-8859-1; ~15 anuncios vigentes en listado completo
- `martos.sedelectronica.es` → página «Sede Electrónica Indeterminada» (no usable)

### Portal de transparencia (WordPress multisite)

- Base: https://transparencia.martos.es
- Procedimientos en exposición pública: https://transparencia.martos.es/procedimientos-en-exposicion-publica/
  - PDFs urbanismo (consulta pública mejora urbana calle Linares/Bailén, etc.)
- Consulta pública reglamentos (art. 133): enlaces WPFD adicionales

### Otros (no operativos / informativos)

- Agenda Urbana: https://agendaurbanamartos.es/ — error crítico WordPress (caído)
- SITUA difusión Junta Andalucía: https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf — planeamiento regional digitalizado (PDF), sin API GeoJSON por expediente municipal
- Mapa web: https://martos.es/mapa-web/ — mapa corporativo sin capas urbanísticas enlazadas a expedientes

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Información pública / calificación ambiental | Tablón sede propia (tabla HTML + PDF) |
| Consultas urbanísticas | Transparencia → procedimientos en exposición pública (WPFD) |
| PGOU / interpretaciones | Web corporativa → categoría WPFD «interpretaciones del plan general» |
| Ordenanzas | Web corporativa → categoría WPFD ordenanzas urbanismo |
| Licencias concedidas | No hay registro histórico público; solo edictos/tablon y formularios de trámite |

## Cómo se publican licencias

- Edictos de calificación ambiental y apertura de actividades en tablón
- Formularios DR/comunicación previa en modelos y solicitudes (no concesiones)
- Tramitación presencial / sede propia (sin dataset de licencias otorgadas)

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** SITUA difusión (PDF escaneado PGOU regional); mapa web corporativo sin WFS/ArcGIS público; tablón y transparencia solo PDF sin georreferencia
- **Estrategia:** N/A — sin visor urbanístico municipal ni WFS enlazable a código de expediente
- **Limitaciones:** anuncios con dirección textual (calle, ref. catastral) pero sin polígono descargable; SITUA no expone GeoJSON queryable por expediente

## Limitaciones generales

- Tablón: solo anuncios vigentes (~15), sin histórico archivado en URL pública
- Codificación Latin-1 en sede propia
- `agendaurbanamartos.es` caído
- espublico (`martos.sedelectronica.es`) no configurado
