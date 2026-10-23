"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { joindreJustificatifChauffeur } from "@/lib/auth-chauffeur";
import { formatDate, formatMontant } from "@/lib/format";
import {
  graineFichier,
  nomCommercant,
  simulerLectureTicket,
  type LectureTicket,
} from "@/lib/lecture-ticket";
import type { TransactionVue } from "@/lib/types";

/** Une photo s'attache à une seule dépense du mois, jamais à toutes.
 * La lecture est simulée : on confirme si ça colle, sinon on dit pourquoi. */
export function StationTickets({
  dossierId,
  mois,
  depenses,
  onJointe,
}: {
  dossierId: string;
  mois: string;
  depenses: TransactionVue[];
  onJointe: (transaction: TransactionVue) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [lecture, setLecture] = useState<LectureTicket | null>(null);
  const [fichier, setFichier] = useState<File | null>(null);
  const [enLecture, setEnLecture] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [choisir, setChoisir] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const sansTicket = depenses.filter((depense) => !depense.a_justificatif);
  const moisLu = new Intl.DateTimeFormat("fr-FR", { month: "long" }).format(
    new Date(`${mois}-01T12:00:00`),
  );

  function ouvrirAppareil() {
    setErreur(null);
    inputRef.current?.click();
  }

  function lire(photo: File) {
    setFichier(photo);
    setLecture(null);
    setChoisir(false);
    setEnLecture(true);
    setErreur(null);
    window.setTimeout(() => {
      setLecture(simulerLectureTicket(graineFichier(photo), sansTicket));
      setEnLecture(false);
    }, 700);
  }

  async function poser(ecritureId: string) {
    if (!fichier) return;
    setEnvoi(true);
    setErreur(null);
    try {
      const transaction = await joindreJustificatifChauffeur(dossierId, ecritureId, fichier);
      onJointe(transaction);
      setLecture(null);
      setFichier(null);
      setChoisir(false);
    } catch (exception) {
      setErreur(exception instanceof ApiError ? exception.message : "Échec de l'envoi de la photo.");
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <section className="mt-6 border-b border-hairline pb-4">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(evenement) => {
          const photo = evenement.target.files?.[0];
          if (photo) lire(photo);
          evenement.target.value = "";
        }}
      />
      <h2 className="text-base font-semibold text-ink">Tickets</h2>
      <p className="mt-1 text-sm text-subtle">{phraseManquants(sansTicket.length, moisLu)}</p>
      {!lecture && !enLecture && sansTicket.length > 0 && (
        <Button type="button" variant="secondary" className="mt-4 w-full" onClick={ouvrirAppareil}>
          Ajouter un ticket à une dépense
        </Button>
      )}
      {enLecture && <p className="mt-4 text-sm text-subtle">Lecture du ticket…</p>}
      {lecture && (
        <Resultat
          lecture={lecture}
          envoi={envoi}
          choisir={choisir}
          autres={sansTicket.filter((depense) => depense.ecriture_id !== lecture.mouvement?.ecriture_id)}
          onConfirmer={() => lecture.mouvement && void poser(lecture.mouvement.ecriture_id)}
          onChoisir={() => setChoisir(true)}
          onPoser={(id) => void poser(id)}
          onReprendre={ouvrirAppareil}
        />
      )}
      {erreur && <p className="mt-2 text-sm text-danger">{erreur}</p>}
    </section>
  );
}

function phraseManquants(nombre: number, mois: string): string {
  if (nombre === 0) return `Les sorties de ${mois} ont leur ticket.`;
  const entree = "Les entrées n'en demandent pas.";
  if (nombre === 1) {
    return `1 sortie sans ticket en ${mois}. La photo s'attache à cette dépense. ${entree}`;
  }
  return `${nombre} sorties sans ticket en ${mois}. Une photo s'attache à une seule dépense, pas aux ${nombre}. ${entree}`;
}

function Resultat({
  lecture,
  envoi,
  choisir,
  autres,
  onConfirmer,
  onChoisir,
  onPoser,
  onReprendre,
}: {
  lecture: LectureTicket;
  envoi: boolean;
  choisir: boolean;
  autres: TransactionVue[];
  onConfirmer: () => void;
  onChoisir: () => void;
  onPoser: (ecritureId: string) => void;
  onReprendre: () => void;
}) {
  const mouvement = lecture.mouvement;
  const nom = mouvement ? nomCommercant(mouvement.libelle) : "";
  return (
    <div className="mt-4">
      <Comparaison
        titre="Ticket"
        enseigne={lecture.enseigne}
        montant={lecture.montant_cts}
        date={lecture.date}
      />
      {mouvement && (
        <Comparaison
          titre="Mouvement"
          enseigne={nom}
          montant={mouvement.montant_cts}
          date={mouvement.date}
        />
      )}
      <p className="mt-3 text-sm text-ink">{raison(lecture, mouvement)}</p>
      {mouvement && (
        <p className="mt-2 text-sm text-ink">
          Cette photo sera posée sur {nom} ({formatMontant(mouvement.montant_cts)}).
        </p>
      )}
      {lecture.ecart === null && mouvement && (
        <Button type="button" className="mt-4 w-full" disabled={envoi} onClick={onConfirmer}>
          {envoi ? "Envoi…" : `Poser sur ${nom}`}
        </Button>
      )}
      {lecture.ecart !== null && !choisir && (
        <div className="mt-4 flex flex-col gap-2">
          {mouvement && (
            <Button type="button" className="w-full" disabled={envoi} onClick={onConfirmer}>
              {envoi ? "Envoi…" : `Poser sur ${nom}`}
            </Button>
          )}
          {mouvement && (
            <Button type="button" variant="secondary" disabled={envoi} onClick={onChoisir}>
              Choisir un autre mouvement
            </Button>
          )}
          <button type="button" className="py-2 text-sm font-medium text-primary" onClick={onReprendre}>
            Choisir une autre photo
          </button>
        </div>
      )}
      {choisir && (
        <ul className="mt-3">
          {autres.slice(0, 5).map((depense) => (
            <li key={depense.ecriture_id} className="border-t border-hairline">
              <button
                type="button"
                disabled={envoi}
                className="flex w-full items-baseline justify-between gap-3 py-3 text-left"
                onClick={() => onPoser(depense.ecriture_id)}
              >
                <span className="min-w-0 truncate text-sm font-medium text-ink">
                  {nomCommercant(depense.libelle)}
                </span>
                <span className="shrink-0 text-sm tabular-nums text-amount-negative">
                  {formatMontant(depense.montant_cts)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Comparaison({
  titre,
  enseigne,
  montant,
  date,
}: {
  titre: string;
  enseigne: string;
  montant: number;
  date: string;
}) {
  return (
    <p className="mt-3 flex items-baseline justify-between gap-3">
      <span className="min-w-0">
        <span className="block text-xs text-subtle">{titre}</span>
        <span className="block truncate text-sm font-medium text-ink">{enseigne}</span>
        {date && <span className="block text-xs text-subtle">{formatDate(date)}</span>}
      </span>
      <span className="shrink-0 text-sm font-semibold tabular-nums text-ink">{formatMontant(montant)}</span>
    </p>
  );
}

function raison(lecture: LectureTicket, mouvement: TransactionVue | null): string {
  if (lecture.ecart === null) return "Ça colle. On peut le poser sur ce mouvement.";
  if (lecture.ecart === "aucun" || !mouvement) return "Aucune dépense sans ticket ce mois-ci.";
  if (lecture.ecart === "montant") {
    const ecart = Math.abs(lecture.montant_cts - mouvement.montant_cts);
    return `Le montant ne colle pas. Écart de ${formatMontant(ecart)}.`;
  }
  return `L'enseigne ne colle pas. Le ticket dit « ${lecture.enseigne} », le mouvement est ${nomCommercant(mouvement.libelle)}.`;
}
