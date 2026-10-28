# Yecla — investigación portal ayuntamiento

**Municipio:** Yecla (Murcia, Región de Murcia)  
**Slug:** `yecla`  
**Boletín:** sin asociación en cola (`bocm_count: 0`)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa (WordPress) | https://yecla.es | Operativa |
| Obras y Urbanismo | https://yecla.es/obras-y-urbanismo/ | Enlaces a PGOU y trámites |
| PGOU (documentación) | https://yecla.es/obras-y-urbanismo/plan-general-de-ordenacion-urbana/ | PDFs PGOU, calificación, término municipal |
| Sede electrónica (Sedipualba) | https://yecla.sedipualba.es/ | Diputación Albacete — plataforma compartida |
| Tablón de anuncios | https://yecla.sedipualba.es/tablondeanuncios/default.aspx?pub=false | Tabla HTML (~30 visibles) + RSS |
| Tablón RSS | https://yecla.sedipualba.es/tablondeanuncios/tablon_rss.aspx | ISO-8859-1, subset reciente |
| Catálogo Urbanismo y Actividades | https://yecla.sedipualba.es/catalogoservicios.aspx?area=589&ambito=1 | **Vacío** (sin `tramite.aspx` listados) |
| Oficina Virtual — formularios | https://ov.yecla.es/WebOFICINAVIRTUAL/Vista/Paginas/WebFormTramite.aspx?T=35 | PDFs licencias, DR, cédulas (no listado de concesiones) |

## Listado de expedientes / proyectos

- **Tablón Sedipualba:** filas con enlace `anuncio.aspx?id=`; título en atributo `alt` del icono. Muchos avisos **PMH / BOII** (expedientes de licencia urbanística) y publicaciones **BORM** (tramitación autonómica de actividades).
- **PGOU:** documentos estáticos en WordPress (`wp-content/uploads/2023/02/*.pdf`).
- No hay portal tipo SIU/Liferay con listas IP/PL como Cartagena o Lorca.

## Licencias de obra

- No hay dataset público de licencias concedidas (solo edictos en tablón y formularios descargables en OV).
- El adapter expone páginas informativas (tablón, OV, catálogo vacío) y filas del tablón cuyo título coincide con patrones de licencia/PMH/BOII.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS CARM `SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo` filtrado `Municipio='Yecla'` (82 polígonos, EPSG:4326 vía `srsName`). Ficha enlazada en propiedad `Enlace_ficha` → SITMURCIA (`opweb.carm.es`).
- **Estrategia:** índice por nombre de ámbito (`Ambito`) y códigos SUPI/SNU en título; join heurístico con titulares del tablón/PDF (sin enlace expediente→polígono en sede).
- **Limitaciones:** tablón/PDF sin georreferencia directa; catálogo sede sin trámites urbanísticos electrónicos; visor municipal no expuesto en web del ayto (solo planeamiento regional).

## Limitaciones técnicas

- RSS con encoding `iso-8859-1`; HTML tablón con títulos en `alt`, no texto de enlace.
- Paginación del tablón vía filtros ASP.NET (`ddlMes`); primera página suficiente para muestra reciente.
- Sin `SUPABASE_DB_URL` en agente cloud → sync Supabase queda skipped en CI del agente.
