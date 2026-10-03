<#
  Capture a page at a chosen viewport width using headless Edge.

  Pages are rendered inside tools/overflow-probe.html at an exact iframe width.
  Passing --window-size to headless Edge does not resize the layout viewport,
  it only crops the capture, so a naive screenshot of a phone-width window
  shows a desktop layout with its right-hand side cut off.

    pwsh tools/shoot.ps1 -Path "/programs/.../map/" -Width 390 -Out map.png
#>
param(
  [string]$Path = "/",
  [int]$Width = 390,
  [int]$Height = 1400,
  [string]$Out = "shot.png",
  [int]$Port = 8000
)

$edge = @(
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $edge) { Write-Error "Microsoft Edge not found."; exit 1 }

$profileDir = Join-Path $env:TEMP "ki-edge-shots"
$encoded = [uri]::EscapeDataString($Path)
$probe = "http://localhost:$Port/tools/overflow-probe.html?bare=1&w=$Width&h=$Height&url=$encoded"

& $edge --headless=new --disable-gpu --no-first-run --hide-scrollbars `
        --user-data-dir="$profileDir" --virtual-time-budget=6000 `
        --window-size="$Width,$Height" --screenshot="$Out" $probe 2>$null | Out-Null

if (Test-Path $Out) {
  "{0}  ({1}x{2})  {3} KB" -f (Split-Path $Out -Leaf), $Width, $Height, [int]((Get-Item $Out).Length / 1KB)
} else {
  Write-Error "No screenshot written."
}
