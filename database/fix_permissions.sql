-- Script para corregir permisos en Supabase
-- Ejecuta esto en el SQL Editor de Supabase si tienes problemas con RLS

-- 1. Verificar si RLS está habilitado
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('transactions', 'budgets');

-- 2. Deshabilitar RLS temporalmente para desarrollo (OPCIONAL - solo si es necesario)
-- ALTER TABLE transactions DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE budgets DISABLE ROW LEVEL SECURITY;

-- 3. O crear políticas que permitan todas las operaciones (RECOMENDADO)
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

-- 4. Habilitar RLS si no está habilitado
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;

-- 5. Verificar que las tablas existen y tienen la estructura correcta
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name = 'transactions'
ORDER BY ordinal_position;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name = 'budgets'
ORDER BY ordinal_position;

