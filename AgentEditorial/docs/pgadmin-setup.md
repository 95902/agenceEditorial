# Configuration pgAdmin

Guide pour configurer pgAdmin et se connecter à PostgreSQL.

## Accès à pgAdmin

1. Ouvrez votre navigateur : http://localhost:5050
2. Connectez-vous avec :
   - **Email** : `admin@editorial.dev`
   - **Password** : `admin`

## Configuration de la connexion PostgreSQL

Après vous être connecté à pgAdmin, vous devez ajouter le serveur PostgreSQL :

### Étape 1 : Ajouter un nouveau serveur

1. Clic droit sur **"Servers"** dans le panneau de gauche
2. Sélectionnez **"Register"** → **"Server..."**

### Étape 2 : Onglet "General"

- **Name** : `Editorial DB` (ou tout autre nom de votre choix)

### Étape 3 : Onglet "Connection"

Remplissez les champs suivants :

- **Host name/address** : `postgres` ⚠️ **Important** : Utilisez le nom du service Docker, pas `localhost`
- **Port** : `5432`
- **Maintenance database** : `editorial_db`
- **Username** : `editorial_user`
- **Password** : La valeur de `POSTGRES_PASSWORD` dans votre fichier `.env` (par défaut : `change_me_strong_password`)

### Étape 4 : Onglet "Advanced" (optionnel)

- **DB restriction** : Vous pouvez laisser vide ou spécifier `editorial_db` pour ne voir que cette base

### Étape 5 : Sauvegarder

Cliquez sur **"Save"** pour enregistrer la connexion.

## Vérification

Une fois connecté, vous devriez voir :
- La base de données `editorial_db` dans le panneau de gauche
- Les tables : `site_profiles`, `workflow_executions`, `site_analysis_results`, etc.

## Notes importantes

⚠️ **Host name** : Utilisez toujours `postgres` (nom du service Docker) et **PAS** `localhost` car pgAdmin s'exécute dans le même réseau Docker que PostgreSQL.

Si vous utilisez `localhost`, la connexion échouera car pgAdmin cherchera PostgreSQL sur sa propre machine, pas dans le conteneur Docker.

## Dépannage

### Erreur : "database does not exist"

Si vous voyez l'erreur `database "editorial_user" does not exist` dans les logs, c'est normal. pgAdmin essaie de se connecter automatiquement avant que vous ayez configuré la connexion. Configurez manuellement la connexion comme décrit ci-dessus.

### Erreur : "could not connect to server"

Vérifiez que :
1. Le conteneur PostgreSQL est en cours d'exécution : `docker compose -f docker/docker-compose.yml ps`
2. Vous utilisez `postgres` comme host name (pas `localhost`)
3. Le port est `5432`
4. Les identifiants correspondent à ceux dans votre `.env`

### Réinitialiser pgAdmin

Si vous avez des problèmes, vous pouvez réinitialiser pgAdmin :

```bash
# Arrêter les services
docker compose -f docker/docker-compose.yml down

# Supprimer le volume pgAdmin (⚠️ supprime toutes les configurations)
docker volume rm docker_pgadmin_data

# Redémarrer
docker compose -f docker/docker-compose.yml up -d
```

