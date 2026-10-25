/** Bloc gris de la même emprise que le contenu qui va le remplacer. */
export function Squelette({ className }: { className: string }) {
  return <span aria-hidden className={`block animate-pulse rounded-md bg-surface-soft ${className}`} />;
}

export function SqueletteLignes({ nombre, className }: { nombre: number; className: string }) {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: nombre }, (_, index) => (
        <Squelette key={index} className={className} />
      ))}
    </div>
  );
}
