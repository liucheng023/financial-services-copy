# Supabase Migrations

Source of truth for the FinAgentOS Postgres schema. Files are applied in
filename order.

## Naming

`NNNN_description.sql` where `NNNN` is a zero-padded 4-digit sequence.

## How to apply

### Local validation (no Supabase project needed)

```bash
docker run --rm -d --name finagent-pg-test \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=finagent_test \
  postgres:16-alpine
sleep 3
docker exec -i finagent-pg-test psql -U postgres -d finagent_test \
  -v ON_ERROR_STOP=1 --no-psqlrc < 0001_initial_schema.sql
docker exec finagent-pg-test psql -U postgres -d finagent_test --no-psqlrc -c "\dt"
docker stop finagent-pg-test
```

### Real Supabase project (when credentials are available)

```bash
# Supabase CLI
supabase db push

# Or psql directly
psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f 0001_initial_schema.sql
```

## Migrations

| File | Description |
|------|-------------|
| `0001_initial_schema.sql` | Phase 1 schema: agents, skills, verticals, mcp_servers, association tables, chat_sessions/messages, model_configs |
