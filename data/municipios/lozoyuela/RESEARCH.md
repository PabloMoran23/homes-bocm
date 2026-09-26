# Investigación portal — Lozoyuela

Municipio: **Lozoyuela** (`lozoyuela`)  
Provincia: Lozoyuela | CCAA: Comunidad de Madrid | Boletín: BOCM (`bocm_count`: 3)

> **Nota:** Lozoyuela se fusionó en 2013 con Navas de Buitrago y Sieteiglesias formando
> **Lozoyuela-Navas-Sieteiglesias**. El portal oficial (`lozoyuela.com`) y la sede electrónica
> sirven al municipio fusionado. El slug `lozoyuela` en la cola corresponde a entradas BOCM
> históricas bajo el nombre «Lozoyuela».

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.lozoyuela.com | WordPress 6.x (Ayto. Lozoyuela-Navas-Sieteiglesias) |
| Normas subsidiarias | https://www.lozoyuela.com/108-2/normativa-municipal/normas-subsidiarias/ | PDFs NN.SS: P-1 término, P-2.1 Lozoyuela Norte, P-2.2 Lozoyuela Sur, P-2.3 Las Navas, P-2.4 Sieteiglesias |
| PONP Mazacorta | https://www.lozoyuela.com/108-2/normativa-municipal/plan-de-ordenacion-del-nucleo-de-poblacion-de-mazacorta/ | PDF PON + planos 1988 |
| Bandos | https://www.lozoyuela.com/108-2/bandos/ | Bandos PGOU, subastas parcelas |
| Trámites personales | https://www.lozoyuela.com/tramites-personales/ | Formularios licencia, DR urbanística, autoliquidación |
| Sede electrónica | https://lozoyuela.sedelectronica.es | espublico gestiona (eHome) |
| Tablón sede | https://lozoyuela.sedelectronica.es/board | Tabla HTML preview-document |
| Catálogo trámites | https://lozoyuela.sedelectronica.es/dossier | Trámites electrónicos urbanismo |

## Cómo se listan expedientes / proyectos

- **Planeamiento:** PDFs en páginas WordPress (normas subsidiarias con planos P-2.1/P-2.2 del núcleo de Lozoyuela, PONP Mazacorta, bandos).
- **Noticias PGOU:** WordPress REST API (`/wp-json/wp/v2/posts?search=pgou`) — bandos, sesiones informativas, exposición pública avance PGOU (2018–2020).
- **Tablón sede:** HTML tabla Documento / Expediente / Procedimiento / Categoría / Descripción / Fecha. En agosto 2026: 2 entradas (IAE, desbroce); sin urbanismo activo.
- **Licencias:** Sin dataset público de concesiones; formularios informativos en trámites personales y sede.

## Cómo se publican licencias

- No hay listado de licencias concedidas con coordenadas.
- Trámites informativos: solicitud licencia/autorización urbanística, declaración responsable, autoliquidación (PDF).
- Tablón puede publicar edictos de licencia; actualmente sin entradas urbanísticas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SITCM WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, `DS_MUNICIPIO='LOZOYUELA-NAVAS-SIETEIGLESIAS'`
  - PDFs planimétricos NN.SS (P-2.1 Lozoyuela Norte, P-2.2 Lozoyuela Sur) sin GeoJSON embebido
- **Estrategia:** `resolve_ambito_geometry()` por código de ámbito en título (AA/SR/SUZ/UE). Sin visor ArcGIS municipal.
- **Limitaciones:** Tablón sin expedientes urbanísticos; PDFs sin georreferencia; WFS del municipio fusionado; sin capa separada «LOZOYUELA».

## Limitaciones generales

- Sede con certificado Firmaprofesional → `insecure_ssl: true`.
- Portal compartido con municipio fusionado; registros usan nombre «Lozoyuela» para cruce BOCM.
- Sin API JSON de expedientes; scrape HTML + WP REST + PDFs.
- PGOU en redacción; documentación en noticias y bandos.

## Adapter

- Módulo: `municipio/adapters/lozoyuela.py`
- Clase: `LozoyuelaAyuntamientoAdapter` (subclase de `LozoyuelaNavasSieteiglesiasAyuntamientoAdapter`)
- Patrón: WordPress + espublico eHome + SITCM WFS partial
