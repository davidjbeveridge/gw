param([switch]$All, [string]$Agents = '', [string]$Project = '', [switch]$Knowledge, [switch]$Plugins, [switch]$AgentTools, [switch]$Context)
$ErrorActionPreference = 'Stop'
$ref = if ($env:GW_REF) { $env:GW_REF } else { 'v0.8.0' }
if ($ref -notmatch '^[A-Za-z0-9._-]+$') { throw 'Invalid GW_REF' }
$root = if ($env:GW_INSTALL_DIR) { $env:GW_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'gw' }
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw 'Install Python 3.10+ and rerun this script.' }
& $python -c 'import sys; assert sys.version_info >= (3,10)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required.' }
& $python -m venv (Join-Path $root 'venv')
if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment.' }
$venvPython = Join-Path $root 'venv\Scripts\python.exe'
& $venvPython -m pip install --disable-pip-version-check --no-input --upgrade "https://github.com/davidjbeveridge/gw/archive/$ref.zip"
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
& $venvPython -m pip install --disable-pip-version-check --no-input --upgrade "https://github.com/davidjbeveridge/gw/archive/$ref.zip#subdirectory=packages/gw-builtin"
if ($LASTEXITCODE -ne 0) { throw 'Reference plugin installation failed.' }
if ($Context -or $Knowledge -or $AgentTools) {
  & $venvPython -m pip install --disable-pip-version-check --no-input --upgrade "https://github.com/davidjbeveridge/gw/archive/$ref.zip#subdirectory=packages/gw-context"
  if ($LASTEXITCODE -ne 0) { throw 'Context package installation failed.' }
}
if ($Knowledge) {
  & $venvPython -m pip install --disable-pip-version-check --no-input --upgrade "https://github.com/davidjbeveridge/gw/archive/$ref.zip#subdirectory=packages/gw-knowledge"
  if ($LASTEXITCODE -ne 0) { throw 'Knowledge package installation failed.' }
}
if ($Plugins) {
  foreach ($package in @('gw-observe', 'gw-learning', 'gw-sync')) {
    & $venvPython -m pip install --disable-pip-version-check --no-input --upgrade "https://github.com/davidjbeveridge/gw/archive/$ref.zip#subdirectory=packages/$package"
    if ($LASTEXITCODE -ne 0) { throw "Plugin package installation failed: $package" }
  }
}
if ($AgentTools) {
  & $venvPython -m pip install --disable-pip-version-check --no-input --upgrade "gw-supervisor[agent] @ https://github.com/davidjbeveridge/gw/archive/$ref.zip"
  if ($LASTEXITCODE -ne 0) { throw 'Agent tool dependencies failed to install.' }
}
$gw = Join-Path $root 'venv\Scripts\gw.exe'
$arguments = @('bootstrap')
if ($AgentTools) { $arguments += '--agent-tools' }
if ($All) { $arguments += '--all' }
if ($Agents) { $arguments += @('--agents', $Agents) }
if ($Project) { $arguments += @('--project', $Project) }
& $gw @arguments
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap failed; existing settings were not blindly overwritten.' }
Write-Host "Installed $gw. Run: & '$gw' doctor"
Write-Host 'No machine PATH, execution policy, provider login, or service was changed.'
