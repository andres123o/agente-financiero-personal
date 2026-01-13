-- Tabla para almacenar historial de conversaciones
CREATE TABLE IF NOT EXISTS conversation_history (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  chat_id BIGINT NOT NULL,
  role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
  message TEXT NOT NULL,
  intent VARCHAR(20), -- 'FINANCE' o 'MENTORSHIP'
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para búsquedas eficientes
CREATE INDEX IF NOT EXISTS idx_conversation_chat_id ON conversation_history(chat_id);
CREATE INDEX IF NOT EXISTS idx_conversation_created_at ON conversation_history(chat_id, created_at DESC);

-- RLS (Row Level Security)
ALTER TABLE conversation_history ENABLE ROW LEVEL SECURITY;

-- Política para permitir todas las operaciones (con API key)
DROP POLICY IF EXISTS "Allow all operations on conversation_history" ON conversation_history;
CREATE POLICY "Allow all operations on conversation_history" ON conversation_history
    FOR ALL
    USING (true)
    WITH CHECK (true);

