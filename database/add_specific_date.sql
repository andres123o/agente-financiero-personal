-- Ejecuta esto en Supabase SQL Editor (una sola vez)
-- Para recordatorios personalizados "recuérdame a las 4 tal cosa"

ALTER TABLE schedule_reminders ADD COLUMN IF NOT EXISTS specific_date DATE;

COMMENT ON COLUMN schedule_reminders.specific_date IS 'Si está definido, recordatorio único para esa fecha. Si es NULL, usa days_of_week (recurrente).';
