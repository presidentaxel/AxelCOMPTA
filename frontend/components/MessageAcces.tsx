import { CircleAlert, CircleCheck, Info, LoaderCircle, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "cn";

/** Une phrase d'état et son icône. L'icône double toujours le texte : la
 * couleur ne porte jamais seule le sens. Rouge pour les seules erreurs
 * d'authentification (`erreur`) ; le texte des autres tons reste à l'encre. */
const TONS = {
  // Annoncée tout de suite par le lecteur d'écran.
  erreur: { Icone: CircleAlert, role: "alert", texte: "text-danger", icone: "" },
  attention: { Icone: TriangleAlert, role: "status", texte: "text-ink", icone: "text-warning" },
  succes: { Icone: CircleCheck, role: "status", texte: "text-ink", icone: "text-success" },
  info: { Icone: Info, role: "status", texte: "text-body", icone: "text-subtle" },
  attente: {
    Icone: LoaderCircle,
    role: "status",
    texte: "text-subtle",
    icone: "animate-spin motion-reduce:animate-none",
  },
} as const;

export type TonMessage = keyof typeof TONS;

export function MessageAcces({
  ton,
  id,
  className,
  children,
}: {
  ton: TonMessage;
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  const { Icone, role, texte, icone } = TONS[ton];
  return (
    <p id={id} role={role} className={cn("flex items-start gap-2 text-sm", texte, className)}>
      <Icone aria-hidden className={cn("mt-0.5 size-4 shrink-0", icone)} />
      <span className="min-w-0">{children}</span>
    </p>
  );
}
