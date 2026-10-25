import type { Metadata } from "next";
import { Inter } from "next/font/google";

import "./globals.css";
import { RebondLienAuth } from "@/components/RebondLienAuth";
import { SentryNavigateur } from "@/components/SentryNavigateur";
import { cn } from "@/lib/utils";

// DESIGN.md : une seule famille, Inter, partout — jamais mélangée à une
// autre police d'affichage. `shadcn init` propose Geist par défaut (preset
// Nova) : écarté ici, --font-sans reste Inter pour que les composants
// shadcn (qui utilisent la variable --font-sans) restent conformes.
const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "AxeL",
  description: "AxeL, production comptable.",
};

// Habillage volontairement neutre ici (doc 19 §7 : « même socle, deux
// habillages ») — la Sidebar/TopBar gestionnaire vit dans
// `app/(gestionnaire)/layout.tsx`, l'habillage chauffeur dans
// `app/chauffeur/layout.tsx`. Rien de commun aux deux rôles à part la
// police et le fond.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={cn("font-sans", inter.variable)}>
      <body className="min-h-screen bg-canvas-app font-sans text-ink">
        <SentryNavigateur />
        <RebondLienAuth />
        {children}
      </body>
    </html>
  );
}
