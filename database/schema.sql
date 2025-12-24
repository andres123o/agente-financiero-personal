-- Schema for Kepler CFO Supabase Database

-- Table: transactions
-- Stores all financial transactions (expenses and income)
CREATE TABLE IF NOT EXISTS transactions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  amount DECIMAL(10, 2) NOT NULL,
  category VARCHAR(50) NOT NULL,
  type VARCHAR(20) NOT NULL CHECK (type IN ('expense', 'income')),
  description TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table: budgets
-- Stores budget limits and current spending for each category
CREATE TABLE IF NOT EXISTS budgets (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  category VARCHAR(50) UNIQUE NOT NULL,
  monthly_limit DECIMAL(10, 2) NOT NULL,
  current_spent DECIMAL(10, 2) DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_budgets_category ON budgets(category);

-- Insert initial budget categories (adjust amounts according to your 40/40/20 budget)
-- Example values - UPDATE THESE WITH YOUR ACTUAL BUDGET LIMITS
INSERT INTO budgets (category, monthly_limit, current_spent) VALUES
  ('fixed_survival', 0, 0),
  ('debt_offensive', 0, 0),
  ('kepler_growth', 0, 0),
  ('networking_life', 0, 0),
  ('stupid_expenses', 0, 0)
ON CONFLICT (category) DO NOTHING;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
CREATE TRIGGER update_budgets_updated_at BEFORE UPDATE ON budgets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

