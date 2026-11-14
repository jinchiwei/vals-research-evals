param([string]$pptx, [string]$outdir)
$tmp = Join-Path $env:TEMP ("deckqa_" + [guid]::NewGuid().ToString() + ".pptx")
Copy-Item $pptx $tmp
$app = New-Object -ComObject PowerPoint.Application
try {
  $pres = $app.Presentations.Open($tmp, 0, 0, -1)
  New-Item -ItemType Directory -Force -Path $outdir | Out-Null
  $i = 1
  foreach ($s in $pres.Slides) { $s.Export((Join-Path $outdir ("slide-{0}.png" -f $i)), "PNG", 1600, 900); $i++ }
  Write-Output "exported $($i-1)"
  $pres.Close()
} catch { Write-Output ("ERR: " + $_.Exception.Message) }
$app.Quit()
Remove-Item $tmp -ErrorAction SilentlyContinue
