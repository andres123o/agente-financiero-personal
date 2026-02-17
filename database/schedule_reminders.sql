-- Tabla para recordatorios proactivos según el horario del Plan Kepler
-- Los recordatorios se envían automáticamente por Telegram a la hora indicada

CREATE TABLE IF NOT EXISTS schedule_reminders (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  chat_id BIGINT NOT NULL,
  hour SMALLINT NOT NULL CHECK (hour >= 0 AND hour <= 23),
  minute SMALLINT NOT NULL CHECK (minute >= 0 AND minute <= 59),
  days_of_week VARCHAR(20) NOT NULL,  -- '0,1,2,3,4' = L-V, '5' = Sábado, '6' = Domingo, '0,1,2,3,4,5,6' = todos
  message TEXT NOT NULL,
  reminder_type VARCHAR(50),  -- 'wake_up', 'bloque_rojo', 'exercise', 'reading', etc.
  last_sent_date DATE,       -- Para no enviar dos veces el mismo día
  enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_schedule_reminders_chat_enabled ON schedule_reminders(chat_id, enabled);
CREATE INDEX IF NOT EXISTS idx_schedule_reminders_time ON schedule_reminders(hour, minute);

-- RLS
ALTER TABLE schedule_reminders ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow all operations on schedule_reminders" ON schedule_reminders;
CREATE POLICY "Allow all operations on schedule_reminders" ON schedule_reminders
    FOR ALL USING (true) WITH CHECK (true);

COMMENT ON TABLE schedule_reminders IS 'Recordatorios proactivos enviados por horario según Plan Kepler';

-- NO ejecutes INSERT manual. Di "activar recordatorios" al bot en Telegram
-- y se insertarán automáticamente para tu chat_id.
