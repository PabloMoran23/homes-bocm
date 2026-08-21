import { MunicipioScrapersPanel } from "@/components/admin/MunicipioScrapersPanel";

export const metadata = {
  title: "Admin · Scrapers",
  robots: { index: false, follow: false },
};

export default function AdminScrapersPage() {
  return <MunicipioScrapersPanel />;
}
