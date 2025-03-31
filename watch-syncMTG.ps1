$LocalFrontend = "C:\Users\jules\Desktop\Jules\Github\mtg_optimizer\frontend"
$LocalBackend  = "C:\Users\jules\Desktop\Jules\Github\mtg_optimizer\backend"
$FrontendSrc   = Join-Path $LocalFrontend "src"

$syncCooldownMs = 1000
$syncScheduled = $false
$buildScheduled = $false

function Run-Build-And-Sync {
    if (-not $syncScheduled) {
        $syncScheduled = $true
        Write-Host "📝 Detected change. Building and syncing in $syncCooldownMs ms..."
        Start-Sleep -Milliseconds $syncCooldownMs

        try {
            Write-Host "⚙️  Running npm build..."
            Push-Location $LocalFrontend
            npm run build | Out-Null
            Pop-Location
        } catch {
            Write-Host "❌ npm build failed: $_" -ForegroundColor Red
        }

        try {
            Write-Host "🔄 Running syncMTG..."
            syncMTG
        } catch {
            Write-Host "❌ syncMTG failed: $_" -ForegroundColor Red
        }

        $syncScheduled = $false
    }
}

function Run-Sync-Only {
    if (-not $syncScheduled) {
        $syncScheduled = $true
        Write-Host "📝 Backend change detected. Syncing in $syncCooldownMs ms..."
        Start-Sleep -Milliseconds $syncCooldownMs

        try {
            Write-Host "🔄 Running syncMTG..."
            syncMTG
        } catch {
            Write-Host "❌ syncMTG failed: $_" -ForegroundColor Red
        }

        $syncScheduled = $false
    }
}

# === Watchers ===
$frontendWatcher = New-Object System.IO.FileSystemWatcher $FrontendSrc -Property @{
    IncludeSubdirectories = $true
    NotifyFilter = [System.IO.NotifyFilters]'LastWrite, FileName, DirectoryName, Size'
}
$backendWatcher = New-Object System.IO.FileSystemWatcher $LocalBackend -Property @{
    IncludeSubdirectories = $true
    NotifyFilter = [System.IO.NotifyFilters]'LastWrite, FileName, DirectoryName, Size'
}

$frontendWatcher.EnableRaisingEvents = $true
$backendWatcher.EnableRaisingEvents = $true

# === Frontend (src/) triggers build + sync ===
$frontendEvents = @('Changed', 'Created', 'Renamed', 'Deleted')
foreach ($eventType in $frontendEvents) {
    Register-ObjectEvent $frontendWatcher $eventType -Action {
        Write-Host "🔧 Frontend SRC $($eventType.ToUpper()): $($Event.SourceEventArgs.FullPath)"
        Run-Build-And-Sync
    } | Out-Null
}

# === Backend triggers sync only ===
$backendEvents = @('Changed', 'Created', 'Renamed', 'Deleted')
foreach ($eventType in $backendEvents) {
    Register-ObjectEvent $backendWatcher $eventType -Action {
        Write-Host "🛠️ Backend $($eventType.ToUpper()): $($Event.SourceEventArgs.FullPath)"
        Run-Sync-Only
    } | Out-Null
}

Write-Host "👀 Watching frontend/src for build triggers, and backend for sync triggers..."

# Keep session alive
while ($true) {
    Start-Sleep -Seconds 1
}
