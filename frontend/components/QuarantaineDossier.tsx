"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Montant } from "@/components/Montant";
import { PanneauEtat } from "@/components/PanneauEtat";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listerQuarantaine, resoudreQuarantaine } from "@/lib/auth-gestionnaire";
import { formatDate } from "@/lib/format";
import { phraseResolution, resteATraiter, trierQuarantaine } from "@/lib/quarantaine";
import { messageEchecChargement } from "@/lib/session";
import type { EntreeQuarantaine } from "@/lib/types";

/** Opérations bancaires que la synchro n'a pas pu écrire seule (AXE-424) :
 * montant changé ou opération retirée par la banque, opération datée dans
 * un exercice clos. « Accepter » écrit en comptabilité ; « Ignorer » non. */
export function QuarantaineDossier({ dossierId, ecriture }: { dossierId: string; ecriture: boolean }) {
  const [entrees, setEntrees] = useState<EntreeQuarantaine[] | null>(null);
  const [echecLecture, setEchecLecture] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState<string | null>(null);
  // Une relecture lancée à la main peut croiser la précédente : seule la
  // dernière demande a le droit d'écrire l'état.
  const ticket = useRef(0);

  const lire = useCallback(() => {
    const courant = ++ticket.current;
    listerQuarantaine(dossierId)
      .then((lues) => {
        if (ticket.current !== courant) return;
        setEntrees(lues);
        setEchecLecture(null);
      })
      .catch((exception: unknown) => {
        if (ticket.current === courant) {
          setEchecLecture(
            messageEchecChargement(exception, "Les opérations à revoir n'ont pas pu être lues."),
          );
        }
      });
  }, [dossierId]);

  useEffect(() => {
    lire();
  }, [lire]);

  function resoudre(entree: EntreeQuarantaine, decision: "accepter" | "ignorer") {
    setEnvoi(entree.id);
    setErreur(null);
    resoudreQuarantaine(dossierId, entree.id, decision)
      .then((resolue) =>
        setEntrees((courantes) => (courantes ?? []).map((e) => (e.id === resolue.id ? resolue : e))),
      )
      .catch((exception) =>
        setErreur(
          exception instanceof Error
            ? exception.message
            : "Cette opération n'a pas pu être traitée. Réessayez.",
        ),
      )
      .finally(() => setEnvoi(null));
  }

  if (echecLecture !== null && !entrees) {
    return (
      <section className="mt-8">
        <PanneauEtat
          type="erreur"
          message={echecLecture}
          action={{
            libelle: "Réessayer",
            onClick: () => {
              setEchecLecture(null);
              lire();
            },
          }}
        />
      </section>
    );
  }
  // La section n'existe que s'il y a quelque chose à revoir : pendant la
  // lecture comme à vide, rien ne s'affiche (pas de bloc qui apparaît puis
  // disparaît au milieu de la page).
  if (!entrees || entrees.length === 0) return null;

  return (
    <section className="mt-8" aria-labelledby="titre-quarantaine">
      <h2 id="titre-quarantaine" className="text-xl font-semibold text-ink">
        Opérations bancaires à revoir ({resteATraiter(entrees)})
      </h2>
      <p className="mt-1 text-sm text-subtle">
        La synchronisation n&apos;a pas pu les écrire seule. Accepter une opération l&apos;écrit en
        comptabilité ; l&apos;ignorer ne l&apos;écrit pas.
      </p>
      {erreur && (
        <Card variant="danger" role="alert" className="mt-3 text-sm">
          {erreur}
        </Card>
      )}
      <Card variant="section" className="mt-3 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-32">Date</TableHead>
              <TableHead>Opération</TableHead>
              <TableHead>Motif</TableHead>
              <TableHead montant>Montant</TableHead>
              <TableHead>Décision</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {trierQuarantaine(entrees).map((entree) => {
              const resolution = phraseResolution(entree, formatDate);
              return (
                <TableRow key={entree.id}>
                  <TableCell className="py-2 whitespace-nowrap tabular-nums text-subtle">
                    {entree.date ? formatDate(entree.date) : "—"}
                  </TableCell>
                  <TableCell className="py-2 text-ink">{entree.libelle ?? "Ligne illisible"}</TableCell>
                  <TableCell className="py-2 font-medium text-ink">{entree.libelle_motif}</TableCell>
                  <TableCell montant className="py-2">
                    {entree.montant_cts !== null ? <Montant centimes={entree.montant_cts} /> : "—"}
                  </TableCell>
                  <TableCell className="py-2">
                    {resolution ? (
                      <span className="text-sm text-subtle">{resolution}</span>
                    ) : (
                      ecriture && (
                        <span className="flex gap-2">
                          {entree.resoluble && (
                            <Button
                              type="button"
                              variant="secondary"
                              disabled={envoi === entree.id}
                              onClick={() => resoudre(entree, "accepter")}
                            >
                              Accepter
                            </Button>
                          )}
                          <Button
                            type="button"
                            variant="ghost"
                            disabled={envoi === entree.id}
                            onClick={() => resoudre(entree, "ignorer")}
                          >
                            Ignorer
                          </Button>
                        </span>
                      )
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>
    </section>
  );
}
