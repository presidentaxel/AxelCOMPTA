"use client";

import { useCallback, useEffect, useState } from "react";

import { MessageAcces, type TonMessage } from "@/components/MessageAcces";
import { PageAcces, TitreAcces } from "@/components/PageAcces";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  ETAT_ATTENTE,
  ETAT_INJOIGNABLE,
  etatApresReponse,
  type EtatDesinscription,
} from "@/lib/desinscription";

/** Un refus du lien n'est pas une erreur d'authentification : pas de rouge. */
const TON_PAR_STATUT: Record<EtatDesinscription["statut"], TonMessage> = {
  attente: "attente",
  faite: "succes",
  refusee: "attention",
  injoignable: "attention",
};

/** AXE-808 : lien en bas de chaque rappel. Public : la signature du lien
 * suffit, aucun compte n'est demandé. */
export default function DesinscriptionPage() {
  const [etat, setEtat] = useState<EtatDesinscription>(ETAT_ATTENTE);

  const enregistrer = useCallback(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${base}/desinscription${window.location.search}`)
      .then(async (reponse) => {
        const corps = (await reponse.json().catch(() => ({}))) as { message?: unknown; detail?: unknown };
        setEtat(etatApresReponse(reponse.ok, corps));
      })
      .catch(() => setEtat(ETAT_INJOIGNABLE));
  }, []);

  useEffect(() => {
    // La désinscription part à l'ouverture du lien : c'est tout l'écran.
    enregistrer();
  }, [enregistrer]);

  return (
    <PageAcces>
      <TitreAcces>Rappels</TitreAcces>
      <Card className="mt-6">
        <MessageAcces ton={TON_PAR_STATUT[etat.statut]}>{etat.message}</MessageAcces>
      </Card>
      {etat.statut === "injoignable" && (
        <Button
          type="button"
          className="mt-4 w-full"
          onClick={() => {
            setEtat(ETAT_ATTENTE);
            enregistrer();
          }}
        >
          Réessayer
        </Button>
      )}
    </PageAcces>
  );
}
