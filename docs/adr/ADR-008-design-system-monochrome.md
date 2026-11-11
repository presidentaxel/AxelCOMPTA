# ADR-008 — Design system monochrome, accent orange foncé

**Date :** 2026-11-11
**Statut :** accepté
**Décideurs :** Arthur Reichard, relecture Louis Vedovato (en attente)

## Contexte

Le design system 1.x d'AxeLCompta reposait sur un accent bleu professionnel (`#2563EB`), une gamme de neutres froids (Slate), des titres à 700 et des cartes ombrées, avec une sidebar à gauche. `DESIGN.md` posait la règle « un seul accent bleu, pas de deuxième couleur d'accent sans ADR ».

Le 2026-11-10, la remise à jour AXE-870 (PR 129) a corrigé la divergence qui s'était creusée entre le code et le document : ombres absentes de `@theme`, anneau de focus à 45 % dans le code et 12 % dans le contrat, taille 44 px du chauffeur non documentée, sidebar claire non décrite. Le contrat et le code disaient de nouveau la même chose, mais sur un design qui ne plaisait plus : générique, froid, sans signature.

La refonte AXE-873 repart de ce constat. Plusieurs directions ont été dessinées sous forme de maquettes, et la **direction « C2 »** a été retenue : monochrome, texte et bouton principal à l'encre, un seul accent orange foncé, un surligneur jaune pour le chiffre qui compte, une barre de navigation d'abord horizontale (devenue une barre latérale claire, voir la décision). Le CRM de l'équipe (crm.axelproject.fr) sert d'inspiration : son surligneur jaune et sa sobriété donnent un ton plus humain à un outil de comptabilité. Cet ADR en acte les choix et AXE-874 en porte les tokens, `DESIGN.md` et la documentation.

## Décision

**Design system v2.0 monochrome**, sur un fond blanc cassé chaud, avec un accent unique orange foncé.

- **Palette monochrome chaude.** Fond de l'application `canvas-app` `#FBFAF8`, cartes `#FFFFFF` cernées d'un filet `#E7E5E0`, sans ombre. Encre `#111111` pour le texte, corps `#3D3D3A`, secondaire `#55534E`, discret `#66645F`. `faint` `#A8A59E` est réservé aux éléments non textuels.
- **Bouton principal noir.** `primary` devient l'encre : `#111111` (survol `#2B2B2B`, appui `#000000`). Le bouton principal n'est jamais orange.
- **Accent `signal` `#C2410C`** (survol et appui `#9A3412`) : liens d'action, repères, point d'alerte de la navigation, focus. Nommé `signal` pour ne pas entrer en collision avec `--accent` de shadcn.
- **Surligneur `highlight` `#FDE7C4`** (le jaune du CRM) et lavis `highlight-wash` `#FFF8EA` pour les lignes « à traiter ». Règles : l'orange ne sert jamais de fond de bouton ; au plus un surlignage jaune par écran ; le rouge n'apparaît jamais sur un lien ou un bouton, hors bouton danger.
- **Rouge cramoisi et or pour la séparation.** `danger` passe de `#D42626` à `#BE123C` (ΔE 33 avec le signal) et l'ambre `#B45309` à l'or `#A16207` (`warning` et `pending`, ΔE 30). Un nouveau `pending-ink` `#854D0E` colore le texte sur fond `pending-subtle` (contraste 6,15). Les couleurs de sous-ton, de bordure et les sources de catégorisation (`auto-rule`, `auto-ml`, `auto-llm`) suivent ou restent inchangées.
- **Inter seule**, titres à 600 au lieu de 700. Deux tokens nouveaux : `display-xl` (56 px, un par écran, ex. « 3 dossiers à traiter. ») et `overline` (12 px, majuscules, en-têtes de liste). Les montants gardent `amount-*` avec `tabular-nums`, alignés à droite.
- **Rayons et ombres.** Contrôles (boutons, champs) à 6 px, cartes à 12 px, fenêtres à 16 px. Aucune ombre sur les cartes ; les tokens `shadow-*` ne servent qu'aux menus et fenêtres.
- **Barre latérale claire** (256 px, fond blanc, filet droit, collée à la hauteur de l'écran) : la marque en haut, les sept entrées en colonne, un bloc de compte en bas (avatar, nom de l'organisation, e-mail). L'entrée active est en poids 600 à l'encre sur un fond `surface-soft`, avec un filet vertical de 2 px qui glisse d'une entrée à l'autre ; un point `signal` signale une action attendue dans la section. Sous 1024 px, la barre latérale est remplacée par une barre haute de 56 px (marque, bouton « Menu », avatar) dont le bouton ouvre les entrées dans un tiroir. Une barre de navigation horizontale (AXE-874) avait été essayée dans la refonte, puis écartée : sur grand écran, elle laissait les côtés de la page vides. On revient donc à une barre latérale, claire cette fois.
- **Statut des dossiers** par un point et un libellé (`statut-dossier` : à traiter, à jour, sans compte, clôturé), distinct des 8 badges d'écriture, qui gardent leur sens et ne changent que de couleur.

