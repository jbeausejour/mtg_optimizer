# ------------------------------
# sync-watch.ps1 (Modular Refactor)
# ------------------------------

param (
    [switch]$ForceRecreate,
    [switch]$UseWatcher
)

Import-Module "$HOME/.config/powershell/sync-utils.ps1"

# Define missing variables for Docker commands
$CommandToRun = "sudo docker-compose --profile all -f /volume1/docker/dc-t3.yml "
$ParamUp = "up -d "
$ParamRec = "up -d --force-recreate "
$ParamBuild = "build --no-cache "
$BackendApp = "mtg-flask-app mtg-celery-beat mtg-celery-worker-main mtg-celery-worker-crystal-1 mtg-celery-worker-crystal-2 mtg-celery-worker-shopify mtg-celery-worker-other"
$FrontendApp = "mtg-frontend"

$LastChangeTime = @{ "FrontendLastBuild" = Get-Date; "BackendLastSync" = Get-Date }
$processedFiles = @{}
$syncInProgress = $false
$cooldown = 10
$buildCooldown = 30
$cleanupCounter = 0

function Get-TimeStamp { return "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]" }

function Run-SshCommand($Command) {
    try {
        Write-Host "$(Get-TimeStamp) 🖥️ SSH: $Command" -ForegroundColor Magenta
        $plink = "plink -batch -agent -load `"ext.julzandfew.com root`" bash -l -c `"$Command`""
        Invoke-Expression $plink | Out-Host
        return $true
    } catch {
        Write-Host "$(Get-TimeStamp) ❌ SSH failed: $_" -ForegroundColor Red
        return $false
    }
}

function Is-DependencyFile($FilePath) {
    return $FilePath -match 'package\.json$|package-lock\.json$|requirements\.txt$|Dockerfile$|\.env$'
}

function Process-Change($type, $path, $isDependency) {
    if ($syncInProgress) {
        Write-Host "$(Get-TimeStamp) ⏳ Sync in progress, skipping..." -ForegroundColor Yellow
        return
    }
    $syncInProgress = $true
    try {
        Write-Host "$(Get-TimeStamp) 🔄 Change in ${type}: $path" -ForegroundColor Cyan
        if ($type -eq 'frontend') {
            Write-Host "$(Get-TimeStamp) 🔄 Starting frontend sync..." -ForegroundColor Blue
            $syncResult = SyncFrontendOnly
            Write-Host "$(Get-TimeStamp) 🔄 Frontend sync result: $syncResult" -ForegroundColor Blue
            if (-not $syncResult) { 
                Write-Host "$(Get-TimeStamp) ❌ Frontend sync failed, aborting" -ForegroundColor Red
                return 
            }
            Start-Sleep -Seconds 2
            if ($isDependency) {
                Write-Host "$(Get-TimeStamp) 🏗️ Dependency file detected, rebuilding..." -ForegroundColor Blue
                Run-SshCommand "$CommandToRun$ParamBuild$FrontendApp"
                Run-SshCommand "$CommandToRun$ParamUp$FrontendApp"
            }
            $LastChangeTime["FrontendLastBuild"] = Get-Date
        } else {
            Write-Host "$(Get-TimeStamp) 🔄 Starting backend sync..." -ForegroundColor Blue
            $syncResult = SyncBackendOnly
            Write-Host "$(Get-TimeStamp) 🔄 Backend sync result: $syncResult" -ForegroundColor Blue
            if (-not $syncResult) { 
                Write-Host "$(Get-TimeStamp) ❌ Backend sync failed, aborting" -ForegroundColor Red
                return 
            }
            Start-Sleep -Seconds 2
            $cmd = $ForceRecreate ? $ParamRec : $ParamUp
            Write-Host "$(Get-TimeStamp) 🐳 Running Docker command: $CommandToRun$cmd$BackendApp" -ForegroundColor Blue
            Run-SshCommand "$CommandToRun$cmd$BackendApp"
            $LastChangeTime["BackendLastSync"] = Get-Date
        }
        Write-Host "$(Get-TimeStamp) ✅ Process completed successfully" -ForegroundColor Green
    } finally {
        $syncInProgress = $false
    }
}

function Check-Changes($dir, $lastKey, $ignorePattern) {
    $since = (Get-Date) - $LastChangeTime[$lastKey]
    if ($since.TotalSeconds -lt $cooldown) { return $null }

    $files = Get-ChildItem -Recurse -Path $dir -File |
        Where-Object { $_.LastWriteTime -gt $LastChangeTime[$lastKey] -and $_.FullName -notmatch $ignorePattern }
    if ($files.Count -eq 0) { return $null }

    $file = $files | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $isDep = Is-DependencyFile $file.FullName
    $cool = $isDep ? $buildCooldown : $cooldown

    if ($processedFiles[$file.FullName] -and ((Get-Date) - $processedFiles[$file.FullName]).TotalSeconds -lt $cool) {
        return $null
    }

    $processedFiles[$file.FullName] = Get-Date
    return @{ File = $file; IsDependency = $isDep }
}

