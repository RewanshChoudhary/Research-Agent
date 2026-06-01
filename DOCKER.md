# ResearchBuddy Docker Setup

## Start Everything

```bash
cp .env.example .env
# edit .env and set GROQ_API_KEY
docker compose up --build
```

Services:

- Frontend: http://localhost:3000
- Java API: http://localhost:8080
- Postgres: localhost:5432
- Redis: localhost:6379

## Stop

```bash
docker compose down
```

To remove database and Redis data too:

```bash
docker compose down -v
```
