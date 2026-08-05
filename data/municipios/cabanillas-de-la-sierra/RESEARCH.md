# Cabanillas de la Sierra — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.cabanillasdelasierra.es |
| Urbanismo (trámites) | https://www.cabanillasdelasierra.es/ciudadanos/tramites-personales/urbanismo |
| PGOU / normativa | https://www.cabanillasdelasierra.es/tu-ayuntamiento/normativa-municipal/plan-general-de-urbanismo |
| Tablón municipal (Joomla icagenda) | https://www.cabanillasdelasierra.es/ciudadanos/tablon-municipal |
| Tablón RSS | https://www.cabanillasdelasierra.es/ciudadanos/tablon-municipal?format=feed&type=rss |
| Sede electrónica | https://cabanillasdelasierra.sedelectronica.es/ |
| Tablón sede (espublico) | https://cabanillasdelasierra.sedelectronica.es/board/ |
| SIT ficha municipal PGOU | https://gestiona.comunidad.madrid/desvan/almudena/FichaMunicipal.icm?codMunZona=0297 |
| Visor SITCM | https://www.madrid.org/cartografia/sitcm/html/visor.htm |

## CMS y formato de listados

- **Web:** Joomla 4 + Helix Ultimate + icagenda para tablón municipal (paginación `?start=30`).
- **Sede:** espublico gestiona (Wicket); tablón en tabla HTML con enlaces `preview-document/{uuid}`.
- **Licencias:** no hay listado de concesiones; formularios PDF en urbanismo y presentación telemática en sede.
- **Proyectos:** tablón web (fotovoltaicas Calera/Vallejón, plan especial infraestructuras, convenios) + sede (contribuciones especiales, urbanización) + PGOU PDFs + ámbitos SIT.

## Licencias

- Modelos: declaración responsable, licencia obra mayor/actividad, autoliquidación vía pública (PDF en `/images/ciudadanos/tramites/urbanismo/`).
- Anuncios puntuales en tablón (autorización demanial, exposición pública licencia actividad).
- Sin dataset histórico de coordenadas ni geometría por licencia.

## Geometría / visor

- **geometry_status:** `available` (parcial por expediente; completo para ámbitos PGOU en SIT)
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro municipio: `DS_MUNICIPIO='CABANILLAS DE LA SIERRA'`
  - Campos: `DS_NOMB_AMB` (código ámbito: AA-02, AANI-04B, SAU-9, etc.)
  - Visor: SITCM (enlace desde PGOU)
- **Estrategia:** descarga masiva de ámbitos vía WFS (`outputFormat=application/json`, `srsName=EPSG:4326`); enriquecimiento puntual por código en título (`RE_AMBIT_CODE`) o `ILIKE` sobre `DS_NOMB_AMB`.
- **Limitaciones:** licencias y expedientes de tablón sin enlace GIS directo; fotovoltaicas/planes especiales pueden no tener polígono en VPLA_V_AMBITO (solo documentación PDF/imagen). Centroide municipio + jitter para filas sin match.

## Limitaciones

- Tablón web publica muchos anuncios no urbanísticos (filtrados por regex).
- Sede board mezcla personal, hacienda y urbanismo; paginación limitada en una sola página.
- PGOU modificación puntual 2017 solo como PDF, sin geometría adicional en portal municipal.
- SSL en WFS/idem: requiere `insecure_ssl` en algunos entornos.
