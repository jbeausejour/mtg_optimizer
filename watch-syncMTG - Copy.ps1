# Define paths
$LocalFrontendDir = "C:\Users\jules\Desktop\Jules\Github\mtg_optimizer\frontend"
$LocalBackendDir = "C:\Users\jules\Desktop\Jules\Github\mtg_optimizer\backend" 
$FrontendAppSrc = Join-Path $LocalFrontendDir "src"

# Define Synology SSH connection details
$SynologyServer = "ext.julzandfew.com"
$SynologyUser = "root" # Replace with your Synology username if different
$CommandToRun = "sudo docker-compose --profile all -f /volume1/docker/dc-t3.yml "
$ParamRec = "up -d --force-recreate "
$ParamUp = "up -d --build --remove-orphans "
$ParamBuild = "build --no-cache "
$BackendApp = "mtg-flask-app mtg-celery-beat mtg-celery-worker-main mtg-celery-worker-crystal-1 mtg-celery-worker-crystal-2 mtg-celery-worker-shopify mtg-celery-worker-other"
$FrontendApp = "mtg-frontend"

# Create timestamp function
function Get-TimeStamp {
    return "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')]"
}

# Create hashtable to store last change times and processed files
$LastChangeTime = @{
    "FrontendLastBuild" = [DateTime]::MinValue
    "BackendLastSync" = [DateTime]::MinValue
}

# Track processed files to avoid infinite loops
$processedFiles = @{}
$syncInProgress = $false
$cooldownPeriod = 10 # seconds
$buildCooldownPeriod = 30 # seconds for dependency changes

# Function to run SSH command
function Run-SshCommand {
    param(
        [string]$Command
    )
    
    try {
        Write-Host "$(Get-TimeStamp) 🖥️ Running SSH command: $Command" -ForegroundColor Magenta
        
        # Use plink with pageant for SSH in batch mode to avoid interactive prompts
        $plinkCmd = "plink -batch -agent -load `"ext.julzandfew.com root`" bash -l -c '`"$Command`"' "
        
        # Execute the command
        $output = Invoke-Expression $plinkCmd
        
        Write-Host "$(Get-TimeStamp) ✅ SSH command completed" -ForegroundColor Green
        if ($output) {
            Write-Host $output
        }
        return $true
    }
    catch {
        Write-Host "$(Get-TimeStamp) ❌ SSH command failed: $_" -ForegroundColor Red
        return $false
    }
}

# Function to check if a file is a dependency file
function Is-DependencyFile {
    param([string]$FilePath)
    
    # Check if the file is package.json, package-lock.json, or requirements.txt
    return ($FilePath -match "package\.json$" -or 
            $FilePath -match "package-lock\.json$" -or 
            $FilePath -match "requirements\.txt$" -or
            $FilePath -match "Dockerfile$" -or
            $FilePath -match "\.env$")
}

# Function to run sync for frontend with dependency detection
function Process-FrontendChange {
    param(
        $path,
        [switch]$IsDependency
    )
    
    if ($syncInProgress) {
        Write-Host "$(Get-TimeStamp) ⏳ Sync already in progress, skipping" -ForegroundColor Yellow
        return
    }
    
    $syncInProgress = $true
    try {
        Write-Host "$(Get-TimeStamp) 🔧 Frontend change detected: $path" -ForegroundColor Cyan
        
        # Run sync
		if (-not (Sync-FrontendOnly)) {
			return
		}
        
        # Add a small delay to ensure files are completely synced
        Start-Sleep -Seconds 2
        
        # If it's a dependency file, rebuild the container
        if ($IsDependency) {
            # First build the frontend container
            $dockerCommand = $CommandToRun + $ParamBuild + $FrontendApp
            Write-Host "$(Get-TimeStamp) 🔨 Building frontend container..." -ForegroundColor Yellow
            $sshSuccess = Run-SshCommand -Command $dockerCommand
            
            if (-not $sshSuccess) {
                Write-Host "$(Get-TimeStamp) ❌ Frontend build failed" -ForegroundColor Red
                return
            }
            
            # Then bring it up
            $dockerCommand = $CommandToRun + $ParamUp + $FrontendApp
            Write-Host "$(Get-TimeStamp) 🚀 Starting frontend container..." -ForegroundColor Yellow
            $sshSuccess = Run-SshCommand -Command $dockerCommand
            
            # Update last build time if everything was successful
            if ($sshSuccess) {
                $LastChangeTime["FrontendLastBuild"] = Get-Date
                Write-Host "$(Get-TimeStamp) ✅ Frontend deployment completed" -ForegroundColor Green
            }
        } else {
            # Just update the timestamp for regular files
            $LastChangeTime["FrontendLastBuild"] = Get-Date
        }
    }
    finally {
        $syncInProgress = $false
    }
}

