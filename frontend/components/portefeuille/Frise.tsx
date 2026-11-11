import { ETAPES_FRISE, rangEtape } from "@/lib/filtres-portefeuille";

/** Le compte se prépare une fois. Ensuite, par exercice : clôture, signature
 * de validation, dépôt au greffe, dépôt aux impôts, signature légale
 * (doc 02 §4 et §6, doc 19 §5.3, doc 20 §4bis).
 *
 * La liste n'affiche plus que « 3/6 · Signature » ; la frise complète des six
 * jalons, pour les deux exercices, vit dans la fiche de l'entreprise, là où
 * on a la place de la lire. */
export function Frise({
  annee,
  etape,
  compteOuvert,
}: {
  annee: number;
  etape: string;
  compteOuvert: boolean;
}) {
  const index = rangEtape(etape, compteOuvert);
  const lecture = ETAPES_FRISE.map((nom, rang) => `${nom} ${rang <= index ? "faite" : "à faire"}`).join(", ");
  return (
    <span role="img" className="flex items-start gap-3" aria-label={`${annee} : ${lecture}`}>
      <span className="w-8 shrink-0 pt-px text-xs leading-none text-subtle">{annee}</span>
      <span className="grid min-w-0 flex-1 grid-cols-6">
        {ETAPES_FRISE.map((nom, rang) => {
          const fait = rang <= index;
          const traitFait = rang < index;
          return (
            <span key={nom} className="relative flex flex-col items-center">
              {rang > 0 && (
                <span
                  className={`absolute right-1/2 top-[3px] left-0 h-px ${traitFait || fait ? "bg-primary" : "bg-border"}`}
                />
              )}
              {rang < ETAPES_FRISE.length - 1 && (
                <span
                  className={`absolute top-[3px] right-0 left-1/2 h-px ${traitFait ? "bg-primary" : "bg-border"}`}
                />
              )}
              <span className={`relative z-10 h-2 w-2 rounded-full ${fait ? "bg-primary" : "bg-border"}`} />
              <span className={`mt-1 text-center text-[10px] leading-tight ${fait ? "text-ink" : "text-subtle"}`}>
                {nom}
              </span>
            </span>
          );
        })}
      </span>
    </span>
  );
}
