# Stage111Z31R. Generates ONE two-mode x32dbg capture, offline and read-only.
# Works with Windows PowerShell 5.1. Does NOT start original MVKView or a device.
[CmdletBinding()]
param(
    [ValidateRange(1,8)][int]$Adc = 4,
    [ValidateSet(4096,8192,16384,32768,65536,131072,262144)][int]$N = 262144,
    [ValidateRange(0,3)][int]$SpectrumType = 2,
    [string]$Root = 'C:\MVK_CAPTURE',
    [string]$ArchiveBin = '',
    [string]$ArchiveTsxml = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# The supported original site and mode are intentionally fixed by the
# source-verified DFM/IDP GetSpectrum path, not guessed by a script.
$RawFs = 65536
$EnvelopeCode = 20
$EnvelopeOutputFs = 32768

# Avoid x32dbg quoting ambiguity, existing file overwrite and UNC surprises.
if ($Root -notmatch '^[A-Za-z]:\\[A-Za-z0-9_\\-]+$' -or $Root.Length -gt 100) {
    throw 'Root must be a simple ASCII local Windows path such as C:\MVK_CAPTURE (no spaces, punctuation or UNC).'
}
$fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
if ($fullRoot -match '^[A-Za-z]:$') { throw 'Refuse to write at a drive root.' }
if (-not (Test-Path -LiteralPath $fullRoot)) { New-Item -ItemType Directory -Path $fullRoot -Force | Out-Null }
$runName = 'Z31R_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
$runPath = Join-Path $fullRoot $runName
New-Item -ItemType Directory -Path $runPath -ErrorAction Stop | Out-Null
foreach ($phase in @('A','B')) {
    New-Item -ItemType Directory -Path (Join-Path $runPath $phase) -ErrorAction Stop | Out-Null
}

function To-Hex([int]$value) { return ('0x{0:X}' -f $value) }
function Load-Template([string]$name) {
    $path = Join-Path $PSScriptRoot $name
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing package file: $name" }
    return [System.IO.File]::ReadAllText($path,[System.Text.Encoding]::ASCII)
}
$script = Load-Template 'CAPTURE_BOTH.template.txt'
$replacements = @{
    '__OUT__' = $runPath
    '__N_HEX__' = (To-Hex $N)
    '__HALF_N_HEX__' = (To-Hex ($N / 2))
    '__MODE_HEX__' = (To-Hex $SpectrumType)
    '__ENV_HEX__' = (To-Hex $EnvelopeCode)
    '__RAW_FS_HEX__' = (To-Hex $RawFs)
    '__ENVELOPE_FS_HEX__' = (To-Hex $EnvelopeOutputFs)
}
foreach ($key in $replacements.Keys) { $script = $script.Replace($key,[string]$replacements[$key]) }
if ($script -match '__[A-Z_]+__') { throw 'Internal placeholder substitution incomplete' }
$ready = Load-Template 'CHECK_READY.template.txt'
$scriptFile = Join-Path $runPath 'CAPTURE_BOTH.txt'
$readyFile = Join-Path $runPath 'CHECK_READY.txt'
[System.IO.File]::WriteAllText($scriptFile,$script,[System.Text.Encoding]::ASCII)
[System.IO.File]::WriteAllText($readyFile,$ready,[System.Text.Encoding]::ASCII)

$config = [ordered]@{
    schema = 'MVKVIEW_STAGE111Z31R_TWO_MODE_CAPTURE_V1'
    fft_n = $N
    spectrum_mode = $SpectrumType
    adc_claim = $Adc
    raw_sample_rate_hz = $RawFs
    envelope_code = $EnvelopeCode
    envelope_output_fs_hz = $EnvelopeOutputFs
    source_archive_same_run_not_automatically_proven = $true
    generated_utc = [DateTime]::UtcNow.ToString('o')
    original_program = 'MVKView 1.0.47 x32dbg only'
    script_sha256 = (Get-FileHash -LiteralPath $scriptFile -Algorithm SHA256).Hash.ToLowerInvariant()
}
if (-not [string]::IsNullOrWhiteSpace($ArchiveBin)) {
    if (-not (Test-Path -LiteralPath $ArchiveBin -PathType Leaf)) { throw 'Archive BIN missing' }
    $config['source_bin_filename_claim'] = [System.IO.Path]::GetFileName($ArchiveBin)
    $config['source_bin_sha256'] = (Get-FileHash -LiteralPath $ArchiveBin -Algorithm SHA256).Hash.ToLowerInvariant()
}
if (-not [string]::IsNullOrWhiteSpace($ArchiveTsxml)) {
    if (-not (Test-Path -LiteralPath $ArchiveTsxml -PathType Leaf)) { throw 'Archive TSXML missing' }
    $config['source_tsxml_filename_claim'] = [System.IO.Path]::GetFileName($ArchiveTsxml)
    $config['source_tsxml_sha256'] = (Get-FileHash -LiteralPath $ArchiveTsxml -Algorithm SHA256).Hash.ToLowerInvariant()
}
$configPath = Join-Path $runPath 'capture_config.json'
$config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $configPath -Encoding UTF8
$steps = @(
 'STAGE111Z31R: original MVKView1.0.47 + x32dbg, NO device connection.',
 '1) Run original GUI to the normal screen first; do NOT start from System/Entry breakpoint or old TAG INT3.',
 ('2) Open offline source ADC ' + $Adc + ', FFT N=' + $N + ', Fs=65536, SpectrumType=' + $SpectrumType + ', filter=0.'),
 '3) In x32dbg F12 Pause; disable old unrelated breakpoints. Run CHECK_READY first:',
 ('scriptexec "' + $readyFile + '"'),
 '4) With original GUI still open, F12 Pause again then launch ONE script:',
 ('scriptexec "' + $scriptFile + '"'),
 '5) Trigger/refresh plain spectrum in original GUI only when it resumes.',
 '6) After first capture a message appears. Click OK, choose menu '1oct 16 kHz' (EnvelopeCode 20) and trigger a new spectrum calculation.',
 '7) Do NOT manually press F9 or skip x32dbg scripts while they are active.',
 '8) After Z31R_BOTH_COMPLETE check with: py -3 Verify-Capture.py "RUN_FOLDER"',
 '9) If a FAIL appears, keep all partial files and the x32dbg Log. Do not bypass pointer or window checks.',
 '10) Same END and matching raw samples required; otherwise reports NOT SAME WINDOW.'
)
$steps | Set-Content -LiteralPath (Join-Path $runPath 'RUN_ME.txt') -Encoding UTF8
Write-Host ''
Write-Host 'Z31R CREATED (private, local only):' $runPath
Write-Host 'CHECK_READY:' ('scriptexec "' + $readyFile + '"')
Write-Host 'CAPTURE_BOTH:' ('scriptexec "' + $scriptFile + '"')
Write-Host 'After capture: py -3 Verify-Capture.py' ('"' + $runPath + '"')
Write-Host 'Original device/EXE/IDP untouched. Do not upload files to public GitHub.'
