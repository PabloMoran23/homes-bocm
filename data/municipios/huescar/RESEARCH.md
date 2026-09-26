# Huéscar — investigación portal ayuntamiento

**Municipio:** Huéscar (`huescar`)  
**Provincia:** Granada (Andalucía)  
**INE:** 18123  
**BOJA:** 1 expediente en cola BOCM

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web ayuntamiento | https://www.aytohuescar.es | CMS propio (PHP, no WordPress) |
| Área de Urbanismo | https://www.aytohuescar.es/?s=contenido&opc=011&t=Area-de-Urbanismo | HTML + PDFs estáticos |
| Sede electrónica | https://aytohuescar.sedelectronica.es | espublico gestiona |
| Tablón de anuncios | https://aytohuescar.sedelectronica.es/board/ | HTML tabla Wicket |
| Obras y Urbanismo | https://aytohuescar.sedelectronica.es/citizen-service/f28b394b-5d71-46f4-a071-8347659a6d5a | Página informativa + enlaces trámites |
| Portal transparencia (sede) | https://aytohuescar.sedelectronica.es/transparency | Sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (~80 docs, AJAX Wicket) |
| ATUM Diputación Granada | https://atum.dipgra.es/atum/formulario_actuaciones/buscador.php?ent=098 | Buscador formularios normalizados |
| Turismo (no ayto) | https://www.huescar.es | WordPress turismo — **no usar** para urbanismo |

**Nota:** `huescar.sedelectronica.es` redirige a selector genérico; la sede correcta es `aytohuescar.sedelectronica.es`.

## Expedientes / proyectos

### Tablón de anuncios (sede)
- Listado HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
- Enlaces a `/preview-document/{uuid}`.
- ~10 avisos vigentes (sep 2026); la mayoría no urbanísticos (licitaciones feria, empleo, edictos).
- Contenido urbanístico detectado: «ORDENANZA REGULADORA DE LAS LICENCIAS DE VADOS» (sep 2026).

### Área de Urbanismo (web ayuntamiento)
- 14 PDFs de modelos normalizados (Modelos I.1–I.4, II.1–II.4, III, IV, VI).
- Autoliquidación ICIO y normativa/ordenanzas (`normativa.pdf`).
- Enlace a ATUM Diputación Granada para localizar el modelo correcto.
- Sin listado de expedientes ni información pública de planeamiento en curso.

### Portal transparencia (sede)
- Carpeta «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con ~80 documentos.
- Navegación vía AJAX Wicket (no scrapeable de forma fiable sin sesión); no implementado en adapter v1.

### Consulta expedientes
- https://aytohuescar.sedelectronica.es/expedientes — requiere autenticación.

## Licencias

- **Tablón:** publica edictos/ordenanzas; no hay concesiones de licencia de obra individuales en el tablón actual.
- **Trámites:** sede citizen-service «Obras y Urbanismo» con secciones Declaraciones Responsables, Licencias Urbanísticas, Comunicación Previa (enlaces informativos, no listado histórico).
- **Modelos:** PDFs descargables en Área de Urbanismo + buscador ATUM (Dip. Granada, código entidad 098).
- **Sin dataset** de licencias concedidas ni API pública.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - ATUM Diputación Granada: buscador de formularios, no visor GIS.
  - SITUA (Junta de Andalucía): sin entrada localizada para Huéscar en búsqueda pública.
  - incidenciasurbanas.com (`huescar-publicform.incidenciasurbanas.com`): formulario incidencias, sin capas GIS.
  - Web ayuntamiento: sin visor urbanístico ni datos abiertos georreferenciados.
  - Portal transparencia sede: documentos PDF sin enlace a geometría.
- **Estrategia:** no aplicable; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** solo PDFs y tablón sin coordenadas; consulta expedientes tras login; transparencia con navegación AJAX.

## Limitaciones generales

- SSL en sede: certificado con hostname alternativo; adapter usa `insecure_ssl: true`.
- Tablón con pocos avisos urbanísticos; mayoría administrativos.
- Transparencia sede (~80 docs urbanismo) no scrapeada por AJAX Wicket.
- Licencias: páginas informativas + modelos PDF, sin histórico de concesiones públicas.
