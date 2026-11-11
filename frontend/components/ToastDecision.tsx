"use client";

const ANNEAU =
  "outline-none focus-visible:shadow-focus-detache-sombre";

/** Confirmation éphémère : le tap est encore annulable. */
export function ToastDecision({
  libelle,
  onAnnuler,
}: {
  libelle: string;
  onAnnuler: (() => void) | null;
}) {
  return (
    <div className="fixed bottom-[calc(3.5rem+env(safe-area-inset-bottom)+0.75rem)] left-1/2 z-40 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 rounded-md border border-white/10 bg-surface-dark px-4 py-3 text-on-dark shadow-lg">
      <p className="text-sm leading-5">Classé en « {libelle} ».</p>
      {onAnnuler && (
        <div className="flex justify-end">
          <button type="button" onClick={onAnnuler} className={`min-h-11 rounded-md px-2 text-sm font-semibold ${ANNEAU}`}>
            Annuler
          </button>
        </div>
      )}
    </div>
  );
}
