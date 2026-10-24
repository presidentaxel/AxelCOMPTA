"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { InstructionAlerte } from "@/components/InstructionAlerte";
import { ErreurAuthGestionnaire, instruireAlerte, listerAnomalies } from "@/lib/auth-gestionnaire";
import type { AlerteAnomalie } from "@/lib/types";

export default function AnomaliesPage() {
  const params = useParams<{ dossierId: string }>();
  const router = useRouter();
  const dossierId = params.dossierId;
  const [alertes, setAlertes] = useState<AlerteAnomalie[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState<string | null>(null);

  const charger = useCallback(() => {
    listerAnomalies(dossierId)
      .then(setAlertes)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) {
          router.replace("/connexion");
        } else {
          setErreur("Impossible de charger les anomalies.");
        }
      });
  }, [dossierId, router]);

  useEffect(() => {
    charger();
  }, [charger]);

  async function decider(alerteId: string, decision: AlerteAnomalie["etat"], commentaire: string) {
    setEnvoi(alerteId);
    setErreur(null);
    try {
      const miseAJour = await instruireAlerte(dossierId, alerteId, decision, commentaire);
      setAlertes((courantes) =>
        (courantes ?? []).map((alerte) => (alerte.id === alerteId ? miseAJour : alerte)),
      );
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "La qualification a échoué.");
    } finally {
      setEnvoi(null);
    }
  }

  return (
    <div>
      <Link href="/portefeuille" className="text-sm font-medium text-primary hover:underline">
        Entreprises
      </Link>
      <h1 className="mt-4 text-[28px] font-bold tracking-tight text-ink">Anomalies</h1>
      {erreur && <p className="mt-4 text-sm text-danger">{erreur}</p>}
      {alertes && alertes.length === 0 && (
        <p className="mt-8 text-sm text-subtle">Aucune dépense à qualifier.</p>
      )}
      <div className="mt-6">
        {alertes?.map((alerte) => (
          <InstructionAlerte
            key={alerte.id}
            alerte={alerte}
            envoi={envoi === alerte.id}
            onDecider={(decision, commentaire) => void decider(alerte.id, decision, commentaire)}
          />
        ))}
      </div>
    </div>
  );
}
