import { ETAPES, FONCTIONS, POUR_QUI } from "@/lib/landing-contenu";

const SECTION =
  "mx-auto flex w-full max-w-[1280px] px-[clamp(20px,4vw,48px)] py-[clamp(40px,6vw,72px)]";
const SURTITRE = "text-xs font-semibold uppercase tracking-[0.06em] text-muted";
const TITRE = "text-balance text-[28px] font-semibold leading-[1.21] tracking-[-0.02em] text-ink";

/** Les trois blocs de texte de la page : pour qui, ce que fait AxeL, l'ordre
 * des opérations. Chacun garde sa forme : deux colonnes séparées d'un filet,
 * des lignes réglées, trois étapes sous un trait d'encre. Pas d'ombre, pas de
 * carte de plus : les filets de DESIGN.md. */
export function PourQui() {
  return (
    <section aria-labelledby="pour-qui" className={`${SECTION} flex-wrap gap-x-16 gap-y-8`}>
      <div className="flex min-w-0 flex-[1_1_280px] flex-col gap-3">
        <p className={SURTITRE}>{POUR_QUI.surtitre}</p>
        <h2 id="pour-qui" className={TITRE}>
          {POUR_QUI.titre}
        </h2>
      </div>
      <div className="flex min-w-0 flex-[2_1_520px] flex-wrap">
        {POUR_QUI.profils.map((profil, rang) => (
          <div
            key={profil.titre}
            className={`flex min-w-0 flex-[1_1_280px] flex-col gap-2 pb-6 ${
              rang === 0 ? "min-[680px]:pr-8" : "border-border min-[680px]:border-l min-[680px]:pl-8"
            }`}
          >
            <h3 className="text-lg font-semibold text-ink">{profil.titre}</h3>
            <p className="text-[15px] text-body">{profil.texte}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

export function Fonctions() {
  return (
    <section aria-labelledby="fonctions" className={`${SECTION} flex-wrap gap-x-16 gap-y-8`}>
      <div className="flex min-w-0 flex-[1_1_280px] flex-col gap-3">
        <p className={SURTITRE}>{FONCTIONS.surtitre}</p>
        <h2 id="fonctions" className={TITRE}>
          {FONCTIONS.titre}
        </h2>
      </div>
      <ul className="m-0 flex min-w-0 flex-[2_1_520px] list-none flex-col border-b border-border-strong p-0">
        {FONCTIONS.liste.map((fonction, rang) => (
          <li
            key={fonction.nom}
            className={`flex flex-wrap gap-x-6 gap-y-1.5 py-[18px] ${
              rang === 0 ? "border-t border-border-strong" : "border-t border-border"
            }`}
          >
            <h3 className="min-w-0 flex-[0_0_200px] text-[15px] font-semibold text-ink">{fonction.nom}</h3>
            <p className="min-w-0 flex-[1_1_280px] text-[15px] text-body">{fonction.texte}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Etapes() {
  return (
    <section id="etapes" aria-labelledby="etapes-titre" className={`${SECTION} flex-col gap-8`}>
      <div className="flex max-w-[640px] flex-col gap-3">
        <p className={SURTITRE}>{ETAPES.surtitre}</p>
        <h2 id="etapes-titre" className={TITRE}>
          {ETAPES.titre}
        </h2>
      </div>
      <ol className="m-0 flex list-none flex-wrap gap-x-10 gap-y-8 p-0">
        {ETAPES.liste.map((etape, rang) => (
          <li
            key={etape.titre}
            className="flex min-w-0 flex-[1_1_280px] flex-col gap-2 border-t-2 border-ink pt-4"
          >
            <span className={SURTITRE}>Étape {rang + 1}</span>
            <h3 className="text-lg font-semibold text-ink">{etape.titre}</h3>
            <p className="text-sm text-body">{etape.texte}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
