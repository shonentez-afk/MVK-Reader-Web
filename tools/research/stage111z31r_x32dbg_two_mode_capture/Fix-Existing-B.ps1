# Z31R v1.4: repair ONLY a previously prepared B script while x32dbg is paused.
# Does not open x32dbg, change any breakpoint, resume the process, or read captures.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RunFolder)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

# Fail closed outside a plausible existing Z31R capture folder.
$folder=[System.IO.Path]::GetFullPath($RunFolder).TrimEnd('\')
if ($folder -notmatch '^[A-Za-z]:\\(?:[A-Za-z0-9_-]+\\)*Z31R_[0-9]{8}_[0-9]{6}_[0-9a-f]{8}$') {
    throw 'RunFolder must be one existing Z31R_YYYYMMDD_HHMMSS_XXXXXXXX local folder.'
}
if (-not (Test-Path -LiteralPath $folder -PathType Container)) {
    throw 'The existing Z31R run folder does not exist.'
}
$script=Join-Path $folder 'RESUME_B_FROM_14AA.txt'
$config=Join-Path $folder 'capture_config.json'
$backup=Join-Path $folder 'RESUME_B_FROM_14AA.v13.backup.txt'
if (-not (Test-Path -LiteralPath $script -PathType Leaf) -or -not (Test-Path -LiteralPath $config -PathType Leaf)) {
    throw 'Missing previously generated B script/config: do not patch a different run.'
}
if (Test-Path -LiteralPath $backup) {
    throw 'Backup exists: this run may already have been patched. No overwrite.'
}
# Only replace precisely one known x32dbg command; preserve the original output path.
$original=[System.IO.File]::ReadAllText($script,[System.Text.Encoding]::ASCII)
$needle="bpc 0x007D14AA"
if (([regex]::Matches($original,[regex]::Escape($needle))).Count -ne 1) {
    throw 'B script does not contain exactly one historical faulty command.'
}
foreach ($expected in @('Z31R V1.3 RESUME B','cmp eip,0x007D14AA',
                        'cmp dword:[ebx+8], 0x14','Z31R_B_RESUME','Z31R_BOTH_COMPLETE')) {
    if (-not $original.Contains($expected)) { throw "Unexpected original B script: missing $expected" }
}
if ($original.Contains('__OUT__')) { throw 'B script was not generated for the run folder.' }
$cfg=Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
if ($cfg.schema -ne 'MVKVIEW_STAGE111Z31R_TWO_MODE_CAPTURE_V1' -or
    $cfg.envelope_code -ne 20 -or $cfg.resume_from_original_eip_14aa -ne $true) {
    throw 'Unexpected Z31R capture config; cannot patch safely.'
}
$oldHash=(Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
if ($cfg.script_b_sha256 -ne $oldHash) {
    throw 'Original generated script hash differs from capture_config.json.'
}
$updated=$original.Replace($needle,
    '// Z31R v1.4: no bpc; an already-paused EIP14AA needs no existing BP.')
if ($updated.Contains($needle)) { throw 'Faulty breakpoint command not removed.' }
Copy-Item -LiteralPath $script -Destination $backup -ErrorAction Stop
[System.IO.File]::WriteAllText($script,$updated,[System.Text.Encoding]::ASCII)
$cfg.script_b_sha256=(Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
$cfg | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $config -Encoding UTF8
Write-Host 'Z31R_B_PATCH_OK: removed missing-breakpoint command from EXISTING RESUME_B.'
Write-Host 'Backup:' $backup
Write-Host 'Ready if x32dbg still PAUSED at 007D14AA with [EBX+8]=00000014.'
Write-Host ('scriptexec "'+$script+'"')
