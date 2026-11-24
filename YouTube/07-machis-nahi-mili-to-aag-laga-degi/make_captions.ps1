# Render the Hindi captions as transparent PNGs (1080x300), one per caption card.
#
# Windows' own text engine (GDI+) is used because it shapes Devanagari correctly;
# the image library used for the video frames does not. The cards are listed in
# captions.txt as  name|text  (with \n for a line break) so this script stays ASCII.
#
# Run (from this folder):
#     powershell -ExecutionPolicy Bypass -File make_captions.ps1

Add-Type -AssemblyName System.Drawing

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $here "captions"
New-Item -ItemType Directory -Force $outDir | Out-Null

$W = 1080; $H = 300
$maxTextW = 960; $maxTextH = 220
$padX = 30; $padY = 22; $radius = 25

function New-RoundedPath([single]$x, [single]$y, [single]$w, [single]$h, [single]$r) {
    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = 2 * $r
    $p.AddArc($x, $y, $d, $d, 180, 90)
    $p.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $p.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $p.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $p.CloseFigure()
    return $p
}

$format = New-Object System.Drawing.StringFormat ([System.Drawing.StringFormat]::GenericTypographic)
$format.Alignment = [System.Drawing.StringAlignment]::Center
$format.LineAlignment = [System.Drawing.StringAlignment]::Center

foreach ($row in Get-Content (Join-Path $here "captions.txt") -Encoding UTF8) {
    if (-not $row.Trim()) { continue }
    $name, $text = $row.Split("|", 2)
    $text = $text.Replace("\n", "`n")

    $bitmap = New-Object System.Drawing.Bitmap $W, $H, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bitmap)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)

    # Largest size (up to 56 px) at which the text fits the card.
    $size = 56
    do {
        $font = New-Object System.Drawing.Font "Nirmala UI", $size, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
        $measured = $g.MeasureString($text, $font, 4000, $format)
        if ($measured.Width -le $maxTextW -and $measured.Height -le $maxTextH) { break }
        $font.Dispose(); $size -= 2
    } while ($size -gt 20)

    $boxW = $measured.Width + 2 * $padX; $boxH = $measured.Height + 2 * $padY
    $boxX = ($W - $boxW) / 2; $boxY = ($H - $boxH) / 2
    $path = New-RoundedPath $boxX $boxY $boxW $boxH $radius
    $fill = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(184, 0, 0, 0))
    $edge = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(153, 255, 255, 255)), 2
    $g.FillPath($fill, $path); $g.DrawPath($edge, $path)

    $area = New-Object System.Drawing.RectangleF $boxX, $boxY, $boxW, $boxH
    $g.DrawString($text, $font, [System.Drawing.Brushes]::White, $area, $format)

    $g.Dispose()
    $bitmap.Save((Join-Path $outDir "$name.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    $bitmap.Dispose()
    "{0}: {1}px text, box {2}x{3}" -f $name, $size, [int]$boxW, [int]$boxH
}
