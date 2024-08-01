$OhMyPoshConfig = "$Env:POSH_THEMES_PATH/kali.omp.json"
$font="FiraCode" # Font-Display and variable Name, name the same as font_folder
$name = "Jules"
$configPath = "$HOME\pwsh_custom_config.yml"

# OK $OhMyPoshTheme = "$Env:POSH_THEMES_PATH/emodipt-extend.omp.json"
# OK $OhMyPoshTheme = "$Env:POSH_THEMES_PATH/amro.omp.json"

# Function to create config file
function Install-Config {
    if (-not (Test-Path -Path $configPath)) {
        Write-Host "No configuration file found @ $configPath creating...❗" -ForegroundColor Yellow
        New-Item -ItemType File -Path $configPath | Out-Null
        Write-Host "Configuration file created at $configPath ❗" -ForegroundColor Green
    } else {
        Write-Host "✅ Successfully loaded config file ($configPath)" -ForegroundColor Green
    }
    Initialize-Keys
    Initialize-DevEnv
}

# Function to set a value in the config file
function Set-ConfigValue {
    param (
        [string]$Key,
        [string]$Value
    )
    $config = @{}
    # Try to load the existing config file content
    if (Test-Path -Path $configPath) {
        $content = Get-Content $configPath -Raw
        if (-not [string]::IsNullOrEmpty($content)) {
            $config = $content | ConvertFrom-Yaml
        }
    }
    # Ensure $config is a hashtable
    if (-not $config) {
        $config = @{}
    }
    $config[$Key] = $Value
    $config | ConvertTo-Yaml | Set-Content $configPath
    # Write-Host "Set '$Key' to '$Value' in configuration file." -ForegroundColor Green
    Initialize-Keys
}

# Function to get a value from the config file
function Get-ConfigValue {
    param (
        [string]$Key
    )
    $config = @{}
    # Try to load the existing config file content
    if (Test-Path -Path $configPath) {
        $content = Get-Content $configPath -Raw
        if (-not [string]::IsNullOrEmpty($content)) {
            $config = $content | ConvertFrom-Yaml
        }
    }
    # Ensure $config is a hashtable
    if (-not $config) {
        $config = @{}
    }
    return $config[$Key]
}

function Initialize-Module {
    param (
        [string]$moduleName
    )
	try {
		Install-Module -Name $moduleName -Scope CurrentUser -SkipPublisherCheck
		Set-ConfigValue -Key "${moduleName}_installed" -Value "True"
	} catch {
		Write-Error "❌ Failed to install module ${moduleName}: $_"
	}
}

function Initialize-Keys {
    $keys = "Powershell-Yaml_installed", "Terminal-Icons_installed", "PoshFunctions_installed", "${font}_installed", "ohmyposh_installed"
    foreach ($key in $keys) {
        $value = Get-ConfigValue -Key $key
        Set-Variable -Name $key -Value $value -Scope Global
    }
}

function Initialize-DevEnv {

    $modules = @(
        @{ Name = "Powershell-Yaml"; ConfigKey = "Powershell-Yaml_installed" },
        @{ Name = "Terminal-Icons"; ConfigKey = "Terminal-Icons_installed" },
        @{ Name = "PoshFunctions"; ConfigKey = "PoshFunctions_installed" }
    )
    $importedModuleCount = 0
    foreach ($module in $modules) {
        $isInstalled = Get-ConfigValue -Key $module.ConfigKey
        if ($isInstalled -ne "True") {
            Write-Host "Initializing $($module.Name) module..."
            Initialize-Module $module.Name
			Write-Host "✅ Successfully initialized $($module.Name)" -ForegroundColor Green
        } else {
            Import-Module $module.Name
			Write-Host "✅ Successfully loaded $($module.Name)" -ForegroundColor Green
            $importedModuleCount++
        }
    }
    Write-Host "✅ Imported $importedModuleCount modules successfully." -ForegroundColor Green
}

# -------------
# Run section
Write-Host ""
Write-Host "(CurrentUserCurrentHost) Welcome $name ⚡" -ForegroundColor DarkCyan
Write-Host ""
#All Colors: Black, Blue, Cyan, DarkBlue, DarkCyan, DarkGray, DarkGreen, DarkMagenta, DarkRed, DarkYellow, Gray, Green, Magenta, Red, White, Yellow.

Install-Config

# Inject OhMyPosh
oh-my-posh init pwsh --config $OhMyPoshConfig | Invoke-Expression

function GoToProjects {
    Set-Location -Path "~\Desktop\Jules\GitHub\"
}

fnm env --use-on-cd | Out-String | Invoke-Expression
Set-Alias -Name gh -Value GoToProjects