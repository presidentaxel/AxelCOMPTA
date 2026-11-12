"use client";

import { useEffect, useRef, useState } from "react";

import { Dialogue } from "@/components/Dialogue";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { preparerWebhook, type FicheWebhook } from "@/lib/auth-gestionnaire";

/** Ce qu'il faut reporter dans le formulaire « New Webhook » de Rollee.
 * Le secret reste chiffré au repos et masqué ici jusqu'à « Afficher ». */
export function FicheWebhookRollee({
  id,
  onFermer,
  onPrepare,
}: {
  id: string;
  onFermer: () => void;
  onPrepare: () => void;
}) {
  const [fiche, setFiche] = useState<FicheWebhook | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const prepare = useRef(onPrepare);
  useEffect(() => {
    prepare.current = onPrepare;
  });

  useEffect(() => {
    let ignore = false;
    preparerWebhook(id)
      .then((recue) => {
        if (ignore) return;
        setFiche(recue);
        prepare.current();
      })
      .catch((exception: unknown) => {
        if (ignore) return;
        const texte = exception instanceof Error ? exception.message : "Le webhook n'a pas pu être préparé.";
        setErreur(texte);
      });
    return () => {
      ignore = true;
    };
  }, [id]);

  return (
    <Dialogue titre="Relier le webhook" titreId="titre-webhook-rollee" onFermer={onFermer}>
      <p className="mt-2 text-sm text-subtle">
        Chez Rollee, créez un webhook et reportez ces valeurs. Le secret est chiffré dans
        AxeLCompta : il n&apos;apparaît dans la liste des comptes que comme un champ masqué.
      </p>
      {erreur && <p className="mt-3 text-sm text-danger">{erreur}</p>}
      {!fiche && !erreur && <p className="mt-3 text-sm text-subtle">Préparation…</p>}
      {fiche && (
        <div className="mt-4 space-y-4">
          {!fiche.joignable && (
            <p className="text-sm text-danger">
              Cette adresse est locale : Rollee ne peut pas l&apos;appeler. Le secret est prêt pour
              quand l&apos;API sera en ligne.
            </p>
          )}
          <LigneACopier libelle="Webhook URL" valeur={fiche.url} />
          <SecretACopier secret={fiche.secret} />
          <LigneACopier libelle="HTTP Method" valeur={fiche.methode} />
          <div>
            <p className="text-sm font-medium text-ink">Cases à cocher</p>
            <ul className="mt-1 list-disc pl-5 text-sm text-ink">
              {fiche.evenements.map((evenement) => (
                <li key={evenement}>{evenement}</li>
              ))}
            </ul>
            <p className="mt-1 text-xs text-subtle">Users peut rester décoché.</p>
          </div>
        </div>
      )}
      <div className="mt-5 flex justify-end">
        <Button type="button" variant="secondary" size="sm" onClick={onFermer}>
          Fermer
        </Button>
      </div>
    </Dialogue>
  );
}

function LigneACopier({ libelle, valeur }: { libelle: string; valeur: string }) {
  return (
    <label className="block text-sm text-ink">
      {libelle}
      <span className="mt-1 flex gap-2">
        <Input readOnly value={valeur} className="font-mono text-[13px]" />
        <Copier valeur={valeur} />
      </span>
    </label>
  );
}

function SecretACopier({ secret }: { secret: string }) {
  const [visible, setVisible] = useState(false);
  return (
    <label className="block text-sm text-ink">
      Secret Key
      <span className="mt-1 flex gap-2">
        <Input
          readOnly
          type={visible ? "text" : "password"}
          value={secret}
          autoComplete="off"
          spellCheck={false}
          aria-label="Secret Key"
          className="font-mono text-[13px]"
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-pressed={visible}
          onClick={() => setVisible((etat) => !etat)}
        >
          {visible ? "Masquer" : "Afficher"}
        </Button>
        <Copier valeur={secret} />
      </span>
      <span className="mt-1 block text-xs text-subtle">Chiffré au repos. Affichez-le pour le coller.</span>
    </label>
  );
}

function Copier({ valeur }: { valeur: string }) {
  const [copie, setCopie] = useState(false);
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={() => {
        void navigator.clipboard.writeText(valeur).then(() => {
          setCopie(true);
          window.setTimeout(() => setCopie(false), 1500);
        });
      }}
    >
      {copie ? "Copié" : "Copier"}
    </Button>
  );
}
