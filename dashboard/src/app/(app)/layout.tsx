import { Sidebar } from "@/components/sidebar";
import { TierProvider } from "@/lib/tier-context";

// Paginas do app usam useSearchParams/localStorage — nao prerender estatico (Vercel)
export const dynamic = "force-dynamic";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <TierProvider>
      <div className="flex">
        <Sidebar />
        <main className="ml-64 flex-1 min-h-screen p-8">{children}</main>
      </div>
    </TierProvider>
  );
}
