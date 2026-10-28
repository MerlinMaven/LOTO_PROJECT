# Infrastructure status

The supported local setup uses two native FastAPI processes sharing SQLite and a
Vite development server. Follow [LAUNCH.md](../LAUNCH.md).

`docker-compose.yml` and `supabase/migrations/001_initial.sql` are retained historical
deployment references. The Compose file assumes an authoring Dockerfile that is not
present, PostgreSQL/driver configuration outside the supported SQLite quick start,
and an older Supabase/YOLO arrangement. It is not a tested production deployment or
a copy-paste alternative to the native setup.

Do not apply the historical SQL or run database-reset helpers against operational
data as part of repository preparation. Runtime infrastructure and database schemas
were intentionally preserved by this release-cleanup task.
