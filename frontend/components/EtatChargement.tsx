"use client";

import { Button } from "@/components/ui/button";

/** Erreur de chargement : le message (réseau ou serveur) et une action. */
export function EtatErreur({
  message,
  onReessayer,
}: {
  message: string;
  onReessayer: () => void;
}) {
  return (
    <div role="alert" className="mt-6 rounded-md border border-danger-border bg-danger-subtle p-4">
      <p className="text-sm text-ink">{message}</p>
      <Button type="button" variant="secondary" className="mt-3 h-11 w-full" onClick={onReessayer}>
        Réessayer
      </Button>
    </div>
  );
}

/** Rien à montrer : une phrase et une action, jamais un écran mort. */
export function EtatVide({
  titre,
  action,
  onAction,
}: {
  titre: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <div className="mt-6 rounded-md border border-border bg-canvas p-4">
      <p className="text-sm text-ink">{titre}</p>
      <Button type="button" variant="secondary" className="mt-3 h-11 w-full" onClick={onAction}>
        {action}
      </Button>
    </div>
  );
}
