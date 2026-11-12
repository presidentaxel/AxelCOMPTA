import type { ReactNode } from "react";

/** Titre d'un écran du chauffeur : 28 px, plus grand que côté gestionnaire,
 * car il se lit à bout de bras sur un téléphone. Le sous-titre (en enfant)
 * est du texte courant de 16 px : en dessous, iOS zoomerait aussi les champs
 * qui suivent, et le chauffeur n'est pas un lecteur de tableaux. */
export function TitreEcran({
  id,
  titre,
  children,
}: {
  id?: string;
  titre: string;
  children?: ReactNode;
}) {
  return (
    <header className="mb-6">
      <h1 id={id} className="text-[28px] font-semibold leading-tight tracking-[-0.02em] text-ink">
        {titre}
      </h1>
      {children && <p className="mt-2 text-base text-subtle">{children}</p>}
    </header>
  );
}
