# Rociana del Condado — investigación portal ayuntamiento

Municipio: **Rociana del Condado** (`rociana-del-condado`)  
Provincia: Huelva | CCAA: Andalucía | INE: 21089 | Boletín: BOJA

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (SAGA/Dip. Huelva) | https://www.rocianadelcondado.es |
| Urbanismo | https://www.rocianadelcondado.es/es/servicios/urbanismo/ |
| Planeamiento urbanístico | https://www.rocianadelcondado.es/es/planeamiento-urbanistico/ |
| Planeamiento municipal | https://www.rocianadelcondado.es/es/planeamiento-urbanistico/planeamiento-municipal/ |
| Ordenanzas | https://www.rocianadelcondado.es/es/ayuntamiento/ordenanzas/ |
| Transparencia PGOU | https://www.rocianadelcondado.es/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00039/ |
| Sede electrónica (espublico) | https://rocianadelcondado.sedelectronica.es |
| Tablón de anuncios | https://rocianadelcondado.sedelectronica.es/board/ |
| SITUA (Junta de Andalucía) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |
| Sitemap (PDFs indexados) | https://www.rocianadelcondado.es/sitemap.xml |

## Cómo se listan expedientes / proyectos

- **Web SAGA (OpenCms)**: plantilla Diputación de Huelva (`com.saga.sagasuite.theme.diputacion.huelva.base`). PDFs de planeamiento en galerías OpenCms bajo `/export/sites/rociana/es/.galleries/` y en transparencia bajo `TRANSPARENCIA-EN-MATERIAS-DE-URBANISMO-OBRAS-PUBLICAS-Y-MEDIOAMBIENTE/`. La página `/es/planeamiento-urbanistico/planeamiento-municipal/` existe pero está vacía de documentos enlazados.
- **Transparencia**: indicadores DPH-E publicados; galería con al menos 2 PDFs urbanísticos (modificación puntual estudio de detalle 2017, modificación puntual plan parcial industrial).
- **Sede espublico**: tablón HTML con filas `class_name`, `class_folderCode`, `class_folderName`, `class_description`, `class_dateFrom`. Actualmente 1 anuncio de calidad ambiental (planta fotovoltaica) y avisos de padrón.
- **SITUA**: visor regional de instrumentos de planeamiento (PGOU, modificaciones). No hay API scrapeable por expediente individual desde el portal municipal.
- **BOJA**: modificación puntual nº 1 del PGOU publicada septiembre 2025 (ya en pipeline regional, no re-parseado).

## Cómo se publican licencias

- No hay listado histórico público de concesiones de licencia.
- Trámites vía sede (`/dossier`, `/expedientes` con autenticación).
- Tablón sede para edictos/notificaciones (actualmente sin licencias de obra publicadas).
- Web urbanismo describe servicios de licencias de obra pero sin dataset descargable.

## Geometría / visor

- **geometry_status**: `unavailable`
- **Fuentes**: no hay visor urbanístico municipal (ArcGIS/WFS/GeoJSON). SITUA ofrece consulta de planeamiento a nivel autonómico pero sin polígonos enlazables a expedientes del tablón.
- **Estrategia**: el adapter no implementa `_fetch_geometry`; el orquestador usará centroide municipal + jitter.
- **Limitaciones**: portal sin GIS público; documentación solo en PDF; certificado SSL inválido en web municipal (requiere `insecure_ssl`).

## Limitaciones generales

- Certificado SSL de `www.rocianadelcondado.es` inválido (curl sin `-k` falla).
- Página planeamiento-municipal vacía; pocos PDFs urbanísticos indexados en sitemap.
- Tablón sede con pocos anuncios urbanísticos (mayoría padrón).
- Transparencia urbanismo indica 0 documentos en sección Wicket «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE».
