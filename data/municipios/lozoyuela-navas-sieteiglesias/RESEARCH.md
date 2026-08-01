# Investigación portal — Lozoyuela-Navas-Sieteiglesias

Municipio: **Lozoyuela-Navas-Sieteiglesias** (`lozoyuela-navas-sieteiglesias`)  
Provincia: Madrid | CCAA: Comunidad de Madrid | Boletín: BOCM (`bocm_count`: 13)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.lozoyuela.com | WordPress 6.x (tema municipal) |
| Normas subsidiarias | https://www.lozoyuela.com/108-2/normativa-municipal/normas-subsidiarias/ | PDFs planos NN.SS (P-1 término, P-2.x núcleos) + enlaces BOCM |
| PONP Mazacorta | https://www.lozoyuela.com/108-2/normativa-municipal/plan-de-ordenacion-del-nucleo-de-poblacion-de-mazacorta/ | PDF PON + planos 1988 |
| Bandos | https://www.lozoyuela.com/108-2/bandos/ | Bandos históricos PGOU, subastas parcelas |
| Trámites personales | https://www.lozoyuela.com/tramites-personales/ | Formularios licencia, DR, autoliquidación |
| Sede electrónica | https://lozoyuela.sedelectronica.es | espublico gestiona (eHome) |
| Tablón sede | https://lozoyuela.sedelectronica.es/board | Tabla HTML con preview-document |
| Catálogo trámites | https://lozoyuela.sedelectronica.es/dossier | Trámites electrónicos (sin listado público de licencias concedidas) |

## Cómo se listan expedientes / proyectos

- **Planeamiento:** PDFs enlazados en páginas WordPress (normas subsidiarias, PONP, bandos PGOU). Sin visor de expedientes IP estructurado.
- **Noticias PGOU:** WordPress REST API (`/wp-json/wp/v2/posts?search=pgou`) — bandos, sesiones informativas, exposición pública del avance PGOU (2018–2020).
- **Tablón sede:** HTML tabla con columnas Documento / Expediente / Procedimiento / Categoría / Descripción / Fecha. En julio 2026 solo 3 entradas (ninguna urbanística); patrón `preview-document/{uuid}`.
- **Licencias:** No hay dataset público de concesiones. Solo formularios informativos en trámites personales y sede.

## Cómo se publican licencias

- **No hay listado** de licencias concedidas con coordenadas.
- Trámites informativos: solicitud licencia, declaración responsable, autoliquidación (PDF descargables).
- El tablón podría publicar edictos de licencia en el futuro; actualmente vacío de urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SITCM WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, `DS_MUNICIPIO='LOZOYUELA-NAVAS-SIETEIGLESIAS'`
  - PDFs planimétricos NN.SS (P-1, P-2.x) sin GeoJSON embebido
- **Estrategia:** `resolve_ambito_geometry()` por código de ámbito en título (AA/SR/SUZ/UE). Sin visor ArcGIS municipal ni enlace expediente→polígono.
- **Limitaciones:** Tablón sin expedientes urbanísticos; PDFs sin georreferencia; WFS solo coincide si el título contiene código SITCM.

## Limitaciones generales

- Sede con certificado Firmaprofesional → `insecure_ssl: true` en adapter.
- Tablón muy escaso (3 filas, sin urbanismo a fecha de investigación).
- Sin API JSON de expedientes; scrape determinista HTML + WP REST + PDFs.
- PGOU en redacción; documentación dispersa en noticias y bandos.

## Adapter

- Módulo: `municipio/adapters/lozoyuela_navas_sieteiglesias.py`
- Clase: `LozoyuelaNavasSieteiglesiasAyuntamientoAdapter`
- Patrón: WordPress + espublico eHome (similar Loeches/Patones)
