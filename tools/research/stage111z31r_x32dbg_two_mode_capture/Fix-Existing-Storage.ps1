# Z31R v1.5 -- correct source-proven Float32 ring enum for a PREPARED B script.
# This does NOT touch the original executable, x32dbg, breakpoints, source archive or samples.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RunFolder)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest

$folder=[System.IO.Path]::GetFullPath($RunFolder).TrimEnd('\')
if ($folder -notmatch '^[A-Za-z]:\\(?:[A-Za-z0-9_-]+\\)*Z31R_[0-9]{8}_[0-9]{6}_[0-9a-f]{8}$') {
    throw 'RunFolder must be an existing Z31R_YYYYMMDD_HHMMSS_XXXXXXXX local directory.'
}
if (-not (Test-Path -LiteralPath $folder -PathType Container)) { throw 'Capture run folder missing.' }
$script=Join-Path $folder 'RESUME_B_FROM_14AA.txt'
$config=Join-Path $folder 'capture_config.json'
$backup=Join-Path $folder 'RESUME_B_FROM_14AA.v14.bad_datatype.backup.txt'
if (-not (Test-Path -LiteralPath $script -PathType Leaf) -or -not (Test-Path -LiteralPath $config -PathType Leaf)) {
    throw 'Expected existing B script/capture_config.json missing; do not create a new session.'
}
if (Test-Path -LiteralPath $backup) { throw 'Already patched or backup exists; refusing overwrite.' }
if ((Get-Item -LiteralPath $script).Length -gt 50000 -or (Get-Item -LiteralPath $config).Length -gt 8192) {
    throw 'Unexpected capture file sizes.'
}
$original=[System.IO.File]::ReadAllText($script,[System.Text.Encoding]::ASCII)
$cfg=Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
if ($cfg.schema -ne 'MVKVIEW_STAGE111Z31R_TWO_MODE_CAPTURE_V1' -or
    $cfg.envelope_code -ne 20 -or $cfg.resume_from_original_eip_14aa -ne $true) {
    throw 'This is not a validated Z31R original x32dbg capture configuration.'
}
$oldHash=(Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
if ($cfg.script_b_sha256 -ne $oldHash) { throw 'Existing B script differs from its recorded SHA256.' }
foreach ($expected in @('cmp eip,0x007D14AA','Z31R_B_RESUME','Z31R_BOTH_COMPLETE',
                       'cmp dword:[ebx+8], 0x14','run 0x007D14B8','Z31R_FAIL_STORAGE:')) {
    if (-not $original.Contains($expected)) { throw "Unexpected B code; missing $expected" }
}
if ($original.Contains('bpc 0x007D14AA')) { throw 'Old missing-BP bug still present. Install v1.4 fix first.' }
if ($original.Contains('__OUT__')) { throw 'This is an ungenerated template, not the active run B.' }
$oldPointer="cmp mem.base(`$z31r_ctx_storage),0`nje Z31R_FAIL_STORAGE"
$newPointer=@'
cmp mem.base($z31r_ctx_storage),0
je Z31R_FAIL_STORAGE
// FAdcDataType, FSampleRate and Float32 ring pointer must be readable.
mov $z31r_storage_last,$z31r_ctx_storage
add $z31r_storage_last,0x37
cmp $z31r_storage_last,$z31r_ctx_storage
jbe Z31R_FAIL_STORAGE
cmp mem.base($z31r_storage_last),mem.base($z31r_ctx_storage)
jne Z31R_FAIL_STORAGE
'@
$newPointer=$newPointer.TrimEnd([char[]]"`r`n")
$oldType="cmp dword:[`$z31r_ctx_storage+0x0C],0x1`njne Z31R_FAIL_STORAGE"
$newType=@'
// Original _Unit115: 007D0A04..2F uses code 0 for Float32, code 2 for byte ring.
log "Z31R_B_STORAGE_PROBE: PTR={p:$z31r_ctx_storage} FAdcDataType={x:dword:[$z31r_ctx_storage+0x0C]} Fs={x:dword:[$z31r_ctx_storage+0x18]}"
cmp dword:[$z31r_ctx_storage+0x0C],0x0
jne Z31R_FAIL_STORAGE_TYPE
'@
$newType=$newType.TrimEnd([char[]]"`r`n")
$oldFail='log "Z31R_FAIL_STORAGE: invalid storage pointer or FAdcDataType not 1 (float ring)."'
$newFail=@'
log "Z31R_FAIL_STORAGE: invalid storage pointer or missing Float32 ring; check EBP-4 and memory region."
jmp Z31R_ABORT
Z31R_FAIL_STORAGE_TYPE:
log "Z31R_FAIL_STORAGE_TYPE: Float32 storage must be type0 in original _Unit115; byte rings are type2. Do NOT force the type."
'@
$newFail=$newFail.TrimEnd([char[]]"`r`n")
# Only known, original generated v1.4 code is eligible for a surgical update.
foreach ($piece in @($oldPointer,$oldType,$oldFail)) {
    if ([regex]::Matches($original,[regex]::Escape($piece)).Count -ne 1) {
        throw 'Expected exactly one historical v1.4 storage guard; cannot safely patch.'
    }
}
$updated=$original.Replace($oldPointer,$newPointer).Replace($oldType,$newType).Replace($oldFail,$newFail)
if ($updated -eq $original -or $updated.Contains($oldType) -or $updated.Contains($oldFail)) {
    throw 'Unexpected patch result; no changes written.'
}
$updated=$updated.Replace('// Z31R V1.3 RESUME B', '// Z31R V1.5 RESUME B')
$updated=$updated.Replace('// Z31R V1.4 RESUME B', '// Z31R V1.5 RESUME B')
if ($updated -notmatch 'Z31R_B_STORAGE_PROBE' -or $updated -notmatch 'Z31R_FAIL_STORAGE_TYPE:') {
    throw 'Missing newly required source-derived diagnostic guard.'
}
# Preserve all previously captured B/A measurements and B failure evidence.
foreach ($logname in @('capture_log_b_snapshot.txt','capture_b.log')) {
    $src=Join-Path $folder $logname
    if (Test-Path -LiteralPath $src -PathType Leaf) {
        $safe=Join-Path $folder ($logname+'.before_storage_fix')
        if (Test-Path -LiteralPath $safe) { throw "Log backup already exists: $safe" }
        Copy-Item -LiteralPath $src -Destination $safe -ErrorAction Stop
    }
}
Copy-Item -LiteralPath $script -Destination $backup -ErrorAction Stop
[System.IO.File]::WriteAllText($script,$updated,[System.Text.Encoding]::ASCII)
$cfg.script_b_sha256=(Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
$cfg | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $config -Encoding UTF8
if ($cfg.script_b_sha256 -ne (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()) {
    throw 'Post-patch B SHA256 mismatch; keep backup and do not resume.'
}
Write-Host 'Z31R_STORAGE_PATCH_OK: existing B now checks original Float32 type0; type2 stays unsupported.'
Write-Host 'Original B backup:' $backup
Write-Host 'If original x32dbg is STILL PAUSED at EIP=007D14AA with [EBX+8]=00000014:'
Write-Host ('scriptexec "'+$script+'"')
