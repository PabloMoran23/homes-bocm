# Investigación portal — Lozo-yuela (alias BOCM)

Municipio cola: **Lozo-yuela** (`lozo-yuela`)  
Municipio INE real: **Lozoyuela-Navas-Sieteiglesias** (`lozoyuela-navas-sieteiglesias`, INE 28079)  
Provincia: Madrid | CCAA: Comunidad de Madrid | Boletín: BOCM (`bocm_count`: 1)

## Resolución del alias

«Lozo-yuela» es una variante tipográfica del nombre **Lozoyuela** en el parseo del BOCM (corte erróneo con guion). No existe municipio INE con ese nombre; el ayuntamiento oficial es **Lozoyuela-Navas-Sieteiglesias**.

Implementación principal ya existente en `data/municipios/lozoyuela-navas-sieteiglesias/` (merge batch 2026-08-01). Este slug de cola reutiliza el mismo portal y adapter.

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
| Catálogo trámites | https://lozoyuela.sedelectronica.es/dossier | Trámites electrónicos |

## Cómo se listan expedientes / proyectos

- **Planeamiento:** PDFs enlazados en páginas WordPress (normas subsidiarias, PONP, bandos PGOU).
- **Noticias PGOU:** WordPress REST API (`/wp-json/wp/v2/posts?search=pgou`).
- **Tablón sede:** HTML tabla con columnas Documento / Expediente / Procedimiento / Categoría / Descripción / Fecha. Patrón `preview-document/{uuid}`.
- **Licencias:** No hay dataset público de concesiones; solo formularios informativos.

## Cómo se publican licencias

- No hay listado de licencias concedidas con coordenadas.
- Trámites informativos en trámites personales y sede.
- El tablón puede publicar edictos de licencia; escaso contenido urbanístico.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SITCM WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, `DS_MUNICIPIO='LOZOYUELA-NAVAS-SIETEIGLESIAS'`
  - PDFs planimétricos NN.SS sin GeoJSON embebido
- **Estrategia:** `resolve_ambito_geometry()` por código de ámbito en título (AA/SR/SUZ/UE).
- **Limitaciones:** Tablón sin expedientes urbanísticos frecuentes; PDFs sin georreferencia; WFS solo coincide si el título contiene código SITCM.

## Limitaciones generales

- Sede con certificado Firmaprofesional → `insecure_ssl: true`.
- Sin API JSON de expedientes; scrape HTML + WP REST + PDFs.
- Alias BOCM: usar `municipio_aliases` para cruce con proyectos del boletín.

## Adapter

- Módulo: `municipio/adapters/lozo_yuela.py` (delega en `lozoyuela_navas_sieteiglesias`)
- Clase: `LozoYuelaAyuntamientoAdapter`
- Referencia completa: `data/municipios/lozoyuela-navas-sieteiglesias/RESEARCH.md`
