import Image from "next/image";

/** Marque du produit : le panda roux dans son hexagone (`public/logo.png`,
 * 200 px, fond transparent), puis « AxeL » et le badge Alpha. Le badge dit que
 * le produit commence, sans étiquette de démonstration. Le logo porte ses
 * propres couleurs : il ne dépend pas des tokens. */
export function Marque({ surFondSombre = false }: { surFondSombre?: boolean }) {
  const encre = surFondSombre ? "var(--color-on-dark)" : "var(--color-ink)";
  const filet = surFondSombre ? "var(--color-on-dark-mute)" : "var(--color-border-strong)";
  const alpha = surFondSombre ? "var(--color-on-dark-mute)" : "var(--color-subtle)";

  return (
    <div className="flex items-center gap-2">
      <Image src="/logo.png" alt="" width={32} height={32} priority className="size-8 shrink-0" />
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
