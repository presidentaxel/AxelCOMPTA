import { LienSeConnecter } from "@/components/landing/LienSeConnecter";
import { Marque } from "@/components/Marque";

/** En-tête de la page publique : la marque, et « Se connecter » seul. Pas de
 * menu : la page tient sur un défilement, et un lien de plus ne tiendrait pas
 * à côté de la marque sur un téléphone. */
export function EnteteLanding() {
  return (
    <header className="mx-auto flex w-full max-w-[1280px] items-center justify-between gap-4 px-[clamp(20px,4vw,48px)] py-5">
      <Marque />
      <LienSeConnecter className="inline-flex min-h-11 items-center rounded-md px-3.5 text-sm font-semibold text-ink outline-none transition-colors duration-150 hover:bg-surface-soft focus-visible:shadow-focus-detache" />
    </header>
  );
}
