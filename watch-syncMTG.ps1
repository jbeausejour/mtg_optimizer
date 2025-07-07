# ------------------------------
# sync-watch.ps1 (Modular Refactor)# ------------------------------

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
$BackendApp = "mtg-flask-app mtg-celery-beat mtg-celery-worker-main mtg-celery-worker-crystal-1 mtg-celery-worker-crystal-2 mtg-celery-worker-shopify mtg-celery-worker-other "
$FrontendApp = "mtg-frontend"
$RootRequirements = "$MTGLocalProjectFolder\\requirements.txt"
$PLinkLocalSession = "192.168.68.61 root"
$PLinkRemoteSession = "ext.julzandfew.com root"

$LastChangeTime = @{ "FrontendLastBuild" = Get-Date; "BackendLastSync" = Get-Date }
$processedFiles = @{}
$syncInProgress = $false
$cooldown = 10
$buildCooldown = 30
$cleanupCounter = 0

function Get-TimeStamp { return "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]" }

function Run-SshCommand($Command, $TimeoutMinutes = 30) {
    $session = if ($startupLocation) { $PLinkLocalSession } else { $PLinkRemoteSession }
    try {
        Write-Host "$(Get-TimeStamp) 🚀 SSH Command: $Command" -ForegroundColor Cyan
        Write-Host "$(Get-TimeStamp) ⏱️  Timeout: $TimeoutMinutes minutes | Press Ctrl+C to cancel" -ForegroundColor Yellow

        # Add PATH explicitly before the command
        $commandWithPath = "export PATH=`$PATH:/usr/local/bin:/usr/bin; $Command"
        
        Write-Host "$(Get-TimeStamp) 🖥️  Starting real-time execution..." -ForegroundColor DarkGray
        Write-Host "$(Get-TimeStamp) 📺 Real-time output:" -ForegroundColor Green
        Write-Host "----------------------------------------" -ForegroundColor DarkGray

        # Create the plink process with real-time output
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "plink"
        $psi.Arguments = "-batch -agent -load `"$session`" -no-antispoof `"$commandWithPath`""
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true

        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $psi

        # Event handlers for real-time output
        $outputAction = {
            if (-not [string]::IsNullOrEmpty($Event.SourceEventArgs.Data)) {
                $timestamp = Get-Date -Format 'HH:mm:ss'
                Write-Host "[$timestamp] 📤 $($Event.SourceEventArgs.Data)" -ForegroundColor Cyan
            }
        }

        $errorAction = {
            if (-not [string]::IsNullOrEmpty($Event.SourceEventArgs.Data)) {
                $timestamp = Get-Date -Format 'HH:mm:ss'
                Write-Host "[$timestamp] ⚠️  $($Event.SourceEventArgs.Data)" -ForegroundColor Yellow
            }
        }

        # Register event handlers
        Register-ObjectEvent -InputObject $process -EventName OutputDataReceived -Action $outputAction | Out-Null
        Register-ObjectEvent -InputObject $process -EventName ErrorDataReceived -Action $errorAction | Out-Null

        # Start the process
        $process.Start() | Out-Null
        $process.BeginOutputReadLine()
        $process.BeginErrorReadLine()

        # Wait with timeout
        $timeoutMs = $TimeoutMinutes * 60 * 1000
        $completed = $process.WaitForExit($timeoutMs)

        if (-not $completed) {
            Write-Host "$(Get-TimeStamp) ⏰ Command timed out after $TimeoutMinutes minutes" -ForegroundColor Red
            $process.Kill()
            $exitCode = -1
        } else {
            $exitCode = $process.ExitCode
        }

        # Clean up event handlers
        Get-EventSubscriber | Where-Object { $_.SourceObject -eq $process } | Unregister-Event

        Write-Host "----------------------------------------" -ForegroundColor DarkGray
        Write-Host "$(Get-TimeStamp) 🏁 Command completed with exit code: $exitCode" -ForegroundColor Magenta

        return $exitCode -eq 0
    } catch {
        Write-Host "$(Get-TimeStamp) ❌ SSH failed: $_" -ForegroundColor Red
        return $false
    }
}


