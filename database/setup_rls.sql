-- Configuración de RLS para Kepler CFO
-- Ejecuta esto completo en el SQL Editor de Supabase

-- 1. Habilitar RLS en las tablas
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;

-- 2. Eliminar políticas existentes si las hay (opcional, para empezar limpio)
DROP POLICY IF EXISTS "Allow insert transactions" ON transactions;
DROP POLICY IF EXISTS "Allow select transactions" ON transactions;
DROP POLICY IF EXISTS "Allow select budgets" ON budgets;
DROP POLICY IF EXISTS "Allow update budgets" ON budgets;

-- 3. Crear políticas que permitan todas las operaciones necesarias

-- Política para INSERT en transactions (permite insertar a cualquiera con la API key)
CREATE POLICY "Allow insert transactions" ON transactions
    FOR INSERT
    WITH CHECK (true);

-- Política para SELECT en transactions
CREATE POLICY "Allow select transactions" ON transactions
    FOR SELECT
    USING (true);

-- Política para SELECT en budgets
CREATE POLICY "Allow select budgets" ON budgets
    FOR SELECT
    USING (true);

-- Política para UPDATE en budgets
CREATE POLICY "Allow update budgets" ON budgets
    FOR UPDATE
    USING (true)
    WITH CHECK (true);

-- 4. Verificar que las políticas se crearon
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE tablename IN ('transactions', 'budgets');

