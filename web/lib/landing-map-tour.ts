import type { LandingMapSpotlightItem } from "@/lib/landing-map-spotlight";
import type { MapSpotlightPlacement } from "@/lib/map-spotlight-placement";

export type LandingTourActiveChange = {
  item: LandingMapSpotlightItem | null;
  placement: MapSpotlightPlacement | null;
};
