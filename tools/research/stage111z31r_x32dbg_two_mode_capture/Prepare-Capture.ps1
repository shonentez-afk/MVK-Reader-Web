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
# Two short resumable scripts: NEVER keep a Script thread waiting for an
# original GUI action. This fixes the observed 'Script is terminated by user'
# on the very first successful stop at 007D14AA in v1.2.
$replacements = @{
    '__OUT__' = $runPath
    '__N_HEX__' = (To-Hex $N)
    '__HALF_N_HEX__' = (To-Hex ($N / 2))
    '__MODE_HEX__' = (To-Hex $SpectrumType)
    '__ENV_HEX__' = (To-Hex $EnvelopeCode)
    '__RAW_FS_HEX__' = (To-Hex $RawFs)
    '__ENVELOPE_FS_HEX__' = (To-Hex $EnvelopeOutputFs)
}
function Generate-Script([string]$template,[string]$output) {
    $body=Load-Template $template
    foreach ($key in $replacements.Keys) { $body = $body.Replace($key,[string]$replacements[$key]) }
    if ($body -match '__[A-Z_]+__') { throw "Unexpanded placeholder in $output" }
    $where=Join-Path $runPath $output
    [System.IO.File]::WriteAllText($where,$body,[System.Text.Encoding]::ASCII)
    return $where
}
$readyFile = Generate-Script 'CHECK_READY.template.txt' 'CHECK_READY.txt'
$aFile = Generate-Script 'RESUME_A_FROM_14AA.template.txt' 'RESUME_A_FROM_14AA.txt'
$bFile = Generate-Script 'RESUME_B_FROM_14AA.template.txt' 'RESUME_B_FROM_14AA.txt'
$armBFile = Generate-Script 'ARM_B_ONLY.template.txt' 'ARM_B_ONLY.txt'

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
    script_a_sha256 = (Get-FileHash -LiteralPath $aFile -Algorithm SHA256).Hash.ToLowerInvariant()
    script_b_sha256 = (Get-FileHash -LiteralPath $bFile -Algorithm SHA256).Hash.ToLowerInvariant()
    arm_b_sha256 = (Get-FileHash -LiteralPath $armBFile -Algorithm SHA256).Hash.ToLowerInvariant()
    resume_from_original_eip_14aa = $true
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
 'Z31R v1.3: Resume-safe ORIGINAL two-mode capture. NO original device connection.',
 ('RUN FOLDER: ' + $runPath),
 '0) Original MVKView1.0.47 must be open in x32dbg; source archive ADC4 loaded.',
 '1) CHECK_READY only once if x32dbg is PAUSED:',
 ('scriptexec "' + $readyFile + '"'),
 '2) For A, STOP at exact original EIP=007D14AA with filter=0.',
 '   If CURRENT EIP is already 007D14AA (INT3 screenshot), DO NOT F9 or re-run CAPTURE_BOTH.',
 '   Otherwise from a PAUSED x32dbg command bar enter: run 0x007D14AA',
 '   Then trigger plain spectrum in the original GUI and wait for x32dbg STOP at 007D14AA.',
 '3) x32dbg MUST BE PAUSED at EIP=007D14AA: execute:',
 ('scriptexec "' + $aFile + '"'),
 '   This performs A->14B8->153D->154B->17E7->1900 and exits; no human wait inside script.',
 '4) After A_SAVED original process remains PAUSED at 007D1900. Now arm code20-only breakpoint:',
 ('scriptexec "' + $armBFile + '"'),
 '5) AFTER ARM_B script says finished, press F9 ONCE. In the ORIGINAL GUI select 1oct 16 kHz (EnvelopeCode 20).',
 '   Recalculate spectrum. x32dbg ignores code0 hits; stops at EIP=007D14AA with code20.',
 '6) From x32dbg PAUSED at EIP=007D14AA and [EBX+8]==0x14 execute:',
 ('scriptexec "' + $bFile + '"'),
 '7) Wait until Z31R_BOTH_COMPLETE, then check: py -3 Verify-Capture.py "RUN_FOLDER"',
 '8) Do not re-run any resume script at wrong EIP, do not overwrite old files, do not modify memory.',
 '9) If FAIL / SCRIPT_TERMINATED appears, SAVE LOG and partial capture without F9.',
 '10) For full BIN numerical parity original archive hash/ADC/window binding is still needed.'
)
$steps | Set-Content -LiteralPath (Join-Path $runPath 'RUN_ME.txt') -Encoding UTF8
Write-Host ''
Write-Host 'Z31R CREATED (private, local only):' $runPath
Write-Host 'CHECK_READY:' ('scriptexec "' + $readyFile + '"')
Write-Host 'RESUME_A (ONLY at EIP14AA):' ('scriptexec "' + $aFile + '"')
Write-Host 'ARM_B (after A finishes):' ('scriptexec "' + $armBFile + '"')
Write-Host 'RESUME_B (ONLY at EIP14AA/code20):' ('scriptexec "' + $bFile + '"')
Write-Host 'After capture: py -3 Verify-Capture.py' ('"' + $runPath + '"')
Write-Host 'Original device/EXE/IDP untouched. Do not upload files to public GitHub.'
