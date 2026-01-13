-- Tabla para almacenar pensamientos, recordatorios e ideas
CREATE TABLE IF NOT EXISTS thoughts_reminders (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  chat_id BIGINT NOT NULL,
  content TEXT NOT NULL,
  type VARCHAR(20) DEFAULT 'thought' CHECK (type IN ('thought', 'reminder', 'idea', 'note')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  reminder_date DATE, -- Fecha específica para recordatorios (opcional)
  is_completed BOOLEAN DEFAULT FALSE -- Para marcar recordatorios como completados
);

-- Índices para búsquedas eficientes
CREATE INDEX IF NOT EXISTS idx_thoughts_chat_id ON thoughts_reminders(chat_id);
CREATE INDEX IF NOT EXISTS idx_thoughts_created_at ON thoughts_reminders(chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_thoughts_date ON thoughts_reminders(reminder_date) WHERE reminder_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_thoughts_type ON thoughts_reminders(type);

-- RLS (Row Level Security)
ALTER TABLE thoughts_reminders ENABLE ROW LEVEL SECURITY;

-- Política para permitir todas las operaciones (con API key)
DROP POLICY IF EXISTS "Allow all operations on thoughts_reminders" ON thoughts_reminders;
CREATE POLICY "Allow all operations on thoughts_reminders" ON thoughts_reminders
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Comentarios en la tabla para documentación
COMMENT ON TABLE thoughts_reminders IS 'Almacena pensamientos, recordatorios, ideas y notas del usuario';
COMMENT ON COLUMN thoughts_reminders.content IS 'Contenido del pensamiento, recordatorio o idea';
COMMENT ON COLUMN thoughts_reminders.type IS 'Tipo: thought (pensamiento), reminder (recordatorio), idea (idea), note (nota)';
COMMENT ON COLUMN thoughts_reminders.reminder_date IS 'Fecha específica para recordatorios (opcional, solo para recordatorios)';
COMMENT ON COLUMN thoughts_reminders.is_completed IS 'Indica si un recordatorio está completado';

