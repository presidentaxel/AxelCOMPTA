"use client";

import { useEffect, useState } from "react";

import { formatMontant } from "@/lib/format";

const JOUR = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

/** Le même bloc sur Activité, Exercice et Résultat : un montant, un libellé. */
export function ResultatACeJour({ centimes }: { centimes: number }) {
  const [au, setAu] = useState<string | null>(null);
  useEffect(() => {
    // La date du jour ne doit pas diverger entre le serveur et le navigateur.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAu(JOUR.format(new Date()));
  }, []);
  const negatif = centimes < 0;
  return (
    <div className="mt-6">
      <p
        className={`text-[28px] font-bold tabular-nums tracking-tight ${
          negatif ? "text-amount-negative" : "text-amount-positive"
        }`}
      >
        {formatMontant(centimes)}
      </p>
      <p className="text-sm text-subtle">
        Résultat à ce jour
        {au ? ` · ${au}` : ""}
      </p>
    </div>
  );
}
