"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { lancerRapprochementRollee, lireRapprochementRollee } from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";
import { phraseRapprochement, rapprochementEnCours, type PassageRollee } from "@/lib/liens-rollee";

const RELECTURE_MS = 4000;

/** AXE-918 : « Rapprocher Rollee » relie les chauffeurs à leur compte Rollee
 * sans attendre la nuit. Le worker lit tous les comptes Rollee (quelques
 * minutes) ; l'état se relit tant qu'il n'a pas fini, puis la section
 * « comptes à choisir » est rechargée. */
export function RapprochementRollee({
  ecriture,
  onTermine,
}: {
  ecriture: boolean;
  onTermine: () => void;
}) {
  const [passage, setPassage] = useState<PassageRollee | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const relire = useCallback(() => {
    lireRapprochementRollee()
      .then(setPassage)
      .catch(() => setPassage(null));
  }, []);
  useEffect(relire, [relire]);

  const enCours = rapprochementEnCours(passage);
  useEffect(() => {
    if (!enCours) return;
    const minuterie = window.setInterval(() => {
      lireRapprochementRollee()
        .then((suivant) => {
          setPassage(suivant);
          if (!rapprochementEnCours(suivant)) onTermine();
        })
        .catch(() => undefined);
    }, RELECTURE_MS);
    return () => window.clearInterval(minuterie);
  }, [enCours, onTermine]);

  function lancer() {
    setErreur(null);
    lancerRapprochementRollee()
      .then(setPassage)
      .catch((exception) =>
        setErreur(exception instanceof ApiError ? exception.message : "Le rapprochement n'a pas pu être lancé."),
      );
  }

  const phrase = erreur ?? phraseRapprochement(passage, formatDate);
  const enEchec = erreur !== null || passage?.statut === "echec";
  return (
    <div className="mt-4 flex flex-wrap items-center gap-3">
      {ecriture && (
        <Button type="button" variant="secondary" size="sm" disabled={enCours} onClick={lancer}>
          {enCours ? "Rapprochement…" : "Rapprocher Rollee"}
        </Button>
      )}
      {phrase && (
        <p role={enEchec ? "alert" : "status"} className={`text-[13px] ${enEchec ? "text-danger" : "text-muted"}`}>
          {phrase}
        </p>
      )}
    </div>
  );
}