# Function to run sync for backend
function Process-BackendChange {
    param(
        $path,
        [switch]$UseRecreate,
        [switch]$IsDependency
    )
    
    if ($syncInProgress) {
        Write-Host "$(Get-TimeStamp) ⏳ Sync already in progress, skipping" -ForegroundColor Yellow
        return
    }
    
    $syncInProgress = $true
    try {
        Write-Host "$(Get-TimeStamp) 🛠️ Backend change detected: $path" -ForegroundColor Yellow
        
        # Run sync
		if (-not (Sync-BackendOnly)) {
			return
		}
        
        # Add a small delay to ensure files are completely synced
        Start-Sleep -Seconds 2
        
        # Always restart container for dependencies, optionally for other changes
        if ($IsDependency -or $UseRecreate) {
            # Run SSH command to restart backend container
            $dockerCommand = if ($UseRecreate) { $CommandToRun + $ParamRec + $BackendApp } else { $CommandToRun + $ParamUp + $BackendApp }
            Write-Host "$(Get-TimeStamp) 🚀 Restarting backend container..." -ForegroundColor Yellow
            $sshSuccess = Run-SshCommand -Command $dockerCommand
            
            # Update last sync time if everything was successful
            if ($sshSuccess) {
                $LastChangeTime["BackendLastSync"] = Get-Date
                Write-Host "$(Get-TimeStamp) ✅ Backend deployment completed" -ForegroundColor Green
            }
        } else {
            # Just update the timestamp
            $LastChangeTime["BackendLastSync"] = Get-Date
        }
    }
    finally {
        $syncInProgress = $false
    }
}
function Sync-BackendOnly {
    Write-Host "$(Get-TimeStamp) 🔄 Running backend-only sync..." -ForegroundColor Yellow
    try {
        & syncMTGB
        Write-Host "$(Get-TimeStamp) ✅ Backend sync completed" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "$(Get-TimeStamp) ❌ Backend sync failed: $_" -ForegroundColor Red
        return $false
    }
}

# Function to run only frontend sync
function Sync-FrontendOnly {
    Write-Host "$(Get-TimeStamp) 🔄 Running frontend-only sync..." -ForegroundColor Yellow
    try {
        & syncMTGF
        Write-Host "$(Get-TimeStamp) ✅ Frontend sync completed" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "$(Get-TimeStamp) ❌ Frontend sync failed: $_" -ForegroundColor Red
        return $false
    }
}
# Function to check for frontend changes
function Check-FrontendChanges {
    # Skip if we're in a cooldown period from last build/sync
    $timeSinceLastBuild = (Get-Date) - $LastChangeTime["FrontendLastBuild"]
    if ($timeSinceLastBuild.TotalSeconds -lt $cooldownPeriod) {
        return $false
    }
    
    # Get recently modified frontend files
    $recentFiles = Get-ChildItem -Path $LocalFrontendDir -Recurse -File | 
                  Where-Object { 
                      $_.LastWriteTime -gt $LastChangeTime["FrontendLastBuild"] -and
                      -not ($_.FullName -match "node_modules|\.git|\.vs|bin|obj|dist")
                  }
    
    if ($recentFiles.Count -gt 0) {
        # Get the most recently modified file
        $mostRecentFile = $recentFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        
        # Skip if it's recently processed
        if ($processedFiles.ContainsKey($mostRecentFile.FullName)) {
            $timeSinceLastProcess = (Get-Date) - $processedFiles[$mostRecentFile.FullName]
            
            # Use a longer cooldown for dependency files
            $requiredCooldown = if (Is-DependencyFile -FilePath $mostRecentFile.FullName) { $buildCooldownPeriod } else { $cooldownPeriod }
            
            if ($timeSinceLastProcess.TotalSeconds -lt $requiredCooldown) {
                return $false
            }
        }
        
        # Mark file as processed with current timestamp
        $processedFiles[$mostRecentFile.FullName] = Get-Date
        
        # Return file with a flag indicating if it's a dependency
        return @{
            File = $mostRecentFile
            IsDependency = Is-DependencyFile -FilePath $mostRecentFile.FullName
        }
    }
    
    return $false
}

