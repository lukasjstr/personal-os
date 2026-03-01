import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import TokenGate from "@/components/TokenGate";

export const metadata: Metadata = {
  title: "Personal OS",
  description: "Dein persönlicher KI-COO — Dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" className="dark">
      <body className="bg-zinc-950 text-white min-h-screen">
        <TokenGate>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 md:ml-56 min-h-screen overflow-y-auto">
              <div className="max-w-5xl mx-auto px-4 md:px-6 pb-6 pt-[72px] md:pt-6">
                {children}
              </div>
            </main>
          </div>
        </TokenGate>
      </body>
    </html>
  );
}