function Cleanup-ProcessedFiles {
    $now = Get-Date
    $processedFiles.Keys | Where-Object { ($now - $processedFiles[$_]).TotalMinutes -gt 10 } | ForEach-Object { $processedFiles.Remove($_) }
}
Write-Host "👀 Watching frontend and backend for changes..." -ForegroundColor Cyan

# Test location status at startup
$startupLocation = Test-LocationStatus
$locationText = if ($startupLocation) { "HOME (local network)" } else { "AWAY (VPN/remote)" }
Write-Host "📍 Current location: $locationText" -ForegroundColor Magenta

if ($UseWatcher) {
    # Debug: Show the paths being watched
    Write-Host "Frontend path: $LocalFrontend" -ForegroundColor Yellow
    Write-Host "Backend path: $LocalBackend" -ForegroundColor Yellow
    
    # Remove trailing slashes for FileSystemWatcher
    $frontendPath = $LocalFrontend.TrimEnd('\')
    $backendPath = $LocalBackend.TrimEnd('\')
    
    Write-Host "Watching Frontend: $frontendPath" -ForegroundColor Yellow
    Write-Host "Watching Backend: $backendPath" -ForegroundColor Yellow
    
    # Check if directories exist
    if (-not (Test-Path $frontendPath)) {
        Write-Host "❌ Frontend path does not exist: $frontendPath" -ForegroundColor Red
        return
    }
    if (-not (Test-Path $backendPath)) {
        Write-Host "❌ Backend path does not exist: $backendPath" -ForegroundColor Red
        return
    }
    
    # Clean up any existing event subscriptions and jobs
    Write-Host "🧹 Cleaning up existing event subscriptions..." -ForegroundColor Blue
    Get-EventSubscriber | Unregister-Event -ErrorAction SilentlyContinue
    Get-Job | Remove-Job -Force -ErrorAction SilentlyContinue
    
    # Create shared variables for communication between event handlers and main loop
    $Global:PendingChanges = @()
    $Global:ChangeLock = $false
    
    # Create FileSystemWatcher objects
    try {
        $watcherF = New-Object IO.FileSystemWatcher $frontendPath
        $watcherF.IncludeSubdirectories = $true
        $watcherF.EnableRaisingEvents = $true
        
        $watcherB = New-Object IO.FileSystemWatcher $backendPath
        $watcherB.IncludeSubdirectories = $true
        $watcherB.EnableRaisingEvents = $true

        Write-Host "✅ Watchers created successfully" -ForegroundColor Green
    } catch {
        Write-Host "❌ Failed to create watchers: $_" -ForegroundColor Red
        return
    }

    # Simple event handlers that just queue changes
    Register-ObjectEvent $watcherF Changed -Action {
        $fp = $Event.SourceEventArgs.FullPath
        Write-Host "🔍 Frontend file changed: $fp" -ForegroundColor Cyan
        if (-not $Global:ChangeLock) {
            $Global:PendingChanges += @{
                Type = 'frontend'
                Path = $fp
                Time = Get-Date
            }
        }
    } | Out-Null
    
    Register-ObjectEvent $watcherB Changed -Action {
        $fp = $Event.SourceEventArgs.FullPath
        Write-Host "🔍 Backend file changed: $fp" -ForegroundColor Yellow
        if (-not $Global:ChangeLock) {
            $Global:PendingChanges += @{
                Type = 'backend'
                Path = $fp
                Time = Get-Date
            }
        }
    } | Out-Null

    Write-Host "🔔 FileSystemWatcher is running. Press Ctrl+C to stop..." -ForegroundColor Green
    Write-Host "💡 Try changing a file now..." -ForegroundColor Blue
    
    # Main processing loop
    while ($true) {
        if ($Global:PendingChanges.Count -gt 0 -and -not $Global:ChangeLock) {
            $Global:ChangeLock = $true
            
            # Get the most recent change
            $change = $Global:PendingChanges | Sort-Object Time -Descending | Select-Object -First 1
            $Global:PendingChanges = @()  # Clear pending changes
            
            # Process the change
            $isDep = Is-DependencyFile $change.Path
            Process-Change $change.Type $change.Path $isDep
            
            $Global:ChangeLock = $false
        }
        Start-Sleep -Milliseconds 500
    }
    
} else {
    while ($true) {
        $fc = Check-Changes $LocalFrontend "FrontendLastBuild" "node_modules|\.git"
        if ($fc) { Process-Change 'frontend' $fc.File.FullName $fc.IsDependency }

        $bc = Check-Changes $LocalBackend "BackendLastSync" "__pycache__|\.git|venv"
        if ($bc) { Process-Change 'backend' $bc.File.FullName $bc.IsDependency }

        if (++$cleanupCounter -ge 600) { Cleanup-ProcessedFiles; $cleanupCounter = 0 }
        Start-Sleep -Milliseconds 500
    }
}