# Function to check for backend changes
function Check-BackendChanges {
    # Skip if we're in a cooldown period from last sync
    $timeSinceLastSync = (Get-Date) - $LastChangeTime["BackendLastSync"]
    if ($timeSinceLastSync.TotalSeconds -lt $cooldownPeriod) {
        return $false
    }
    
    # Get recently modified backend files
    $recentFiles = Get-ChildItem -Path $LocalBackendDir -Recurse -File | 
                  Where-Object { 
                      $_.LastWriteTime -gt $LastChangeTime["BackendLastSync"] -and
                      -not ($_.FullName -match "__pycache__|\.git|\.vs|venv|\.pytest_cache")
                  }
    
    if ($recentFiles.Count -gt 0) {
        # Get the most recently modified file
        $mostRecentFile = $recentFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        
        # Skip if it's recently processed
        if ($processedFiles.ContainsKey($mostRecentFile.FullName)) {
            $timeSinceLastProcess = (Get-Date) - $processedFiles[$mostRecentFile.FullName]
            
            # Use a longer cooldown for dependency files
            $requiredCooldown = if (Is-DependencyFile -FilePath $mostRecentFile.FullName) { $buildCooldownPeriod } else { $cooldownPeriod }
            
            if ($timeSinceLastProcess.TotalSeconds -lt $requiredCooldown) {
                return $false
            }
        }
        
        # Mark file as processed with current timestamp
        $processedFiles[$mostRecentFile.FullName] = Get-Date
        
        # Return file with a flag indicating if it's a dependency
        return @{
            File = $mostRecentFile
            IsDependency = Is-DependencyFile -FilePath $mostRecentFile.FullName
        }
    }
    
    return $false
}

# Cleanup old processed files to prevent memory bloat
function Cleanup-ProcessedFiles {
    $currentTime = Get-Date
    $keysToRemove = @()
    
    foreach ($key in $processedFiles.Keys) {
        $age = $currentTime - $processedFiles[$key]
        if ($age.TotalMinutes -gt 10) {
            $keysToRemove += $key
        }
    }
    
    foreach ($key in $keysToRemove) {
        $processedFiles.Remove($key)
    }
}

# First, test SSH connection to make sure it works
Write-Host "Testing SSH connection to $SynologyUser@$SynologyServer..." -ForegroundColor Cyan
$testResult = Run-SshCommand -Command "echo Connection test successful"
if (-not $testResult) {
    Write-Host "Error: Could not establish SSH connection. Please make sure Pageant is running with your SSH key loaded." -ForegroundColor Red
    Write-Host "Script will continue but SSH commands may fail." -ForegroundColor Yellow
}

# Ask user preference for backend container restart
$recreateBackend = $false
$response = Read-Host "Would you like to use '--force-recreate' for backend changes? (y/N)"
if ($response -eq "y" -or $response -eq "Y") {
    $recreateBackend = $true
    Write-Host "Using '$CommandToRun$ParamRec$BackendApp' for backend container restarts." -ForegroundColor Cyan
} else {
    Write-Host "Using '$CommandToRun$ParamUp$BackendApp' for backend container restarts." -ForegroundColor Cyan
}

# Initialize timestamps to now to avoid processing existing changes
$LastChangeTime["FrontendLastBuild"] = Get-Date
$LastChangeTime["BackendLastSync"] = Get-Date

# Main polling loop
Write-Host ""
Write-Host "👀 Watching for file changes in:" -ForegroundColor Green
Write-Host "Frontend: $LocalFrontendDir" -ForegroundColor Cyan
Write-Host "Backend: $LocalBackendDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔍 Dependency files (package.json, requirements.txt, etc.) will trigger container rebuilds" -ForegroundColor Cyan
Write-Host "⚙️ SSH commands will be executed on $SynologyUser@$SynologyServer" -ForegroundColor Yellow
Write-Host "⚙️ Frontend dependencies will trigger: $CommandToRun$ParamBuild$FrontendApp and then $CommandToRun$ParamUp$FrontendApp" -ForegroundColor Yellow
if ($recreateBackend) {
    Write-Host "⚙️ Backend dependencies will trigger: $CommandToRun$ParamRec$BackendApp" -ForegroundColor Yellow
} else {
    Write-Host "⚙️ Backend dependencies will trigger: $CommandToRun$ParamUp$BackendApp" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Press Ctrl+C to stop watching." -ForegroundColor Yellow
Write-Host ""

$cleanupCounter = 0
try {
    while ($true) {
        # Check for frontend changes
        $frontendChange = Check-FrontendChanges
        if ($frontendChange) {
            Process-FrontendChange -path $frontendChange.File.FullName -IsDependency:$frontendChange.IsDependency
        }
        
        # Check for backend changes
        $backendChange = Check-BackendChanges
        if ($backendChange) {
            Process-BackendChange -path $backendChange.File.FullName -UseRecreate:$recreateBackend -IsDependency:$backendChange.IsDependency
        }
        
        # Cleanup old processed files periodically (every ~5 minutes)
        $cleanupCounter++
        if ($cleanupCounter -ge 600) { # 600 * 500ms = 5 minutes
            Cleanup-ProcessedFiles
            $cleanupCounter = 0
        }
        
        # Short sleep to prevent CPU overuse
        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host "File watcher stopped." -ForegroundColor Yellow
}