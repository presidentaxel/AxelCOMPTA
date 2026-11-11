"use client";

import { useId } from "react";

import { Dialogue } from "@/components/Dialogue";
import { Button } from "@/components/ui/button";

export type Confirmation = {
  titre: string;
  phrase: string;
  libelleConfirmer: string;
  /** Action destructive : le bouton de confirmation est `danger`, le seul
   * endroit où le rouge est un fond (DESIGN.md › `button-danger`). */
  destructive?: boolean;
  onConfirmer: () => void;
};

/** Confirmation d'une action sensible sur `Dialogue`, à la place du
 * `window.confirm` du navigateur. La phrase de la question est celle que le
 * navigateur posait ; « Annuler » est en tête, la confirmation en dernier. */
export function ConfirmationDialogue({
  confirmation,
  onFermer,
}: {
  confirmation: Confirmation;
  onFermer: () => void;
}) {
  const id = useId();
  return (
    <Dialogue titre={confirmation.titre} titreId={`${id}-titre`} onFermer={onFermer}>
      <p className="mt-3 text-sm text-body">{confirmation.phrase}</p>
      <div className="mt-6 flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onFermer}>
          Annuler
        </Button>
        <Button
          type="button"
          variant={confirmation.destructive ? "danger" : "primary"}
          onClick={() => {
            onFermer();
            confirmation.onConfirmer();
          }}
        >
          {confirmation.libelleConfirmer}
        </Button>
      </div>
    </Dialogue>
  );
}
