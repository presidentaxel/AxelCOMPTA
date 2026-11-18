# prospection/

Les demandes d'échange qui arrivent de la page publique d'AxeLCompta
(AXE-949) : une personne sans compte laisse son nom, son e-mail, son
organisation et son profil (cabinet ou centrale), et l'équipe est prévenue
sur Slack.

**Statut démo (doc 17)** : sans objet. **Statut V1 (doc 12)** : en service
avec la landing.

## Ce que fait le module

- `models.py` : `DemandeEchange` et `preparer_demande`, qui nettoie la saisie
  et lève `SaisieInvalide` à la première erreur, avec la phrase affichée au
  visiteur. Le temps et l'identifiant sont des paramètres.
- `service.py` : `recevoir` (valide, écarte un robot ou un doublon, plafonne à
  30 demandes par heure, enregistre), `notifier` (prévient l'équipe, après la
  réponse) et `relancer` (tâches planifiées : réessaie les notifications
  ratées, trois essais, puis une erreur Sentry).
- `slack.py` : le webhook entrant, lu dans `AXELCOMPTA_SLACK_DEMANDES_WEBHOOK`.
- `repository.py`, `postgres.py`, `orm.py` : la table `demandes_echange`.

## Invariants

- **Une demande n'est jamais perdue pour une panne de Slack** : elle est
  enregistrée avant d'être notifiée.
- **Le webhook est un secret** : il n'est écrit ni en base, ni dans un journal,
  ni dans un message d'erreur. Seules les adresses `https://hooks.slack.com/`
  sont acceptées.
- **Le rôle web ne lit pas les demandes** : il en ajoute une, compte les
  demandes récentes (e-mail et date) et note le résultat de la notification.
  Les noms et les messages ne sont lus que par les tâches planifiées.
- **La RLS est activée explicitement par la migration**, avec une politique
  par droit pour le rôle web. Supabase l'active seul sur toute nouvelle table
  de `public` : sans politique, l'API ne pourrait plus rien écrire.
- Ce module ne dépend que de `core` (import-linter).

## Doc de référence

[AXE-949](https://linear.app/axel-project/issue/AXE-949), [doc 10](../../../docs/10-securite-rgpd.md)
(données personnelles), [textes juridiques](../../../docs/juridique/confidentialite.md).
