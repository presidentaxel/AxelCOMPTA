"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ErreurAuthGestionnaire,
  inviterChauffeur,
  listerDossiers,
} from "@/lib/auth-gestionnaire";
import { libelleCompte } from "@/lib/dossier-libelles";
import type { DossierAgregat } from "@/lib/types";
import { Squelette } from "@/components/Squelette";

/** Une ligne par entreprise sans compte, plus un collage pour plusieurs.
 * Plus de liste déroulante : l'e-mail se saisit en face du nom. */
export default function InvitationsPage() {
  const router = useRouter();
  const [dossiers, setDossiers] = useState<DossierAgregat[] | null>(null);
  const [emails, setEmails] = useState<Record<string, string>>({});
  const [cible, setCible] = useState("");
  const [emailNouveau, setEmailNouveau] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState<string | null>(null);

  const charger = useCallback(() => {
    listerDossiers()
      .then(setDossiers)
      .catch((exception) => {
        if (exception instanceof ErreurAuthGestionnaire) {
          router.replace("/connexion");
        } else {
          setErreur("Impossible de charger les entreprises.");
        }
      });
  }, [router]);

  useEffect(charger, [charger]);

  const sansCompte = dossiers?.filter((dossier) => dossier.statut_invitation === null) ?? [];
  const suivies =
    dossiers?.filter((dossier) => dossier.statut_invitation === "invité" || dossier.statut_invitation === "actif") ??
    [];

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-[28px] font-bold tracking-tight text-ink">Invitations</h1>
      <p className="mt-2 text-sm text-subtle">
        Choisis une entreprise et son e-mail. L&apos;invitation part tout de suite.
      </p>
      <form
        className="mt-8 flex flex-wrap items-center gap-2"
        onSubmit={async (evenement) => {
          evenement.preventDefault();
          if (!cible) return;
          setEnCours(cible);
          setErreur(null);
          try {
            await inviterChauffeur(cible, emailNouveau);
            setEmailNouveau("");
            charger();
          } catch (exception) {
            setErreur(exception instanceof Error ? exception.message : "Échec de l'invitation.");
          } finally {
            setEnCours(null);
          }
        }}
      >
        <select
          value={cible}
          onChange={(evenement) => setCible(evenement.target.value)}
          aria-label="Entreprise à inviter"
          className="h-9 min-w-48 rounded-md border border-border bg-canvas px-3 text-sm text-ink"
        >
          <option value="">Entreprise</option>
          {(dossiers ?? []).map((dossier) => (
            <option key={dossier.dossier_id} value={dossier.dossier_id}>
              {dossier.nom}
            </option>
          ))}
        </select>
        <Input
          type="email"
          required
          value={emailNouveau}
          onChange={(evenement) => setEmailNouveau(evenement.target.value)}
          placeholder="E-mail"
          className="max-w-64"
        />
        <Button type="submit" disabled={!cible || enCours !== null}>
          Inviter
        </Button>
      </form>
      {erreur && <p className="mt-6 text-sm text-danger">{erreur}</p>}
      {!dossiers && !erreur && (
        <div className="mt-10 space-y-3" aria-hidden>
          <Squelette className="h-12 w-full" />
          <Squelette className="h-12 w-full" />
          <Squelette className="h-12 w-full" />
        </div>
      )}

      {sansCompte.length > 0 && (
        <ul className="mt-10">
          {sansCompte.map((dossier) => (
            <li key={dossier.dossier_id} className="flex items-center gap-3 border-b border-hairline py-3">
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{dossier.nom}</span>
              <Input
                type="email"
                value={emails[dossier.dossier_id] ?? ""}
                onChange={(evenement) =>
                  setEmails((actuel) => ({ ...actuel, [dossier.dossier_id]: evenement.target.value }))
                }
                placeholder="E-mail"
                className="max-w-56"
                aria-label={`E-mail de ${dossier.nom}`}
              />
              <Button
                type="button"
                size="sm"
                disabled={enCours === dossier.dossier_id || !(emails[dossier.dossier_id] ?? "").includes("@")}
                onClick={async () => {
                  setEnCours(dossier.dossier_id);
                  setErreur(null);
                  try {
                    await inviterChauffeur(dossier.dossier_id, emails[dossier.dossier_id] ?? "");
                    charger();
                  } catch (exception) {
                    setErreur(exception instanceof Error ? exception.message : "Échec de l'invitation.");
                  } finally {
                    setEnCours(null);
                  }
                }}
              >
                Inviter
              </Button>
            </li>
          ))}
        </ul>
      )}
      {dossiers && sansCompte.length === 0 && (
        <p className="mt-8 text-sm text-subtle">Toutes les entreprises ont déjà une invitation.</p>
      )}

      {suivies.length > 0 && (
        <section className="mt-10">
          <h2 className="text-sm font-semibold text-ink">Déjà lancées</h2>
          <ul className="mt-3">
            {suivies.map((dossier) => (
              <li key={dossier.dossier_id} className="flex justify-between border-b border-hairline py-3 text-sm">
                <span className="text-ink">{dossier.nom}</span>
                <span className="text-subtle">{libelleCompte(dossier.statut_invitation)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
