# Séparer le développement et la production

Propriétaire : équipe Plateforme.

1. Les agents et les développeurs travaillent sur une copie de la base de staging, jamais sur la production.
2. Aucune clé de production ne doit se trouver dans l'espace de travail d'un agent.
3. Les accès à la production passent par une demande approuvée par un humain et limitée dans le temps.
4. Les sauvegardes sont stockées sur un volume séparé de la base qu'elles protègent.
5. Une restauration de sauvegarde est testée chaque semaine et son résultat est consigné.
