# Camarma de Esteruelas — investigación portal ayuntamiento

**Municipio:** Camarma de Esteruelas (Madrid, Comunidad de Madrid)  
**Fecha:** 2026-07-11  
**BOCM regional (referencia):** 13 avisos

## Resumen

Camarma de Esteruelas publica urbanismo y licencias en la **sede electrónica espublico gestiona**
(`camarmadeesteruelas.sedelectronica.es`) y normativa/ordenanzas en la **web municipal Umbraco**
(`www.camarmadeesteruelas.es`). No hay visor urbanístico ni datos abiertos georreferenciados.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `http://www.camarmadeesteruelas.es` | Umbraco | Ordenanzas, legislación urbanística, contacto concejalía |
| Ayuntamiento / Urbanismo | `http://www.camarmadeesteruelas.es/ayuntamiento/` | HTML tabs | Ordenanzas fiscales y urbanísticas (PDFs en `/media/`) |
| Sede electrónica | `https://camarmadeesteruelas.sedelectronica.es` | espublico/Wicket | Trámites, tablón, transparencia |
| Tablón de anuncios | `https://camarmadeesteruelas.sedelectronica.es/board/` | HTML tabla | Edictos BOCM, actuaciones urbanísticas, licencias |
| Inicio (extracto tablón) | `https://camarmadeesteruelas.sedelectronica.es/info.0` | HTML Wicket | Últimos anuncios |
| Catálogo trámites | `https://camarmadeesteruelas.sedelectronica.es/dossier` | HTML Wicket | ~133 trámites (`/catalog/t/{uuid}`), incl. urbanismo/licencias |
| Portal transparencia | `https://camarmadeesteruelas.sedelectronica.es/transparency` | Wicket/AJAX | Sección 7 Urbanismo (~152 docs; expansión AJAX anidada) |
| Consulta expedientes | `https://camarmadeesteruelas.sedelectronica.es/expedientes` | Autenticación | Requiere Cl@ve; sin listado público |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas:

- Documento → enlace `preview-document/{uuid}` (PDF)
- Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`DD/MM/YYYY`)

Ejemplos vigentes (jul 2026):

- Aprobación inicial modificación puntual **Plan Parcial Sector SI-4** (Categoría: Actuaciones Urbanísticas)
- Anuncios BOCM de delegaciones, presupuesto, convocatorias

El tablón muestra ~10 anuncios recientes; histórico completo en portal transparencia (AJAX).

## Trámites urbanismo (catálogo sede)

Trámites scrapeables como páginas informativas:

- Solicitud de Licencia o Autorización Urbanística
- Declaración Responsable o Comunicación en Materia Urbanística
- Modificación del Planeamiento de Desarrollo
- Licencias de actividad, aprovechamiento, etc.

## Licencias

No hay dataset abierto de concesiones georreferenciadas (sin paridad Madrid `lat`/`lon` en origen).

- Anuncios de licencia en tablón cuando se publican edictos.
- Páginas de trámite del catálogo sede como referencia informativa.
- Ordenanzas de construcciones y apertura en web municipal.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No se localizó visor ArcGIS, WFS, GeoJSON ni capa SIG municipal enlazada a expedientes.
- **Estrategia:** El orquestador aplicará centroide municipal + jitter en `geocode`.
- **Limitaciones:** Solo PDFs/tablon sin georreferenciación; consulta de expedientes requiere login; certificado SSL sede (Firmaprofesional) requiere `insecure_ssl`.

## Limitaciones

- Certificado SSL sede: emisor no en CA del sistema; adapter usa `insecure_ssl: true`.
- Wicket: URLs con sufijo `.0` y tokens AJAX que expiran; transparencia urbanismo requiere expansión AJAX multinivel (no implementado).
- Tablón: ~10 filas visibles; histórico en transparencia.
- Web Umbraco: sección Urbanismo con ordenanzas históricas (BOCM 2002–2012), no planeamiento vigente detallado.

## Estrategia adapter

1. Scrape tabla tablón `/board` + extracto `/info.0`.
2. Catálogo trámites `/dossier` filtrado por keywords urbanismo/licencia.
3. PDFs ordenanzas urbanísticas en `/ayuntamiento/`.
4. IDs estables: `camarma-de-esteruelas-{lic|proy}-{sha256[:14]}`.
5. `source: ayuntamiento` en todos los registros.

## Referencia adapters

- Tablón espublico + catálogo: `pelabravo.py`, `humanes_de_madrid.py`
- SSL sede inseguro: `getafe.py`, `pelabravo.py`
- Ordenanzas web: `brunete.py`, `hoyo_de_manzanares.py`
