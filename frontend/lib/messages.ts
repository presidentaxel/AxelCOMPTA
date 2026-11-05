import { MESSAGE_SERVEUR_INJOIGNABLE } from "./session";

/** Message montrable au chauffeur. Le détail réseau utile est gardé ;
 * une coupure ne s'affiche pas comme « Failed to fetch ». */
export function messageVisible(exception: unknown, repli: string): string {
  if (!(exception instanceof Error) || exception.message.trim() === "") {
    return repli;
  }
  const brut = exception.message.toLowerCase();
  if (
    brut.includes("failed to fetch") ||
    brut.includes("networkerror") ||
    brut.includes("load failed") ||
    brut.includes("network request failed")
  ) {
    return MESSAGE_SERVEUR_INJOIGNABLE;
  }
  return exception.message;
}
