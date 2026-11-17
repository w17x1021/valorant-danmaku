# Windows.Media.Ocr persistent worker (Windows PowerShell 5.1)
# ASCII-only source: keep it that way so PS 5.1 never mis-decodes the file.
# Protocol: one JSON request per line -> one JSON response per line
#   request : {"b64":"<png bytes base64>","langs":["en-US","ja","zh-Hans-CN"]}
#   response: {"ok":true,"lines":[{"lang":"en-US","text":"...","x":0,"y":0,"w":1,"h":1}]}
param([string]$DefaultLang = "en-US")

$ErrorActionPreference = "Stop"
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
} catch { }

Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataWriter, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]

$available = @()
foreach ($l in [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages) { $available += [string]$l.LanguageTag }

$global:engines = @{}
function Get-Engine([string]$tag) {
    if ($global:engines.ContainsKey($tag)) { return $global:engines[$tag] }
    $e = $null
    try {
        $lang = New-Object Windows.Globalization.Language($tag)
        $e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
    } catch { $e = $null }
    $global:engines[$tag] = $e
    return $e
}

function Decode-Bitmap([string]$b64) {
    $bytes = [Convert]::FromBase64String($b64)
    $ms = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    $writer = New-Object Windows.Storage.Streams.DataWriter($ms)
    $writer.WriteBytes($bytes)
    $null = Await ($writer.StoreAsync()) ([uint32])
    $writer.DetachStream() | Out-Null
    $ms.Seek(0)
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ms)) ([Windows.Graphics.Imaging.BitmapDecoder])
    return (Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap]))
}

function Ocr-Bitmap($bitmap, [string]$lang) {
    $engine = Get-Engine $lang
    if ($null -eq $engine) { return $null }
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $out = New-Object System.Collections.ArrayList
    foreach ($ln in $result.Lines) {
        $x = 1e9; $y = 1e9; $r = -1.0; $b = -1.0
        foreach ($w in $ln.Words) {
            $rect = $w.BoundingRect
            if ($rect.X -lt $x) { $x = $rect.X }
            if ($rect.Y -lt $y) { $y = $rect.Y }
            if (($rect.X + $rect.Width) -gt $r) { $r = $rect.X + $rect.Width }
            if (($rect.Y + $rect.Height) -gt $b) { $b = $rect.Y + $rect.Height }
        }
        if ($r -lt 0) { $x = 0.0; $y = 0.0; $r = 0.0; $b = 0.0 }
        $null = $out.Add([ordered]@{
            lang = [string]$lang
            text = [string]$ln.Text
            x    = [int]$x
            y    = [int]$y
            w    = [int]($r - $x)
            h    = [int]($b - $y)
        })
    }
    return $out
}

$hello = [ordered]@{ ok = $true; ready = $true; available = @($available) }
[Console]::Out.WriteLine(($hello | ConvertTo-Json -Depth 6 -Compress))
[Console]::Out.Flush()

while ($true) {
    $line = [Console]::In.ReadLine()
    if ($null -eq $line) { break }
    $line = $line.Trim()
    if ($line.Length -eq 0) { continue }
    $resp = $null
    try {
        $req = $line | ConvertFrom-Json
        $langList = @($req.langs)
        if ($langList.Count -eq 0) { $langList = @($DefaultLang) }
        $bitmap = Decode-Bitmap ([string]$req.b64)
        $all = New-Object System.Collections.ArrayList
        foreach ($lg in $langList) {
            $res = Ocr-Bitmap $bitmap ([string]$lg)
            if ($null -ne $res) { foreach ($r in $res) { $null = $all.Add($r) } }
        }
        $bitmap.Dispose()
        $resp = [ordered]@{ ok = $true; available = @($available); lines = $all.ToArray() }
    } catch {
        $msg = $_.Exception.Message
        if ($null -ne $_.Exception.InnerException) { $msg = $msg + " | " + $_.Exception.InnerException.Message }
        $resp = [ordered]@{ ok = $false; error = $msg }
    }
    [Console]::Out.WriteLine(($resp | ConvertTo-Json -Depth 8 -Compress))
    [Console]::Out.Flush()
}
