"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Aide, pourquoiEnvoi } from "@/components/Aide";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCanauxEnvoi } from "@/lib/use-canaux-envoi";
import {
  type ConnexionDossier,
  type ConnexionsBancaires,
  ErreurAuthGestionnaire,
  lireConnexionsBancaires,
  type ModeRelance,
  reglerRelanceDossier,
  reglerRelancePortefeuille,
} from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";
import { useDroitGestionnaire } from "@/lib/use-droit";

const STATUTS: Record<ConnexionDossier["statut"], string> = {
  expire: "Expirée",
  a_renouveler: "À renouveler",
  jamais_connecte: "Jamais connectée",
  actif: "Active",
};

const SANTES: Partial<Record<ConnexionDossier["sante"], string>> = {
  auth_requise: "La banque demande de confirmer",
  sans_acces: "Accès aux données coupé",
  en_pause: "En pause",
};

const MODES: { mode: ModeRelance; titre: string; detail: string }[] = [
  {
    mode: "auto",
    titre: "Relance automatique",
    detail:
      "AxeLCompta prévient l'entreprise dans son application : deux semaines avant, une semaine avant, à l'expiration, puis tous les 3 jours. Aucun SMS ni e-mail ne part.",
  },
  {
    mode: "manuel",
    titre: "Relance manuelle",
    detail:
      "Rien n'est envoyé. Vous suivez cette page et vous contactez l'entreprise vous-même. L'envoi par SMS ou e-mail n'est pas branché.",
  },
];

/** doc 14 §2.2 et §2.3 : l'état des connexions bancaires, écran de premier
 * rang, et le mode de relance du portefeuille ou d'un dossier. */
export default function ConnexionsBancairesPage() {
  const router = useRouter();
  const droit = useDroitGestionnaire();
  const canauxEnvoi = useCanauxEnvoi();
  const [donnees, setDonnees] = useState<ConnexionsBancaires | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  const charger = useCallback(() => {
    lireConnexionsBancaires()
      .then(setDonnees)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) router.replace("/connexion");
        else setErreur("Impossible de charger les connexions bancaires.");
      });
  }, [router]);

  useEffect(() => {
    charger();
  }, [charger]);

  async function regler(action: () => Promise<void>) {
    setEnCours(true);
    setErreur(null);
    try {
      await action();
      charger();
    } catch (exception) {
      setErreur(exception instanceof Error ? exception.message : "Réglage refusé.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div>
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Connexions bancaires</h1>
      <p className="mt-2 text-sm text-subtle">
        Sans connexion valide, les opérations d&apos;une entreprise n&apos;arrivent plus.
        <Aide texte={pourquoiEnvoi(canauxEnvoi)} />
      </p>
      {erreur && <p className="mt-4 text-sm text-danger">{erreur}</p>}
      {donnees && (
        <>
          <dl className="mt-8 flex flex-wrap gap-x-12 gap-y-4">
            <Compteur libelle="Expirées" valeur={donnees.compteurs.expire} alerte />
            <Compteur libelle="À confirmer" valeur={donnees.a_reconnecter} alerte />
            <Compteur libelle="À renouveler (14 jours)" valeur={donnees.compteurs.a_renouveler} />
            <Compteur libelle="Actives" valeur={donnees.compteurs.actif} />
            <Compteur libelle="Jamais connectées" valeur={donnees.compteurs.jamais_connecte} />
          </dl>

          <section className="mt-10">
            <h2 className="text-sm font-medium text-ink">
              Relances des entreprises
              <Aide texte={pourquoiEnvoi(canauxEnvoi)} />
            </h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {MODES.map(({ mode, titre, detail }) => {
                const actif = donnees.relance_portefeuille === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    disabled={!droit.ecriture || enCours || actif}
                    onClick={() => void regler(() => reglerRelancePortefeuille(mode))}
                    aria-pressed={actif}
                    className={`rounded-md border p-4 text-left ${actif ? "border-ink bg-primary-subtle" : "border-border-strong hover:border-ink"}`}
                  >
                    <span className="text-sm font-medium text-ink">{titre}</span>
                    <span className="mt-1 block text-xs text-subtle">{detail}</span>
                  </button>
                );
              })}
            </div>
          </section>

          <Table className="mt-10">
            <TableHeader>
              <TableRow>
                <TableHead>Entreprise</TableHead>
                <TableHead>Connexion</TableHead>
                <TableHead>Expire le</TableHead>
                <TableHead>Dernière mise à jour</TableHead>
                <TableHead>Relances</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {donnees.dossiers.map((dossier) => (
                <TableRow key={dossier.dossier_id} className="align-top">
                  <TableCell>{dossier.nom}</TableCell>
                  <TableCell>
                    <Etat dossier={dossier} />
                  </TableCell>
                  <TableCell className="tabular-nums">
                    {dossier.expire_le ? formatDate(dossier.expire_le) : "—"}
                    {dossier.jours_restants !== null && dossier.jours_restants >= 0 && (
                      <span className="block text-xs text-subtle">
                        dans {dossier.jours_restants} jour{dossier.jours_restants > 1 ? "s" : ""}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="tabular-nums text-subtle">
                    {dossier.dernier_rafraichissement
                      ? formatDate(dossier.dernier_rafraichissement)
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {(dossier.statut === "expire" || dossier.statut === "a_renouveler") && (
                      <Link href="/rappels" className="mb-2 block text-sm font-medium text-signal hover:underline">
                        Relancer
                      </Link>
                    )}
                    <Select
                      aria-label={`Relances pour ${dossier.nom}`}
                      disabled={!droit.ecriture || enCours}
                      value={dossier.relance_propre ? dossier.relance : "portefeuille"}
                      onValueChange={(valeur) => {
                        void regler(() =>
                          reglerRelanceDossier(
                            dossier.dossier_id,
                            valeur === "portefeuille" ? null : (valeur as ModeRelance),
                          ),
                        );
                      }}
                      options={[
                        {
                          value: "portefeuille",
                          label: `Comme le portefeuille (${donnees.relance_portefeuille === "auto" ? "automatique" : "manuel"})`,
                        },
                        { value: "auto", label: "Automatique" },
                        { value: "manuel", label: "Manuel" },
                      ]}
                      className="min-w-64"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  );
}

function Compteur({ libelle, valeur, alerte = false }: { libelle: string; valeur: number; alerte?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-subtle">{libelle}</dt>
      <dd
        className={`text-[22px] font-bold tabular-nums ${alerte && valeur > 0 ? "text-danger" : "text-ink"}`}
      >
        {valeur}
      </dd>
    </div>
  );
}

function Etat({ dossier }: { dossier: ConnexionDossier }) {
  const probleme = SANTES[dossier.sante];
  const urgent = dossier.statut === "expire" || dossier.sante === "auth_requise";
  return (
    <span className={urgent ? "text-danger" : dossier.statut === "a_renouveler" ? "text-warning" : "text-ink"}>
      {STATUTS[dossier.statut]}
      {probleme && <span className="block text-xs">{probleme}</span>}
    </span>
  );
}
