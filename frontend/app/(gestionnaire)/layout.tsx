import { GardeEspaceGestionnaire } from "@/components/GardeEspaceGestionnaire";
import { GardeMfa } from "@/components/GardeMfa";
import { Navigation } from "@/components/Navigation";

/** Habillage gestionnaire (PC/web) — doc 19 §7 : « même socle, deux
 * habillages ». Groupe de routes Next.js (`(gestionnaire)`, sans effet sur
 * l'URL) plutôt que codé en dur dans le layout racine, pour que `/chauffeur`
 * ait son propre habillage (`app/chauffeur/layout.tsx`) sans hériter de la
 * barre de navigation gestionnaire.
 *
 * Application shell (DESIGN.md) : la barre de navigation en haut, puis le
 * contenu, 40px de marge de page et 1600px au plus. Le défilement est celui de
 * la page.
 */
export default function GestionnaireLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas-app">
      <GardeEspaceGestionnaire />
      <GardeMfa />
      <Navigation />
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-10 py-10">{children}</main>
    </div>
  );
}
