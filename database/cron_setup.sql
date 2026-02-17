-- ============================================
-- CONFIGURACIÓN pg_cron + pg_net PARA RECORDATORIOS
-- Ejecutar en Supabase SQL Editor
-- ============================================

-- 1. Habilitar extensiones (solo una vez)
CREATE EXTENSION IF NOT EXISTS pg_cron;
CREATE EXTENSION IF NOT EXISTS pg_net;

-- 2. Eliminar cron anterior si existe (para reconfigurar)
SELECT cron.unschedule('kepler-reminders');

-- 3. Programar llamada cada 15 minutos
-- REEMPLAZA TU_URL_VERCEL con tu URL real (ej: https://agente-financiero.vercel.app)
-- Si usas CRON_SECRET, añade: /api/cron/reminders?secret=TU_SECRETO

SELECT cron.schedule(
  'kepler-reminders',
  '*/15 * * * *',
  $$
  SELECT net.http_post(
    url := 'TU_URL_VERCEL/api/cron/reminders'
  ) AS request_id;
  $$
);

-- Verificar que quedó programado:
SELECT * FROM cron.job;
