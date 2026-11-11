import { GardeEspaceGestionnaire } from "@/components/GardeEspaceGestionnaire";
import { GardeMfa } from "@/components/GardeMfa";
import { Navigation } from "@/components/Navigation";

/** Habillage gestionnaire (PC/web) — doc 19 §7 : « même socle, deux
 * habillages ». Groupe de routes Next.js (`(gestionnaire)`, sans effet sur
 * l'URL) plutôt que codé en dur dans le layout racine, pour que `/chauffeur`
 * ait son propre habillage (`app/chauffeur/layout.tsx`) sans hériter de la
 * barre latérale gestionnaire.
 *
 * Application shell (DESIGN.md) : la barre latérale de 256px à gauche (une
 * barre de 56px en haut sous 1024px), puis le contenu, 40px de marge de page et
 * 1600px au plus. Le défilement est celui de la page ; la barre latérale reste
 * collée à l'écran.
 */
export default function GestionnaireLayout({ children }: { children: React.ReactNode }) {
  return (
    <div data-espace="gestionnaire" className="flex min-h-screen flex-col bg-canvas-app lg:flex-row">
      <GardeEspaceGestionnaire />
      <GardeMfa />
      <Navigation />
      <main className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-[1600px] px-4 py-5 sm:px-6 lg:px-8 lg:py-6">{children}</div>
      </main>
    </div>
  );
}
