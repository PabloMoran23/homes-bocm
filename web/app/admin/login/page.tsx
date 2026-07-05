import { AdminLoginForm } from "@/components/admin/AdminLoginForm";

export const metadata = {
  title: "Acceso interno",
  robots: { index: false, follow: false },
};

export default async function AdminLoginPage({
  searchParams,
}: {
  searchParams: Promise<{ from?: string }>;
}) {
  const { from } = await searchParams;
  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center bg-slate-100/60 px-4 py-12">
      <AdminLoginForm from={from} />
    </div>
  );
}
