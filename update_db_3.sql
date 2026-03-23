-- Add missing columns for Chainlit 2.9.4+ compatibility
ALTER TABLE steps ADD COLUMN IF NOT EXISTS "modes" TEXT[];
