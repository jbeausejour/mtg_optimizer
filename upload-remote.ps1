# Configuration
$pscpPath = "C:\Program Files\PuTTY\pscp.exe"   # Change if needed
$localPath = "$HOME\Desktop\Jules\Github\mtg_optimizer\backend"
$remoteUser = "root"
$remoteHost = "ext.julzandfew.com"
$remotePath = "/volume1/docker/appdata/mtg-flask-app/"  # Destination on server
$remotePort = 7022

# Upload all .py files recursively
Get-ChildItem -Path $localPath -Recurse -Include *.py | ForEach-Object {
    $relativePath = $_.FullName.Substring($localPath.Length + 1)
    $remoteFullPath = ($remotePath.TrimEnd('/') + '/' + $relativePath.Replace('\', '/')).Replace('//', '/')

    Write-Host "Uploading $($_.Name) to $remoteFullPath"

    & $pscpPath -scp -P $remotePort $_.FullName "$($remoteUser)@$($remoteHost):$remoteFullPath"
}

Write-Host "`n✅ Upload complete using Pageant authentication on port $remotePort."
