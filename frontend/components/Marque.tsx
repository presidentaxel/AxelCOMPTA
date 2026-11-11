/** Marque du produit. Le badge Alpha dit que le produit commence,
 * sans étiquette de démonstration. */
export function Marque({ surFondSombre = false }: { surFondSombre?: boolean }) {
  const encre = surFondSombre ? "var(--color-on-dark)" : "var(--color-ink)";
  const filet = surFondSombre ? "var(--color-on-dark-mute)" : "var(--color-border-strong)";
  const alpha = surFondSombre ? "var(--color-on-dark-mute)" : "var(--color-subtle)";

  return (
    <div className="flex items-center gap-2.5">
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
        <rect width="28" height="28" rx="8" style={{ fill: "var(--color-signal)" }} />
        <path
          d="M8 20.5 L14 7.5 L20 20.5"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2.2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <path d="M10.4 15.6 H17.6" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" />
      </svg>
      <span className="text-sm font-semibold" style={{ color: encre }}>
        AxeL
      </span>
      <span
        className="rounded-full border px-1.5 py-px text-xs font-semibold uppercase tracking-wide"
        style={{ color: alpha, borderColor: filet }}
      >
        Alpha
      </span>
    </div>
  );
}
