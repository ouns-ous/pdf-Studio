$ErrorActionPreference = 'Stop'
$taskWorkspace = [IO.Path]::GetFullPath($PSScriptRoot)
$taskInstallDir = [IO.Path]::GetFullPath((Join-Path $taskWorkspace 'tmp\installer-check'))
if (-not $taskInstallDir.StartsWith($taskWorkspace + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Test directory must stay inside the workspace.'
}
$taskUninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{17B925AE-7305-4919-9D65-F3B446E2EAAF}_is1'
if (Test-Path $taskUninstallKey) {
    throw 'PDF Studio is already installed. Skipping the isolated installer check.'
}
New-Item -ItemType Directory -Force -Path (Join-Path $taskWorkspace 'tmp') | Out-Null
$taskInstaller = Join-Path $taskWorkspace 'dist\PDF-Studio-Setup.exe'
$taskLog = Join-Path $taskWorkspace 'tmp\installer-check.log'
$taskInstalled = $false
try {
    $taskSetup = Start-Process -FilePath $taskInstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', '/TASKS=""', ('/DIR="' + $taskInstallDir + '"'), ('/LOG="' + $taskLog + '"')) -WindowStyle Hidden -PassThru
    $taskSetup.WaitForExit()
    if ($taskSetup.ExitCode -ne 0) { throw "Installer failed: $($taskSetup.ExitCode)" }
    $taskInstalled = $true
    $taskExe = Join-Path $taskInstallDir 'PDF-Studio.exe'
    if (-not (Test-Path $taskExe)) { throw 'Installed executable is missing.' }
    if ((Get-FileHash $taskExe).Hash -ne (Get-FileHash (Join-Path $taskWorkspace 'dist\PDF-Studio.exe')).Hash) { throw 'Installed executable differs from the release.' }
    $taskRegistration = Get-ItemProperty -LiteralPath $taskUninstallKey
    if ($taskRegistration.DisplayName -notlike 'PDF Studio*') { throw 'Windows uninstall registration is missing.' }
    $taskApp = Start-Process -FilePath $taskExe -ArgumentList '--smoke-test' -WindowStyle Hidden -PassThru
    if (-not $taskApp.WaitForExit(45000)) { throw 'Installed application did not finish the smoke test.' }
    if ($taskApp.ExitCode -ne 0) { throw "Installed application failed: $($taskApp.ExitCode)" }
    Write-Output 'Installer, executable integrity, Windows registration and installed application checks passed.'
}
finally {
    $taskUninstaller = Join-Path $taskInstallDir 'unins000.exe'
    if ($taskInstalled -and (Test-Path $taskUninstaller)) {
        $taskUninstall = Start-Process -FilePath $taskUninstaller -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -WindowStyle Hidden -PassThru
        $taskUninstall.WaitForExit()
        if ($taskUninstall.ExitCode -ne 0) { throw "Test uninstall failed: $($taskUninstall.ExitCode)" }
        if ((Test-Path (Join-Path $taskInstallDir 'PDF-Studio.exe')) -or (Test-Path $taskUninstallKey)) { throw 'Test installation was not fully removed.' }
        Write-Output 'Uninstall check passed; the test installation was removed.'
    }
}
