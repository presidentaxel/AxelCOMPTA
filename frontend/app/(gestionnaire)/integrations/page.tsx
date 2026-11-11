"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Badge, type BadgeVariant } from "@/components/Badge";
import { IntegrationEnvoi } from "@/components/IntegrationEnvoi";
import { LienAction } from "@/components/LienAction";
import { Squelette } from "@/components/Squelette";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  lireCategorisation,
  lireIntegrationsEnvoi,
  obtenirSessionGestionnaire,
} from "@/lib/auth-gestionnaire";
import { useDroitGestionnaire } from "@/lib/use-droit";
import type { EtatCategorisation } from "@/lib/types";

const PREVUES = [
  {
    nom: "Rollee",
    detail: "Lirait les courses et les versements Uber, Bolt et Heetch de chaque chauffeur.",
  },
  {
    nom: "Bridge",
    detail: "Connecterait la banque en direct, en plus de Digifactory.",
  },
  {
    nom: "Volubile",
    detail: "Passerait les appels des relances configurées dans Rappels.",
  },
];

/** La catégorisation se lit en deux temps : `chargement` réserve sa ligne dans
 * le tableau (pas de saut quand elle arrive), `indisponible` la retire (l'état
 * n'a pas pu être lu : on n'affiche rien plutôt qu'un faux « en ordre »). */
type LectureCategorisation =
  | { statut: "chargement" }
  | { statut: "indisponible" }
  | { statut: "lue"; etat: EtatCategorisation };

/** Digifactory est le canal bancaire du portefeuille : les comptes des
 * entreprises arrivent par lui, l'app chauffeur ne propose donc pas de
 * connecter sa banque. Les autres intégrations sont annoncées, pas branchées. */
export default function IntegrationsPage() {
  const router = useRouter();
  const [categorisation, setCategorisation] = useState<LectureCategorisation>({
    statut: "chargement",
  });
  const [envoi, setEnvoi] = useState<Record<string, string>>({});
  // Sans cela, les canaux s'afficheraient « À brancher » le temps de la lecture
  // puis changeraient d'état : on réserve leur place avec des squelettes.
  const [envoiLu, setEnvoiLu] = useState(false);
  const droit = useDroitGestionnaire();

  useEffect(() => {
    if (obtenirSessionGestionnaire() === null) {
      router.replace("/connexion");
      return;
    }
    let actif = true;
    lireIntegrationsEnvoi()
      .then((canaux) => {
        if (actif) setEnvoi(canaux);
      })
      .catch(() => {
        // Non lu : les deux canaux s'affichent « À brancher ».
      })
      .finally(() => {
        if (actif) setEnvoiLu(true);
      });
    lireCategorisation()
      .then((etat) => {
        if (actif) setCategorisation(etat ? { statut: "lue", etat } : { statut: "indisponible" });
      })
      .catch(() => {
        if (actif) setCategorisation({ statut: "indisponible" });
      });
    return () => {
      actif = false;
    };
  }, [router]);

  return (
    <div>
      <h1 className="text-[28px] font-semibold tracking-[-0.02em] text-ink">Intégrations</h1>
      <p className="mt-2 max-w-[75ch] text-sm text-subtle">
        Digifactory apporte les comptes bancaires des entreprises. Le reste n&apos;est pas encore
        connecté.
      </p>

      <Card variant="section" className="mt-8 overflow-hidden">
        <Table>
          <TableHeader>
            <tr>
              <TableHead className="w-64">Intégration</TableHead>
              <TableHead>Rôle</TableHead>
              <TableHead className="w-40">État</TableHead>
            </tr>
          </TableHeader>
          <TableBody>
            <Ligne
              nom="Digifactory"
              etat={<Badge variant="validated">Branché</Badge>}
              detail={
                <>
                  Les opérations arrivent chaque heure ; l&apos;état de chaque banque est dans{" "}
                  <LienAction href="/connexions-bancaires" className="min-h-0">
                    Connexions bancaires
                  </LienAction>
                  .
                </>
              }
            />
            <LigneCategorisation lecture={categorisation} />
            {PREVUES.map((integration) => (
              <Ligne
                key={integration.nom}
                nom={integration.nom}
                detail={integration.detail}
                // `neutral` : un simple tag d'information, hors statut d'écriture.
                etat={<Badge variant="neutral">Prévu</Badge>}
              />
            ))}
          </TableBody>
        </Table>
      </Card>

      <section className="mt-10" aria-labelledby="titre-envoi">
        <h2 id="titre-envoi" className="text-base font-semibold text-ink">
          Envoi des rappels
        </h2>
        <p className="mt-1 max-w-[75ch] text-sm text-subtle">
          Les rappels aux chauffeurs partent par votre e-mail et votre SMS. Les identifiants sont
          chiffrés et ne s&apos;affichent plus après l&apos;enregistrement.
        </p>
        <Card className="mt-4 py-1">
          {envoiLu ? (
            <ul className="grid gap-x-12 lg:grid-cols-2">
              {(["mail", "sms"] as const).map((canal) => (
                <IntegrationEnvoi
                  key={canal}
                  canal={canal}
                  branche={envoi[canal]}
                  admin={droit.admin}
                  onBranche={setEnvoi}
                />
              ))}
            </ul>
          ) : (
            <div
              className="grid gap-x-12 lg:grid-cols-2"
              role="status"
              aria-busy="true"
              aria-label="Chargement des canaux d'envoi"
            >
              <Squelette className="my-4 h-24" />
              <Squelette className="my-4 h-24" />
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}

function Ligne({
  nom,
  detail,
  etat,
}: {
  nom: string;
  detail: ReactNode;
  etat: ReactNode;
}) {
  return (
    <TableRow>
      <TableCell className="py-3 font-semibold text-ink">{nom}</TableCell>
      <TableCell className="py-3 text-subtle">{detail}</TableCell>
      <TableCell className="py-3">{etat}</TableCell>
    </TableRow>
  );
}

function LigneCategorisation({ lecture }: { lecture: LectureCategorisation }) {
  if (lecture.statut === "indisponible") return null;
  if (lecture.statut === "chargement") {
    return (
      <TableRow aria-busy="true">
        <TableCell className="py-3">
          <Squelette className="h-4 w-44" />
        </TableCell>
        <TableCell className="py-3">
          <Squelette className="h-4 w-3/4" />
        </TableCell>
        <TableCell className="py-3">
          <Squelette className="h-5 w-20 rounded-full" />
        </TableCell>
      </TableRow>
    );
  }
  const { etat } = lecture;
  const variante: BadgeVariant = etat.modele_charge ? "validated" : "alert";
  return (
    <Ligne
      nom="Catégorisation automatique"
      detail={
        etat.modele_charge
          ? "Le modèle est chargé : il propose une catégorie quand aucune règle ne s'applique."
          : (etat.raison ?? "Le modèle n'est pas chargé. La synchronisation est arrêtée.")
      }
      etat={<Badge variant={variante}>{etat.modele_charge ? "Branché" : "Dégradée"}</Badge>}
    />
  );
}
