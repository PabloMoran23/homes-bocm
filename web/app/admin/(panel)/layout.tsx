import { AdminSubNav } from "@/components/admin/AdminSubNav";

export const metadata = {
  robots: { index: false, follow: false },
};

export default function AdminPanelLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto min-h-[calc(100vh-3.5rem)] max-w-7xl px-4 py-8">
      <AdminSubNav />
      {children}
    </div>
  );
}
