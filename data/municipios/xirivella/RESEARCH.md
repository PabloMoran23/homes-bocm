# Xirivella — investigación portal ayuntamiento

## Fuentes principales

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.xirivella.es | Drupal 11 (Digital Value / portalesmunicipales). Sección Urbanisme (`/va/taxonomy/term/351`). Algunas rutas `/es/seccion/urbanismo` devuelven error Drupal intermitente. |
| Sede electrónica | https://sede.xirivella.es | Plataforma **Sedipualb@** (ASP.NET). Tablón, catálogo trámites, carpetaciudadana. |
| Tablón de anuncios | https://sede.xirivella.es/tablondeanuncios/ | Listado HTML + filtro «Urbanismo y Medio Ambiente» (id 796). RSS: `tablon_rss.aspx`. |
| Catálogo urbanismo | https://sede.xirivella.es/catalogoservicios.aspx?ambito=&area=1614 | Trámites licencias (obra, parcelación, DR, comunicaciones previas, etc.). |
| Transparencia | https://transparencia.xirivella.es | WordPress Governalia. Enlace al tablón sede; taxonomía «Ordenació del territori, urbanisme i medi ambient» (p. ej. convenis 11.06). |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz | Capa planeamiento ICV (referencia visual). |

## Cómo se listan expedientes / proyectos

- **Tablón RSS**: títulos de anuncios BOP/DOGV/edictos (modificaciones PGOU, información pública, aprobaciones OOFF, etc.). Detalle en `anuncio.aspx?id=` con PDFs en `documento.aspx?id=`.
- **No hay** registro público indexable de expedientes urbanísticos en sede (consulta telemática bajo solicitud, ver edictos actividad).
- **Web Drupal**: páginas informativas; PDFs enlazados en taxonomía urbanismo cuando la página carga.

## Licencias

- Sin listado de concesiones resueltas. Catálogo sede área 1614 expone **páginas de trámite** (`carpetaciudadana/tramite.aspx?idtramite=`).
- Edictos ocasionales en tablón (licencia ambiental, etc.) vía RSS.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS ICV `InventarioSuSuz` con **cod_ine_mun INE 46248** (no confundir con entidad Sedipualb@ 46110).
  - Visor GVA capa `spaicv0702_inventario_su_suz` (polígonos SU/SUZ/PP, no expedientes individuales).
- **Estrategia:** paginar GetFeature WFS; cruzar tokens sector (UE/SD/PP) en título tablón; centroide polígono → `lat`/`lon`.
- **Limitaciones:** tablón/PDF sin georef por expediente; WFS no enlaza id anuncio; consulta expedientes sede requiere auth/solicitud.

## Limitaciones generales

- Web `/es/seccion/*` a veces error 500 Drupal; preferir `/va/taxonomy/` o sede.
- Tablón mezcla personal/subvenciones — filtro regex urbanismo en adapter.
- Sin API JSON pública de expedientes.
