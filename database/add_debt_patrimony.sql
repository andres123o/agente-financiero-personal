-- Tablas para control de Deuda y Patrimonio
-- Ejecuta esto completo en Supabase SQL Editor

-- ============================================
-- 1. TABLA: debts (Control de Deudas)
-- ============================================
CREATE TABLE IF NOT EXISTS debts (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name VARCHAR(50) UNIQUE NOT NULL, -- 'Lumni' o 'ICETEX'
  initial_balance DECIMAL(12, 2) NOT NULL, -- Saldo inicial de la deuda
  current_balance DECIMAL(12, 2) NOT NULL, -- Saldo actual (se actualiza con pagos)
  minimum_payment DECIMAL(10, 2) NOT NULL, -- Cuota mínima mensual
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insertar deudas iniciales
INSERT INTO debts (name, initial_balance, current_balance, minimum_payment) VALUES
  ('ICETEX', 20000000.00, 20000000.00, 565000.00),
  ('Lumni', 10000000.00, 10000000.00, 546000.00)
ON CONFLICT (name) DO UPDATE SET
  initial_balance = EXCLUDED.initial_balance,
  current_balance = EXCLUDED.current_balance,
  minimum_payment = EXCLUDED.minimum_payment;

-- ============================================
-- 2. TABLA: patrimony (Control de Patrimonio)
-- ============================================
CREATE TABLE IF NOT EXISTS patrimony (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  initial_balance DECIMAL(12, 2) NOT NULL DEFAULT 0, -- Saldo inicial del patrimonio
  current_balance DECIMAL(12, 2) NOT NULL DEFAULT 0, -- Patrimonio actual acumulado
  last_month_income DECIMAL(12, 2) DEFAULT 0, -- Último ingreso mensual registrado
  last_month_expenses DECIMAL(12, 2) DEFAULT 0, -- Últimos gastos mensuales
  last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insertar patrimonio inicial (solo si no existe)
INSERT INTO patrimony (id, initial_balance, current_balance)
SELECT 
  gen_random_uuid(),
  5237916.00,
  5237916.00
WHERE NOT EXISTS (SELECT 1 FROM patrimony);

-- Si ya existe, actualizar el saldo inicial pero mantener el current_balance si es mayor
UPDATE patrimony 
SET initial_balance = 5237916.00
WHERE current_balance < 5237916.00;

-- ============================================
-- 3. ÍNDICES para mejor rendimiento
-- ============================================
CREATE INDEX IF NOT EXISTS idx_debts_name ON debts(name);
CREATE INDEX IF NOT EXISTS idx_debts_current_balance ON debts(current_balance);

-- ============================================
-- 4. FUNCIONES y TRIGGERS
-- ============================================

-- Función para actualizar updated_at en debts
CREATE OR REPLACE FUNCTION update_debts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para debts
DROP TRIGGER IF EXISTS update_debts_updated_at ON debts;
CREATE TRIGGER update_debts_updated_at 
    BEFORE UPDATE ON debts
    FOR EACH ROW 
    EXECUTE FUNCTION update_debts_updated_at();

-- Función para actualizar last_updated en patrimony
CREATE OR REPLACE FUNCTION update_patrimony_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para patrimony
DROP TRIGGER IF EXISTS update_patrimony_last_updated ON patrimony;
CREATE TRIGGER update_patrimony_last_updated 
    BEFORE UPDATE ON patrimony
    FOR EACH ROW 
    EXECUTE FUNCTION update_patrimony_last_updated();

-- ============================================
-- 5. ROW LEVEL SECURITY (RLS)
-- ============================================

-- Habilitar RLS en debts
ALTER TABLE debts ENABLE ROW LEVEL SECURITY;

-- Eliminar políticas existentes si las hay
DROP POLICY IF EXISTS "Allow all operations on debts" ON debts;

-- Crear política que permite todas las operaciones (con API key)
CREATE POLICY "Allow all operations on debts" ON debts
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Habilitar RLS en patrimony
ALTER TABLE patrimony ENABLE ROW LEVEL SECURITY;

-- Eliminar políticas existentes si las hay
DROP POLICY IF EXISTS "Allow all operations on patrimony" ON patrimony;

-- Crear política que permite todas las operaciones (con API key)
CREATE POLICY "Allow all operations on patrimony" ON patrimony
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================
-- 6. VERIFICACIÓN
-- ============================================

-- Verificar que las tablas se crearon correctamente
SELECT 'debts table' as table_name, COUNT(*) as row_count FROM debts
UNION ALL
SELECT 'patrimony table', COUNT(*) FROM patrimony;

-- Mostrar datos iniciales
SELECT * FROM debts;
SELECT * FROM patrimony;


