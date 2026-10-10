# Rotation d'une clé exposée

Propriétaire : équipe Données. Déclencheur : une clé a été lue, utilisée ou publiée hors de son usage prévu.

1. Révoquer immédiatement la clé exposée dans le gestionnaire de secrets ou la console du fournisseur.
2. Émettre une nouvelle clé limitée à l'usage prévu, en lecture seule si possible, avec une durée de vie courte.
3. Mettre à jour les services qui utilisaient l'ancienne clé, puis vérifier qu'ils fonctionnent.
4. Retirer le secret de tous les fichiers du dépôt et de l'espace de travail des agents, y compris les fichiers .env.
5. Consulter les journaux d'utilisation de l'ancienne clé pour repérer tout usage anormal depuis son exposition.
6. Consigner l'incident, la date de révocation et le nom de la nouvelle clé dans le registre des secrets.
