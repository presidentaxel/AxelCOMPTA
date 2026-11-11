import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import "./globals.css";
import { RebondLienAuth } from "@/components/RebondLienAuth";
import { SentryNavigateur } from "@/components/SentryNavigateur";
import { cn } from "@/lib/utils";

// DESIGN.md : une seule famille, Inter, partout — jamais mélangée à une
// autre police d'affichage. `shadcn init` propose Geist par défaut (preset
// Nova) : écarté ici. next/font pose `--font-inter` sur <html> ; `@theme
// inline` (globals.css) en fait `--font-sans`, que les composants utilisent.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "AxeL",
  description: "AxeL, production comptable.",
};

/** `viewport-fit=cover` : sans lui, `env(safe-area-inset-*)` vaut 0 et la
 * barre du bas passe sous l'indicateur d'accueil de l'iPhone. Le zoom
 * utilisateur reste possible ; les champs à 16 px évitent le zoom
 * automatique d'iOS au focus. */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

// Habillage volontairement neutre ici (doc 19 §7 : « même socle, deux
// habillages ») — la barre de navigation gestionnaire vit dans
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
