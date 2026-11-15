# One-time server setup

Run once on a fresh Ubuntu server, as a user with sudo. Nothing here touches existing data.

```sh
# Docker with Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"     # log out and back in afterwards

# Firewall: SSH and HTTP only (section 12)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw enable
```

Then, from your own machine, in the repository: `deploy/deploy.sh user@server`.

Create an admin account once:

```sh
ssh user@server "cd flame_in_freefall && docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser"
```

Restore a backup (stops nothing else; replaces the database contents):

```sh
docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < backups/flame-YYYY-MM-DD.dump
```
