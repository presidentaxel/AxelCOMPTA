import Link from "next/link";

import { ExtraitJournal } from "@/components/landing/ExtraitJournal";
import { LienAction } from "@/components/LienAction";
import { Button } from "@/components/ui/button";
import { HERO } from "@/lib/landing-contenu";

/** Le titre d'accueil, un seul par écran (DESIGN.md › display-xl), avec son
 * surlignage jaune, un seul aussi. Le bouton principal est noir : l'orange ne
 * sert qu'au lien qui le suit. */
export function HeroLanding() {
  return (
    <section className="mx-auto flex w-full max-w-[1280px] flex-wrap items-center gap-x-16 gap-y-10 px-[clamp(20px,4vw,48px)] pb-[clamp(48px,6vw,88px)] pt-[clamp(32px,6vw,72px)]">
      <div className="flex min-w-0 flex-[1_1_400px] flex-col gap-6">
        <p className="text-xs font-semibold uppercase tracking-[0.06em] text-muted">{HERO.surtitre}</p>
        <h1 className="text-balance text-[clamp(38px,5.2vw,56px)] font-semibold leading-[1.05] tracking-[-0.04em] text-ink">
          {HERO.titre}{" "}
          <span className="bg-[linear-gradient(transparent_62%,var(--color-highlight)_62%)]">
            {HERO.titreSurligne}
          </span>
        </h1>
        <p className="max-w-[500px] text-lg leading-[1.55] text-body">{HERO.texte}</p>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <Button asChild size="lg" className="px-5">
            <Link href="#echange">{HERO.action}</Link>
          </Button>
          <LienAction href="#etapes">{HERO.lien}</LienAction>
        </div>
        <p className="text-[13px] text-subtle">{HERO.garanties}</p>
      </div>
      <div className="min-w-0 flex-[1.25_1_520px]">
        <ExtraitJournal />
      </div>
    </section>
  );
}
