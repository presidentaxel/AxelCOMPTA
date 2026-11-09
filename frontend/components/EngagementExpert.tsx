"use client";

import { useCallback, useEffect, useState } from "react";

import { Etat } from "@/components/Etat";
import { Squelette } from "@/components/Squelette";
import { Button } from "@/components/ui/button";
import {
  accepterEngagementExpert,
  lireEngagementExpert,
  type EngagementExpert as Engagement,
} from "@/lib/auth-gestionnaire";

/** AXE-800 : avant le mode expert, l'expert-comptable habilité lit et
 * accepte l'engagement de responsabilité. Un autre rôle lit pourquoi le
 * mode expert ne lui est pas ouvert. */
export function EngagementExpert({ raison, onAccepte }: { raison: string; onAccepte: () => void }) {
  const [engagement, setEngagement] = useState<Engagement | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [coche, setCoche] = useState(false);
  const [envoi, setEnvoi] = useState(false);

  const charger = useCallback(() => {
    setErreur(null);
    lireEngagementExpert()
      .then(setEngagement)
      .catch((exception: unknown) =>
        setErreur(exception instanceof Error ? exception.message : "Erreur inattendue."),
      );
  }, []);

  useEffect(() => {
    // Premier chargement à l'ouverture de l'écran.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  async function accepter() {
    if (!engagement) return;
    setEnvoi(true);
    try {
      await accepterEngagementExpert(engagement.version, engagement.texte);
      onAccepte();
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Échec de l'acceptation.");
    } finally {
      setEnvoi(false);
    }
  }

  if (erreur) return <Etat type="erreur" message={erreur} onReessayer={charger} />;
  if (!engagement) return <Squelette className="mt-6 h-40 w-full" />;
  if (!engagement.habilitation) {
    return (
      <p className="mt-6 max-w-2xl text-sm text-ink">
        {raison} Le mode expert est réservé à l&apos;expert-comptable du portefeuille, déclaré
        par un administrateur dans Équipe. Le portefeuille vous montre les agrégats de chaque
        entreprise.
      </p>
    );
  }
  return (
    <section aria-labelledby="titre-engagement" className="mt-6 max-w-2xl">
      <h2 id="titre-engagement" className="text-base font-semibold text-ink">
        Engagement de responsabilité
      </h2>
      <p className="mt-1 text-sm text-subtle">
        {engagement.habilitation.nom}, {engagement.habilitation.cabinet} — lettre de mission{" "}
        {engagement.habilitation.lettre_mission}, {engagement.habilitation.dossiers.length}{" "}
        dossier{engagement.habilitation.dossiers.length > 1 ? "s" : ""}.
      </p>
      <blockquote className="mt-4 rounded-md border border-border bg-canvas p-4 text-sm text-ink">
        {engagement.texte}
      </blockquote>
      <label className="mt-4 flex items-start gap-2 text-sm text-ink">
        <input type="checkbox" checked={coche} onChange={(e) => setCoche(e.target.checked)} />
        <span>J&apos;ai lu ce texte et je l&apos;accepte (version {engagement.version}).</span>
      </label>
      <Button type="button" className="mt-4" disabled={!coche || envoi} onClick={() => void accepter()}>
        {envoi ? "Enregistrement…" : "Accepter et ouvrir le mode expert"}
      </Button>
    </section>
  );
}
