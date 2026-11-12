"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { CLASSE_LIEN_ACTION } from "@/components/BoutonLien";
import { InstructionAlerte } from "@/components/InstructionAlerte";
import { PanneauEtat } from "@/components/PanneauEtat";
import { QuarantaineDossier } from "@/components/QuarantaineDossier";
import { Squelette } from "@/components/Squelette";
import { Card } from "@/components/ui/card";
import {
  ErreurAuthGestionnaire,
  ModeExpertRefuse,
  instruireAlerte,
  listerAnomalies,
  listerDossiers,
} from "@/lib/auth-gestionnaire";
import { messageEchecChargement } from "@/lib/session";
import type { AlerteAnomalie } from "@/lib/types";
import { useDroitGestionnaire } from "@/lib/use-droit";

/** Pourquoi la liste n'a pas pu être lue, et si relire peut y changer
 * quelque chose : un refus du mode expert (AXE-800) ne se rattrape pas. */
type EchecLecture = { message: string; reessayable: boolean };

export default function AnomaliesPage() {
  const params = useParams<{ dossierId: string }>();
  const router = useRouter();
  const droit = useDroitGestionnaire();
  const dossierId = params.dossierId;
  const [alertes, setAlertes] = useState<AlerteAnomalie[] | null>(null);
  const [nom, setNom] = useState<string | null>(null);
  const [echecLecture, setEchecLecture] = useState<EchecLecture | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState<string | null>(null);

  const charger = useCallback(() => {
    listerAnomalies(dossierId)
      .then(setAlertes)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) {
          router.replace("/connexion");
        } else if (exception instanceof ModeExpertRefuse) {
          // AXE-800 : le détail d'un dossier est à l'expert-comptable.
          setEchecLecture({ message: exception.message, reessayable: false });
        } else {
          setEchecLecture({
            message: messageEchecChargement(exception, "Les anomalies n'ont pas pu être chargées."),
            reessayable: true,
          });
        }
      });
  }, [dossierId, router]);

  useEffect(() => {
    charger();
    listerDossiers()
      .then((dossiers) =>
        setNom(dossiers.find((dossier) => dossier.dossier_id === dossierId)?.nom ?? null),
      )
      .catch(() => setNom(null));
  }, [charger, dossierId]);

  async function decider(alerteId: string, decision: AlerteAnomalie["etat"], commentaire: string) {
    setEnvoi(alerteId);
    setErreur(null);
    try {
      const miseAJour = await instruireAlerte(dossierId, alerteId, decision, commentaire);
      setAlertes((courantes) =>
        (courantes ?? []).map((alerte) => (alerte.id === alerteId ? miseAJour : alerte)),
      );
    } catch (exception) {
      setErreur(
        exception instanceof Error
          ? exception.message
          : "La décision n'a pas pu être enregistrée. Réessayez.",
      );
    } finally {
      setEnvoi(null);
    }
  }

  const retour = `/portefeuille?ouvert=${dossierId}`;

  return (
    <div>
      <Link href={retour} className={CLASSE_LIEN_ACTION}>
        Entreprises
      </Link>
      <h1 className="mt-4 text-[22px] leading-[1.21] font-semibold tracking-[-0.02em] text-ink">
        Anomalies{nom ? ` · ${nom}` : ""}
      </h1>
      <p className="mt-2 text-sm text-subtle">
        Dépenses hors profil du dossier, à justifier. Prenez-en une en instruction, puis indiquez votre
        décision et son motif.
      </p>
      {!alertes && !echecLecture && (
        <div className="mt-8 grid gap-4 xl:grid-cols-2" aria-hidden>
          <Squelette className="h-40 w-full" />
          <Squelette className="h-40 w-full" />
        </div>
      )}
      {echecLecture && (
        <div className="mt-8">
          <PanneauEtat
            type="erreur"
            message={echecLecture.message}
            action={
              echecLecture.reessayable
                ? {
                    libelle: "Réessayer",
                    onClick: () => {
                      setEchecLecture(null);
                      charger();
                    },
                  }
                : { libelle: "Retour aux entreprises", href: retour }
            }
          />
        </div>
      )}
      {erreur && (
        <Card variant="danger" role="alert" className="mt-6 text-sm">
          {erreur}
        </Card>
      )}
      <QuarantaineDossier dossierId={dossierId} ecriture={droit.ecriture} />
      {alertes && alertes.length === 0 && (
        <div className="mt-8">
          <PanneauEtat
            type="vide"
            message="Aucune dépense à qualifier."
            action={{ libelle: "Retour aux entreprises", href: retour }}
          />
        </div>
      )}
      {alertes && alertes.length > 0 && (
        <div className="mt-8 grid items-start gap-4 xl:grid-cols-2">
          {alertes.map((alerte) => (
            <InstructionAlerte
              key={alerte.id}
              dossierId={dossierId}
              alerte={alerte}
              envoi={envoi === alerte.id}
              lecture={!droit.ecriture}
              onDecider={(decision, commentaire) => void decider(alerte.id, decision, commentaire)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
