# Deploying the backend to an Oracle Cloud Always Free VM

1. Create an Ubuntu 24.04 Ampere (A1) instance, open TCP 80 and 443 in the subnet's
   Security List, and run on the VM:
   `sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT && sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT && sudo netfilter-persistent save`
2. Install Docker: `curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker ubuntu` (re-login).
3. Point a hostname (e.g. a free duckdns.org subdomain) at the VM's public IP.
4. `git clone <repo> && cd <repo>`
5. `cp backend/.env.example backend/.env` and fill it in (same values as Render, but set
   `FRONTEND_URL` to the Vercel URL). Leave STORAGE_PATH/CHROMA_PATH/HF_HOME blank — the
   Dockerfile sets them.
6. `echo "DOMAIN=your-subdomain.duckdns.org" > deploy/.env`
7. `docker compose -f deploy/docker-compose.prod.yml up -d --build`
8. In Vercel set `NEXT_PUBLIC_API_URL=https://your-subdomain.duckdns.org` and redeploy.

Update later with `./deploy/update.sh`. Logs: `docker compose -f deploy/docker-compose.prod.yml logs -f backend`.
