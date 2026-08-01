-- ============================================================
-- Blindaje del usuario copilot_reader
-- Ejecutar como administrador del servidor (no como copilot_reader).
-- ============================================================

-- 1) Rotar la password (IMPORTANTE: usar la MISMA que pusiste en .env).
ALTER USER copilot_reader WITH PASSWORD 'REEMPLAZA_CON_LA_PASSWORD_NUEVA';

-- 2) Quitarle todo y devolverle solo lectura.
REVOKE ALL ON SCHEMA public FROM copilot_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM copilot_reader;
REVOKE CREATE ON SCHEMA public FROM copilot_reader;
REVOKE ALL ON DATABASE postgres FROM copilot_reader;

GRANT CONNECT ON DATABASE postgres TO copilot_reader;
GRANT USAGE ON SCHEMA public TO copilot_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO copilot_reader;

-- Que tambien aplique a tablas creadas en el futuro.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO copilot_reader;

-- 3) Limites a nivel de rol: segunda red de contencion.
ALTER ROLE copilot_reader SET statement_timeout = '15s';
ALTER ROLE copilot_reader SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE copilot_reader SET default_transaction_read_only = on;
ALTER ROLE copilot_reader CONNECTION LIMIT 10;

-- 4) Verificar que quedo bien.
SELECT has_table_privilege('copilot_reader', 'public.TU_TABLA', 'INSERT') AS puede_insertar,
       has_table_privilege('copilot_reader', 'public.TU_TABLA', 'UPDATE') AS puede_actualizar,
       has_table_privilege('copilot_reader', 'public.TU_TABLA', 'DELETE') AS puede_borrar,
       has_table_privilege('copilot_reader', 'public.TU_TABLA', 'SELECT') AS puede_leer;
