/** Tour animado del mapa de inicio: top proyectos con metadata precalculada. */

import type { MapProjectSpotlightItem } from "@/lib/map-project-spotlight";

export type LandingMapSpotlightItem = MapProjectSpotlightItem & {
  /** [south, west, north, east] */
  bounds: [number, number, number, number];
  center: [number, number];
  score?: number;
};

export type LandingMapSpotlightFile = {
  generatedAt: string;
  source?: string;
  criteria?: string;
  items: LandingMapSpotlightItem[];
};

export type LandingMapSpotlightGeoProps = {
  expedienteGrupo: string;
  sigma_layer_kind?: string | null;
  tourIndex?: number;
};

export type { MapProjectSpotlightItem, SigmaMapCardSlice } from "@/lib/map-project-spotlight";
