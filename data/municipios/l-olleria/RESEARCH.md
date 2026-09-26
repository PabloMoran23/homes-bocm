# L'Olleria — investigación portal ayuntamiento

**Municipio:** L'Olleria (Valencia, Comunitat Valenciana)  
**INE:** 46189 · **DIR3:** L01461831  
**Slug:** `l-olleria`

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web municipal (Drupal portales) | https://www.lolleria.org | Activa |
| Urbanismo | https://www.lolleria.org/es/pagina/urbanismo | Activa |
| Transparencia | https://www.lolleria.org/es/pagina/transparencia | Activa (~900 PDFs) |
| Sede electrónica (espublico gestiona) | https://lolleria.sedelectronica.es | **Inactiva** |
| Sede alternativa (redirect) | https://l-olleria.sedelectronica.es | Indeterminada (selector sede) |
| Visor GVA ICV | https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion | Activo |

## Cómo se listan expedientes / proyectos

- **Transparencia municipal:** página Drupal con enlaces directos a PDFs en `/sites/www.lolleria.org/files/`. Incluye instrumentos de planeamiento (PGOU, planes parciales Galol y Els Teularets), modificaciones puntuales, Pla Anual Normatiu, edictos de información pública, convenios urbanísticos y dossier de propuesta urbanística.
- **Urbanismo:** sección informativa con formularios PDF de solicitud de licencia de obra (comercio y vivienda). Sin listado de expedientes.
- **Sede electrónica:** `lolleria.sedelectronica.es` responde «La Sede Electrónica se encuentra temporalmente inactiva» — sin tablón `/board` ni catálogo de trámites accesible.
- **ICV (GVA):** WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion`, filtro `cod_ine_mun=46189`.

## Cómo se publican licencias

- No hay tablón público activo en sede.
- Formularios de solicitud en web (`sol·licitud llicència obres_c.pdf`, `_v.pdf`).
- PDF `014LICURBANISTICAS.pdf` en transparencia (catálogo/licencias urbanísticas).
- Licencias concedidas no listadas de forma estructurada; el adapter expone páginas informativas + formularios.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `Planeamiento.Zonificacion` (`ms:Planeamiento.Zonificacion`)
  - Campo municipio: `cod_ine_mun=46189`
  - Instrumentos con polígono: Normas subsidiarias (exp. 19940620), Homologación (exp. 20001347, 20060242, 20060244)
- **Estrategia:** paginar WFS (`startIndex` 0–19500, count 500), agrupar por `(denominaci, expediente)`, merge MultiPolygon; enriquecer PDFs de transparencia por coincidencia de título (normas subsidiarias, homologación).
- **Limitaciones:**
  - Sede inactiva → sin geometría por expediente de licencia.
  - PDFs de transparencia sin georreferencia embebida.
  - Planes parciales recientes (Galol, Els Teularets, modificaciones PGOU) aún no en ICV; solo instrumentos históricos.
  - Sin visor cartográfico municipal propio.

## Limitaciones generales

- Sede espublico temporalmente inactiva (sin tablón ni trámites online).
- Transparencia con cientos de PDFs mezclados (personal, convenios laborales, etc.) — filtro por keywords urbanísticas.
- Drupal portalesmunicipales (mismo patrón que Alfafar, Canals).

## Referencias adapter

Patrón: `municipio/adapters/alfafar.py` (ICV WFS + transparencia) adaptado sin tablón sede.
