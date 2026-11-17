import Link from "next/link";

import { Marque } from "@/components/Marque";
import { TEXTES_JURIDIQUES } from "@/lib/juridique";
import { PIED } from "@/lib/landing-contenu";

/** Pied de la page publique : les cinq textes juridiques, lisibles sans
 * compte. La liste vient de `TEXTES_JURIDIQUES`, la même que les pages
 * `/legal/…` : un texte ajouté là apparaît ici sans autre geste. */
export function PiedLanding() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex w-full max-w-[1280px] flex-wrap justify-between gap-6 px-[clamp(20px,4vw,48px)] py-8">
        <div className="flex flex-col gap-2">
          <Marque />
          <p className="text-xs text-muted">{PIED.signature}</p>
        </div>
        <nav aria-label="Informations légales">
          <ul className="m-0 flex list-none flex-wrap gap-x-5 p-0 text-[13px]">
            {Object.entries(TEXTES_JURIDIQUES).map(([cle, titre]) => (
              <li key={cle}>
                <Link
                  href={`/legal/${cle}`}
                  className="inline-flex min-h-11 items-center rounded-sm text-subtle outline-none hover:text-ink focus-visible:shadow-focus-detache"
                >
                  {titre}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
