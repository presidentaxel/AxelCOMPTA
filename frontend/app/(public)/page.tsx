import type { Metadata } from "next";

import { EnteteLanding } from "@/components/landing/EnteteLanding";
import { HeroLanding } from "@/components/landing/HeroLanding";
import { PiedLanding } from "@/components/landing/PiedLanding";
import { SectionEchange } from "@/components/landing/SectionEchange";
import { Etapes, Fonctions, PourQui } from "@/components/landing/SectionsLanding";
import {
  DESCRIPTION_PAGE,
  IMAGE_PARTAGE,
  TITRE_PAGE,
  URL_PUBLIQUE,
} from "@/lib/landing-contenu";

/** La page publique (AXE-949) : la vitrine d'AxeLCompta, sur `/`. Elle reste
 * affichée même avec une session. « Se connecter » ouvre le portefeuille
 * d'un gestionnaire déjà connecté, sinon la page de connexion. Le texte
 * vient de `lib/landing-contenu.ts`. */
export const metadata: Metadata = {
  metadataBase: new URL(URL_PUBLIQUE),
  title: { absolute: TITRE_PAGE },
  description: DESCRIPTION_PAGE,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "AxeLCompta",
    locale: "fr_FR",
    url: "/",
    title: TITRE_PAGE,
    description: DESCRIPTION_PAGE,
    images: [IMAGE_PARTAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: TITRE_PAGE,
    description: DESCRIPTION_PAGE,
    images: [IMAGE_PARTAGE.url],
  },
};

export default function PagePublique() {
  return (
    <div className="flex min-h-dvh flex-col bg-canvas-app text-body">
      <EnteteLanding />
      <main className="flex-1">
        <HeroLanding />
        <PourQui />
        <Fonctions />
        <Etapes />
        <SectionEchange />
      </main>
      <PiedLanding />
    </div>
  );
}