function Is-DependencyFile($FilePath) {
    return $FilePath -match 'package\.json$|package-lock\.json$|Dockerfile$|\.env$'
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
        } elseif ($type -eq 'backend') {
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
        } else{
            Write-Host "$(Get-TimeStamp) 🔄 Starting root sync..." -ForegroundColor Blue
            $syncResult = SyncRootOnly
            Write-Host "$(Get-TimeStamp) 🔄 Root sync result: $syncResult" -ForegroundColor Blue
            if (-not $syncResult) { 
                Write-Host "$(Get-TimeStamp) ❌ Root sync failed, aborting" -ForegroundColor Red
                return 
            }
            Start-Sleep -Seconds 2
            Write-Host "$(Get-TimeStamp) 🐳 Running Docker command: $CommandToRun$ParamBuild$BackendApp" -ForegroundColor Blue
			Run-SshCommand "$CommandToRun$ParamBuild$BackendApp"
			Run-SshCommand "$CommandToRun$ParamRec$BackendApp"
            $LastChangeTime["BackendLastSync"] = Get-Date
		}
        Write-Host "$(Get-TimeStamp) ✅ Process completed successfully" -ForegroundColor Green
    } finally {
        $syncInProgress = $false
    }
}

function Check-Changes($dir, $lastKey, $ignorePattern) {
    if (-not $LastChangeTime[$lastKey]) {
        $LastChangeTime[$lastKey] = Get-Date
        return $null
    }
    
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
    Write-Host "Frontend path: $MTGLocalFrontend" -ForegroundColor Yellow
    Write-Host "Backend path: $MTGLocalBackend" -ForegroundColor Yellow
    Write-Host "Requirements path: $MTGLocalProjectFolder" -ForegroundColor Yellow
    
    # Remove trailing slashes for FileSystemWatcher
    $frontendPath = $MTGLocalFrontend.TrimEnd('\')
    $backendPath = $MTGLocalBackend.TrimEnd('\')
	$reqFilePath = $MTGLocalProjectFolder.TrimEnd('\')
    
    Write-Host "Watching Frontend: $frontendPath" -ForegroundColor Yellow
    Write-Host "Watching Backend: $backendPath" -ForegroundColor Yellow
    Write-Host "Watching requirements: $reqFilePath" -ForegroundColor Yellow
    
    # Check if directories exist
    if (-not (Test-Path $frontendPath)) {
        Write-Host "❌ Frontend path does not exist: $frontendPath" -ForegroundColor Red
        return
    }
    if (-not (Test-Path $backendPath)) {
        Write-Host "❌ Backend path does not exist: $backendPath" -ForegroundColor Red
        return
    }
    if (-not (Test-Path $reqFilePath)) {
        Write-Host "❌ requirements.txt path does not exist: $reqFilePath" -ForegroundColor Red
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
		
		$watcherReq = New-Object IO.FileSystemWatcher $reqFilePath
		$watcherReq.NotifyFilter = [IO.NotifyFilters]'LastWrite'
		$watcherReq.Filter = "requirements.txt"
		$watcherReq.IncludeSubdirectories = $false
		$watcherReq.EnableRaisingEvents = $true
		
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
	
	Register-ObjectEvent $watcherReq Changed -Action {
		$fp = $Event.SourceEventArgs.FullPath
		Write-Host "📦 requirements.txt changed: $fp" -ForegroundColor Magenta
		if (-not $Global:ChangeLock) {
			$Global:PendingChanges += @{
				Type = 'root'  # Treat it as backend-related
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
        $fc = Check-Changes $MTGLocalFrontend "FrontendLastBuild" "node_modules|\.git"
        if ($fc) { Process-Change 'frontend' $fc.File.FullName $fc.IsDependency }

        $bc = Check-Changes $MTGLocalBackend "BackendLastSync" "__pycache__|\.git|venv"
        if ($bc) { Process-Change 'backend' $bc.File.FullName $bc.IsDependency }
		
        $rc = Check-Changes $MTGLocalProjectFolder "RootastSync" "__pycache__|\.git|venv"
        if ($rc) { Process-Change 'root' $rc.File.FullName $rc.IsDependency }

        if (++$cleanupCounter -ge 600) { Cleanup-ProcessedFiles; $cleanupCounter = 0 }
        Start-Sleep -Milliseconds 500
    }
}