Mesures de contraste (WCAG) : encre sur fond 18,10 ; corps sur fond 10,45 ; `muted` sur fond 5,67 ; `signal` sur fond 4,96, sur blanc 5,18, sur lavis 4,90 ; `signal-deep` sur fond 7,00 ; `danger` sur fond 6,03 ; `success` sur fond 4,81 ; `pending` sur fond 4,72.

**Cette décision remplace la règle de `DESIGN.md` « un seul accent bleu, pas de deuxième couleur d'accent sans ADR ».** L'accent unique reste le principe ; il change de couleur, et l'ADR en fixe les conditions de modification (voir « Règle à maintenir »).

## Alternatives considérées

**A — Atelier, avec une serif Fraunces pour les titres :** même monochrome chaud, mais des titres en serif.
- Non retenu à la comparaison des maquettes. Elle ajoute une seconde famille de police ; Inter seule reste la règle.

**B — Cabinet, bleu nuit avec sidebar sombre :** continuité avec le design 1.x, en plus institutionnel.
- Non retenu à la comparaison des maquettes : il prolonge le design qu'on quitte (accent bleu, sidebar sombre) au lieu d'en changer l'identité.

**D — Grand livre :** esthétique de registre comptable, lignes réglées, titres serif et chiffres en police à chasse fixe.
- Non retenu à la comparaison des maquettes. Il ajoute deux familles de police à Inter. Son surligneur jaune sur les dossiers à traiter a inspiré le surligneur de C2.

**E — Graphite sombre :** interface sombre, accent jaune clair.
- Non retenu à la comparaison des maquettes. Le mode sombre global n'est pas prévu avant la phase 5 (DESIGN.md).

**DM Sans à la place d'Inter :** testée dans le navigateur.
- Rejeté : elle n'a pas de chiffres tabulaires, ce qui casse l'alignement des colonnes de montants (invariant non négociable du design system).

**Garder l'ancien rouge `#D42626` avec le nouvel orange :**
- Rejeté : à ΔE 14 de l'orange `signal`, le rouge d'erreur et l'orange d'action sont confondus ; l'ancien ambre `#B45309` l'est aussi. D'où le cramoisi `#BE123C` et l'or `#A16207`, à ΔE 33 et 30.

## Conséquences

- **Avantages :** une identité reconnaissable (encre, filet, surligneur) sans second accent à gérer ; un signal orange qui ne se confond ni avec l'erreur ni avec l'attente ; un contraste mesuré sur chaque paire de couleurs utile ; une barre latérale claire, qui occupe le côté de l'écran au lieu de le laisser vide sur grand écran (la barre horizontale essayée d'abord laissait ces côtés vides) ; un thème piloté par tokens, que les variables shadcn référencent directement.
- **Inconvénients :** tout le code visuel est à reprendre (composants Button/Input/Card/Badge, AXE-875 ; primitives Select, Dialogue, Toast et Tableau, AXE-876 ; navigation, AXE-877), et le front mélange l'ancien et le nouveau rendu tant que ces tickets ne sont pas livrés. La barre latérale prend 256 px de large sur les écrans de 1024 px et plus. Un bouton principal noir et un accent orange demandent de la discipline : l'orange ne devient jamais un fond de bouton, le jaune apparaît une fois par écran. Le preset Nova de shadcn propose Geist par défaut, à écarter à chaque `shadcn add`. La relecture de Louis Vedovato est en attente.
- **Règle à maintenir :** tout changement d'accent, de rouge ou d'or repasse par une mesure de contraste WCAG et de ΔE contre le `signal`, avant de toucher à `DESIGN.md` ou au code ; et un second accent n'est introduit que par un nouvel ADR. `signal` ne distingue jamais seul une information : texte et point vont ensemble.
- **Porte de sortie :** les couleurs vivent dans `DESIGN.md` et dans le bloc `@theme`, et les variables génériques de shadcn les référencent. Changer l'accent revient à modifier quelques tokens et à relancer les mesures, pas à réécrire les composants ; le mode sombre global, prévu en phase 5, se construira sur les mêmes tokens.
