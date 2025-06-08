# Quick test script for location detection
Import-Module "$HOME/.config/powershell/sync-utils.ps1"

function Get-TimeStamp { return "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]" }

Write-Host "🧪 Testing location detection..." -ForegroundColor Cyan

# Test 1: Ping local server
Write-Host "`n1️⃣ Testing ping to local server (192.168.68.61)..." -ForegroundColor Blue
$pingResult = Test-Connection -ComputerName "192.168.68.61" -Count 3 -Quiet
Write-Host "   Ping result: $pingResult" -ForegroundColor $(if ($pingResult) { "Green" } else { "Red" })

# Test 2: Test network share access
Write-Host "`n2️⃣ Testing network share access..." -ForegroundColor Blue
$shareResult = Test-Path "\\192.168.68.61\docker\appdata\mtg-flask-app\" -ErrorAction SilentlyContinue
Write-Host "   Share access: $shareResult" -ForegroundColor $(if ($shareResult) { "Green" } else { "Red" })

# Test 3: Test VPN connectivity
Write-Host "`n3️⃣ Testing VPN connectivity..." -ForegroundColor Blue
try {
    $plinkTest = plink -batch -agent -load "ext.julzandfew.com root" echo "VPN test successful" 2>&1
    $vpnResult = $LASTEXITCODE -eq 0
    Write-Host "   VPN result: $vpnResult" -ForegroundColor $(if ($vpnResult) { "Green" } else { "Red" })
    if ($vpnResult) {
        Write-Host "   VPN response: $plinkTest" -ForegroundColor Green
    } else {
        Write-Host "   VPN error: $plinkTest" -ForegroundColor Red
    }
} catch {
    Write-Host "   VPN error: $_" -ForegroundColor Red
    $vpnResult = $false
}

# Test 4: Use the actual location detection function
Write-Host "`n4️⃣ Testing location detection function..." -ForegroundColor Blue
$Global:IsAtHome = $null
$Global:LastLocationCheck = $null
$detectedLocation = Test-LocationStatus
Write-Host "   Detected location: $(if ($detectedLocation) { 'HOME' } else { 'AWAY' })" -ForegroundColor $(if ($detectedLocation) { "Green" } else { "Yellow" })

# Summary
Write-Host "`n📋 SUMMARY:" -ForegroundColor Magenta
Write-Host "   Local ping: $pingResult" -ForegroundColor $(if ($pingResult) { "Green" } else { "Red" })
Write-Host "   Local share: $shareResult" -ForegroundColor $(if ($shareResult) { "Green" } else { "Red" })
Write-Host "   VPN access: $vpnResult" -ForegroundColor $(if ($vpnResult) { "Green" } else { "Red" })
Write-Host "   Final mode: $(if ($detectedLocation) { 'HOME (local network)' } else { 'AWAY (VPN/remote)' })" -ForegroundColor $(if ($detectedLocation) { "Green" } else { "Yellow" })

if ($detectedLocation -and $shareResult) {
    Write-Host "`n✅ You're at home - local network sync will be used" -ForegroundColor Green
} elseif ($vpnResult) {
    Write-Host "`n🌐 You're away but VPN is working - remote sync will be used" -ForegroundColor Yellow
} else {
    Write-Host "`n❌ Neither local nor remote access is working - check your connections" -ForegroundColor Red
}