-- ============================================
-- PRUEBA RÁPIDA
-- 1. Reemplaza 123456789 con tu chat_id
-- 2. Reemplaza 14 y 45 con la hora y minuto del PRÓXIMO cuarto (:00, :15, :30, :45)
--    Ej: si ahora son 14:37 -> usa hour=14, minute=45
-- 3. Ejecuta. Luego espera ese momento o llama manualmente al endpoint.
-- ============================================

INSERT INTO schedule_reminders (chat_id, hour, minute, days_of_week, message, reminder_type)
VALUES (
  123456789,  -- TU CHAT_ID
  14,         -- hora (0-23)
  45,         -- minuto (0, 15, 30, o 45)
  '0,1,2,3,4,5,6',
  '🧪 PRUEBA - Si ves esto, los recordatorios funcionan!',
  'test'
);
