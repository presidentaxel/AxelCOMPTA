"use client";

// Une lecture ratée ne doit jamais ressembler à une liste vide : la personne
// voit l'erreur et peut relancer, au lieu d'agir sur un écran muet.
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { ErreurAuthChauffeur } from "@/lib/auth-chauffeur";
import { phrasePourChauffeur } from "@/lib/langage-chauffeur";

export function messageEchecLecture(exception: unknown, repli: string): string {
  const brut =
    exception instanceof ErreurAuthChauffeur || exception instanceof ApiError
      ? exception.message
      : repli;
  return phrasePourChauffeur(brut) || phrasePourChauffeur(repli);
}

export function EchecLecture({
  message,
  onReessayer,
  enCours = false,
  className = "mt-3",
}: {
  message: string;
  onReessayer: () => void;
  enCours?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <p role="alert" className="text-sm text-danger">
        {message}
      </p>
      <Button
        type="button"
        variant="secondary"
        className="mt-2 h-11"
        disabled={enCours}
        onClick={onReessayer}
      >
        Réessayer
      </Button>
    </div>
  );
}
