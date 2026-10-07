<#
  Render tools/og-card.html to docs/assets/img/og-card.jpg, the 1200x630
  social sharing card, using headless Edge and Pillow.

    powershell -File tools/og-card.ps1

  Needs images/knowledge-insight-background.jpg (local only) and Pillow
  (py -3 -m pip install pillow). After changing the card, run the link through
  LinkedIn's Post Inspector so LinkedIn drops its cached copy.
#>
$root = Split-Path $PSScriptRoot -Parent
$template = Join-Path $root "tools\og-card.html"
$out = Join-Path $root "docs\assets\img\og-card.jpg"
$png = Join-Path $env:TEMP "ki-og-card.png"

if (-not (Test-Path (Join-Path $root "images\knowledge-insight-background.jpg"))) {
  Write-Error "images\knowledge-insight-background.jpg not found; it is kept locally, not in git."; exit 1
}

$edge = @(
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $edge) { Write-Error "Microsoft Edge not found."; exit 1 }

if (Test-Path $png) { Remove-Item $png }
$url = "file:///" + ($template -replace "\\", "/")
& $edge --headless=new --disable-gpu --no-first-run --hide-scrollbars `
        --allow-file-access-from-files --user-data-dir="$env:TEMP\ki-edge-og" `
        --virtual-time-budget=5000 --window-size="1200,630" --screenshot="$png" $url 2>$null | Out-Null

if (-not (Test-Path $png)) { Write-Error "No screenshot written."; exit 1 }

py -3 -c "from PIL import Image; Image.open(r'$png').convert('RGB').save(r'$out', 'JPEG', quality=88, optimize=True, progressive=True)"
"og-card.jpg  (1200x630)  {0} KB" -f [int]((Get-Item $out).Length / 1KB)
