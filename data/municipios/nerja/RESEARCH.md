# Nerja — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `nerja` |
| Provincia | Málaga |
| CCAA | Andalucía |
| Boletín | BOJA (`boletin_source_id: boja`) |
| Web oficial | https://www.nerja.es |
| Sede electrónica | https://sedeelectronica.nerja.es (plataforma Insuit / PMH, no espublico gestiona) |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Urbanismo | https://www.nerja.es/urbanismo/ | Áreas planeamiento, gestión, disciplina urbanística, vivienda; trámites licencias (informativo) |
| PGOM | https://www.nerja.es/urbanismo/pgom/ | Página PGOM (Plan General de Ordenación Municipal); contacto pgomnerja@nerja.es |
| Tablón virtual | https://sedeelectronica.nerja.es/portal/noEstatica.do?opc_id=268&ent_id=1&idioma=1 | Tablón electrónico JSON (`/sede/tablonElectronico.do`) |
| Catálogo trámites | https://sedeelectronica.nerja.es/sede/catalogoTramites.do?ent_id=1&idioma=1 | Padrón, trámites electrónicos, portal proveedor (sin bloque urbanismo online dedicado) |
| Transparencia | https://transparencia.nerja.es | WordPress transparencia (sin visor urbanístico) |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=29901 | Consulta regional planeamiento (INE 29901) |

## Cómo se listan expedientes / proyectos

- **Tablón Insuit:** POST JSON a `/sede/tablonElectronico.do` con `opcion=consultar`, `opc_id=268`, `subseccion` (p. ej. `TABLONVIRTUAL` → `DEP` → `dep.urb`). Respuesta: `listaExpedientes` (idExp, nombre, tipoDes, anno, codigo, fechas) y `listaDocumentos`. Detalle: `opcion=verDetalleExpediente` + `expId`.
- **Subsecciones urbanísticas relevantes:** `dep.urb` (planeamiento/reparcelación/vivienda), `DEP.AP` (aperturas), `DEP.TRAF` (ocupación vía pública / licencias OVP).
- **Web municipal:** WordPress; PGOM sin PDFs públicos en la página (solo banner/contacto).
- **No hay** listado público de expedientes urbanísticos fuera del tablón ni API de consulta sin autenticación.

## Cómo se publican licencias

- **Tablón:** anuncios de licencias de ocupación de vía pública, quioscos OVP, etc. en `DEP.TRAF`; aperturas en `DEP.AP`.
- **Web urbanismo:** descripción de tipos de licencia (obra, DR, calificación ambiental) sin registro histórico.
- **Sede:** catálogo limitado a padrón y trámites genéricos; licencias de obra se tramitan presencialmente según web.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No se localizó visor urbanístico municipal (ArcGIS/WFS/GeoJSON) ni capa con campo de expediente. SITUA/VITUA Junta publica instrumentos de planeamiento a escala municipal sin enlace a códigos del tablón (`2025/3`, etc.).
- **Estrategia:** metadatos desde tablón + índices web/SITUA; geocode con centroide municipal + jitter.
- **Limitaciones:** PGOM en tramitación sin descarga cartográfica en portal; tablón sin coordenadas; sin WFS municipal consultable por expediente.

## Limitaciones generales

- Tablón con muchas subsecciones no urbanísticas bajo `DEP` (p. ej. `DEP.EMP` con cientos de expedientes); el adapter acota a `dep.urb`, `DEP.AP`, `DEP.TRAF`.
- Respuestas sede en ISO-8859-1.
- SSL sede válido.
