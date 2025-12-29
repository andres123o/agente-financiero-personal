# Script para configurar el webhook de Telegram
# Lee el token del archivo .env y configura el webhook

$envFile = ".env"
$webhookUrl = "https://agente-financiero-personal.vercel.app/api/webhook"

# Leer el token del archivo .env
if (Test-Path $envFile) {
    $content = Get-Content $envFile
    $token = $null
    
    foreach ($line in $content) {
        if ($line -match "^TELEGRAM_BOT_TOKEN=(.+)$") {
            $token = $matches[1].Trim()
            break
        }
    }
    
    if ($token) {
        Write-Host "Token encontrado. Configurando webhook..." -ForegroundColor Cyan
        Write-Host ""
        
        $setWebhookUrl = "https://api.telegram.org/bot$token/setWebhook?url=$webhookUrl"
        
        Write-Host "URL del webhook: $webhookUrl" -ForegroundColor Yellow
        Write-Host ""
        
        try {
            $response = Invoke-RestMethod -Uri $setWebhookUrl -Method Get
            if ($response.ok) {
                Write-Host "✅ Webhook configurado exitosamente!" -ForegroundColor Green
                Write-Host ""
                Write-Host "Información del webhook:" -ForegroundColor Cyan
                Write-Host ($response | ConvertTo-Json -Depth 3)
            } else {
                Write-Host "❌ Error: $($response.description)" -ForegroundColor Red
            }
        } catch {
            Write-Host "❌ Error al configurar webhook: $_" -ForegroundColor Red
        }
        
        Write-Host ""
        Write-Host "Verificando configuración..." -ForegroundColor Cyan
        $getWebhookUrl = "https://api.telegram.org/bot$token/getWebhookInfo"
        try {
            $info = Invoke-RestMethod -Uri $getWebhookUrl -Method Get
            Write-Host ($info | ConvertTo-Json -Depth 3)
        } catch {
            Write-Host "Error al verificar: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "❌ No se encontró TELEGRAM_BOT_TOKEN en el archivo .env" -ForegroundColor Red
    }
} else {
    Write-Host "❌ No se encontró el archivo .env" -ForegroundColor Red
}


