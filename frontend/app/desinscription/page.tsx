"use client";

import { useEffect, useState } from "react";

/** AXE-808 : lien en bas de chaque rappel. Public : la signature du lien
 * suffit, aucun compte n'est demandé. */
export default function DesinscriptionPage() {
  const [message, setMessage] = useState("Enregistrement…");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
    fetch(`${base}/desinscription${window.location.search}`)
      .then(async (reponse) => {
        const corps = (await reponse.json().catch(() => ({}))) as { message?: string; detail?: string };
        setMessage(reponse.ok ? (corps.message ?? "C'est noté.") : (corps.detail ?? "Ce lien n'est pas valable."));
      })
      .catch(() => setMessage("Le serveur ne répond pas. Réessayez dans un instant."));
  }, []);

  return (
    <main className="mx-auto max-w-md px-4 py-16">
      <h1 className="text-xl font-semibold text-ink">Rappels</h1>
      <p role="status" className="mt-4 text-sm text-ink">
        {message}
      </p>
    </main>
  );
}
