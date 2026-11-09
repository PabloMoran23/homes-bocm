import { NextResponse } from "next/server";
import { isSpainLocation } from "@/lib/address-search";

type NominatimResult = {
  lat?: string;
  lon?: string;
  display_name?: string;
  address?: {
    city?: string;
    town?: string;
    village?: string;
    municipality?: string;
    suburb?: string;
    quarter?: string;
    neighbourhood?: string;
    road?: string;
    house_number?: string;
  };
};

function readableLabel(result: NominatimResult, fallback: string) {
  const a = result.address;
  const street = [a?.road, a?.house_number].filter(Boolean).join(" ");
  const area = a?.suburb || a?.quarter || a?.neighbourhood;
  const city = a?.city || a?.town || a?.village || a?.municipality;
  return [street || fallback, area, city].filter(Boolean).join(" · ");
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const q = url.searchParams.get("q")?.trim();
  if (!q || q.length < 3 || q.length > 200) {
    return NextResponse.json({ error: "Escribe una dirección más concreta" }, { status: 400 });
  }

  const params = new URLSearchParams({
    q,
    format: "jsonv2",
    addressdetails: "1",
    limit: "1",
    countrycodes: "es",
  });

  let res: Response;
  try {
    res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, {
      headers: {
        "Accept-Language": "es",
        "User-Agent": "Homes/1.0 (https://homes-urbanismo.es)",
      },
      signal: AbortSignal.timeout(7000),
      next: { revalidate: 86400 },
    });
  } catch {
    return NextResponse.json({ error: "No se pudo localizar la dirección. Vuelve a intentarlo." }, { status: 504 });
  }

  if (!res.ok) {
    return NextResponse.json({ error: "No se pudo buscar esa dirección" }, { status: 502 });
  }

  const items = (await res.json()) as NominatimResult[];
  const first = items[0];
  const lat = Number(first?.lat);
  const lng = Number(first?.lon);
  if (!first || !Number.isFinite(lat) || !Number.isFinite(lng) || !isSpainLocation({ lat, lng })) {
    return NextResponse.json(
      { error: "No hemos encontrado esa dirección. Añade el número y el municipio." },
      { status: 404 },
    );
  }

  return NextResponse.json({
    lat,
    lng,
    label: readableLabel(first, q),
    rawLabel: first.display_name ?? q,
    municipality: first.address?.city || first.address?.town || first.address?.village || first.address?.municipality,
  });
}
