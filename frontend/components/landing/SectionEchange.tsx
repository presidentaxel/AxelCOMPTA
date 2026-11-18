import { FormulaireEchange } from "@/components/landing/FormulaireEchange";
import { ECHANGE } from "@/lib/landing-contenu";

/** La demande d'échange : un panneau blanc cerné d'un filet, le texte à
 * gauche et le formulaire à droite (il passe dessous sur un téléphone). */
export function SectionEchange() {
  return (
    <section
      id="echange"
      aria-labelledby="echange-titre"
      className="mx-auto w-full max-w-[1280px] px-[clamp(20px,4vw,48px)] pb-[clamp(48px,6vw,96px)] pt-[clamp(24px,4vw,48px)]"
    >
      <div className="flex flex-wrap items-start gap-x-16 gap-y-8 rounded-xl border border-border bg-canvas p-[clamp(24px,5vw,56px)]">
        <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-4">
          <p className="text-xs font-semibold uppercase tracking-[0.06em] text-muted">{ECHANGE.surtitre}</p>
          <h2
            id="echange-titre"
            className="text-balance text-[32px] font-semibold leading-[1.15] tracking-[-0.02em] text-ink"
          >
            {ECHANGE.titre}
          </h2>
          <p className="max-w-[420px] text-base text-body">{ECHANGE.texte}</p>
        </div>
        <div className="min-w-0 flex-[1_1_360px]">
          <FormulaireEchange />
        </div>
      </div>
    </section>
  );
}
