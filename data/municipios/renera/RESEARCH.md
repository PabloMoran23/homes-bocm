# Renera — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `renera` |
| Sede | https://renera.sedelectronica.es |
| Web propia | No resuelve DNS (`www.renera.es` inexistente) |
| Ubicación administrativa | Ayuntamiento en Plaza de la Constitución 1, **19145 Renera (Guadalajara, Castilla-La Mancha)** — DIR3 `L01192332` |

La cola BOCM etiqueta `comunidad-madrid` por el boletín de origen; el portal municipal es el de Guadalajara (espublico gestiona).

## URLs semilla

| Recurso | URL | Uso |
|---------|-----|-----|
| Tablón de anuncios | https://renera.sedelectronica.es/board | Anuncios publicados (tabla Wicket + `preview-document`) |
| Transparencia | https://renera.sedelectronica.es/transparency | Documentos de gobierno abierto |
| Inicio / extracto tablón | https://renera.sedelectronica.es/info | Requiere sesión; bucle 302 sin cookie |
| Catálogo trámites | https://renera.sedelectronica.es/dossier | ~113 trámites; categoría Urbanismo y Vivienda |
| Mis expedientes | https://renera.sedelectronica.es/expedientes | Área ciudadana (sin listado público de urbanismo) |

**Sesión:** visitar `/board` antes de `/dossier` o `/info` para obtener `JSESSIONID`. Sin cookie, `/info` y `/dossier` devuelven bucle de redirecciones 302.

## Licencias

- **Tablón:** en la muestra (oct 2026) solo anuncios de hacienda/padrón; no hay edictos de licencia de obra publicados.
- **Catálogo sede:** trámites informativos de licencias y declaraciones responsables, p. ej.:
  - Declaración Responsable o Comunicación en Materia Urbanística
  - Solicitud de Licencia o Autorización Urbanística
  - Solicitud de Licencia de Ocupación
  - Solicitud de Modificación o Renuncia de una Licencia Urbanística

El adapter ingiere las páginas de trámite como filas informativas (`nota` en licencias), al estilo Pozuelo/Pelabravo.

## Proyectos / planeamiento

- Trámites de planeamiento en catálogo: Modificación del Planeamiento de Desarrollo, Planeamiento General (Modificación), Solicitud de Aprobación de Planeamiento de Desarrollo, Solicitud de Actuación Urbanística, certificados/informes urbanísticos, ruina.
- Tablón: anuncios de exposición pública (p. ej. padrones fiscales) capturados si coinciden con patrones de información pública.
- No hay visor urbanístico municipal ni PDFs de PGOU enlazados en la sede.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No hay visor ArcGIS/WFS municipal. Comunidad de Madrid SITCM (`sitcm:VPLA_V_AMBITO`) no contiene el municipio Renera (`sitcm_municipio_available('Renera')` → false). No se localizó capa pública de planeamiento de Castilla-La Mancha enlazada al código de expediente.
- **Estrategia:** El orquestador aplicará centroide municipal + jitter en `geocode`.
- **Limitaciones:** Municipio pequeño sin GIS público; tablón casi vacío de urbanismo; solo trámites y PDFs puntuales.

## Limitaciones técnicas

- Redirecciones en `/info` y `/dossier` sin sesión previa.
- `insecure_ssl: true` por compatibilidad con la cadena TLS de sedes espublico en CI.
- Paginación del tablón: una sola fila visible en el momento de la investigación.

## Patrón de adapter

Mismo esquema que `pelabravo.py` / `pinilla_del_valle.py`: espublico + tablón + catálogo con cookie jar.
