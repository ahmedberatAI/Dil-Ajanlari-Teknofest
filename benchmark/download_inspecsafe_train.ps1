param(
    [ValidateRange(1, 16)]
    [int]$Throttle = 4,
    [ValidateRange(1, 50)]
    [int]$MaxAttempts = 20
)

$ErrorActionPreference = 'Stop'
$total = [int64]17886855594
$chunkSize = [int64](256MB)
$expectedSha256 = 'ef03b9eb2f9bd91b03f203a8e6cfcc3464cb0d9f0215349a80ad95281fa88cd6'
$url = 'https://huggingface.co/datasets/Tetrabot2026/InspecSafe-V1/resolve/f3cb7d3e7827c1afc1c5bfd0524257984bba46ab/train.tar.gz?download=true'
$safePrefixLength = [int64]6312513536

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$downloadRoot = [IO.Path]::GetFullPath((Join-Path $root 'data\external\inspecsafe_v1\ranges_v3'))
$allowedPrefix = $root.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $downloadRoot.StartsWith($allowedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Download target workspace disinda: $downloadRoot"
}
[IO.Directory]::CreateDirectory($downloadRoot) | Out-Null

$chunks = for ($index = 0; $index * $chunkSize -lt $total; $index++) {
    $start = [int64]$index * $chunkSize
    $end = [Math]::Min($total - 1, $start + $chunkSize - 1)
    [pscustomobject]@{
        Index = $index
        Start = $start
        End = $end
        Length = $end - $start + 1
        File = Join-Path $downloadRoot ('chunk_{0:D3}.bin' -f $index)
        Header = Join-Path $downloadRoot ('chunk_{0:D3}.headers' -f $index)
        Seed = Join-Path $downloadRoot ('chunk_{0:D3}.seed.json' -f $index)
    }
}

function Test-HttpRangeFile($chunk) {
    if (-not (Test-Path -LiteralPath $chunk.File -PathType Leaf)) { return $false }
    if (-not (Test-Path -LiteralPath $chunk.Header -PathType Leaf)) { return $false }
    if ((Get-Item -LiteralPath $chunk.File).Length -ne $chunk.Length) { return $false }
    $raw = Get-Content -LiteralPath $chunk.Header -Raw
    $match = [regex]::Match($raw, '(?im)^content-range:\s*([^\r\n]+)')
    $expectedRange = "bytes $($chunk.Start)-$($chunk.End)/$total"
    return ($raw -match '(?im)^HTTP/\S+\s+206\b') -and
        $match.Success -and ($match.Groups[1].Value.Trim() -ieq $expectedRange)
}

function Get-RangeSha256([string]$path, [int64]$offset, [int64]$length) {
    $stream = [IO.File]::OpenRead($path)
    $hash = [Security.Cryptography.SHA256]::Create()
    try {
        $stream.Position = $offset
        $buffer = New-Object byte[] (4MB)
        $remaining = $length
        while ($remaining -gt 0) {
            $want = [int][Math]::Min($buffer.Length, $remaining)
            $read = $stream.Read($buffer, 0, $want)
            if ($read -le 0) { throw 'Seed prefix beklenmedik bicimde bitti' }
            [void]$hash.TransformBlock($buffer, 0, $read, $null, 0)
            $remaining -= $read
        }
        [void]$hash.TransformFinalBlock([byte[]]::new(0), 0, 0)
        return [Convert]::ToHexString($hash.Hash).ToLowerInvariant()
    }
    finally {
        $hash.Dispose()
        $stream.Dispose()
    }
}

function Copy-FileRange([string]$source, [int64]$offset, [int64]$length,
                        [string]$destination) {
    $input = [IO.File]::OpenRead($source)
    $output = [IO.File]::Open($destination, [IO.FileMode]::Create,
        [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $input.Position = $offset
        $buffer = New-Object byte[] (4MB)
        $remaining = $length
        while ($remaining -gt 0) {
            $want = [int][Math]::Min($buffer.Length, $remaining)
            $read = $input.Read($buffer, 0, $want)
            if ($read -le 0) { throw 'Seed prefix kopyalanirken erken EOF' }
            $output.Write($buffer, 0, $read)
            $remaining -= $read
        }
    }
    finally {
        $output.Dispose()
        $input.Dispose()
    }
}

# Onceki tek-baglanti kosusundan kalan ilk 6.312.513.536 bayt kesintisiz ve
# sabit revizyondandir. Yeniden kullanmadan once uc ayri resmi HTTP range ile
# (bas, bitisik ve aralikli blok) bayt hash esitligi zorunludur.
$prefixPath = [IO.Path]::GetFullPath((Join-Path $root 'data\external\inspecsafe_v1\train.tar.gz'))
$witnessIndices = @(0, 1, 3)
$canSeed = (Test-Path -LiteralPath $prefixPath -PathType Leaf) -and
    ((Get-Item -LiteralPath $prefixPath).Length -ge $safePrefixLength)
foreach ($index in $witnessIndices) {
    $chunk = $chunks[$index]
    if (-not (Test-HttpRangeFile $chunk)) { $canSeed = $false; break }
    $prefixHash = Get-RangeSha256 $prefixPath $chunk.Start $chunk.Length
    $rangeHash = (Get-FileHash -LiteralPath $chunk.File -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($prefixHash -ne $rangeHash) { $canSeed = $false; break }
}
if ($canSeed) {
    foreach ($chunk in $chunks) {
        if ($chunk.End + 1 -gt $safePrefixLength) { continue }
        if (Test-HttpRangeFile $chunk) { continue }
        Copy-FileRange $prefixPath $chunk.Start $chunk.Length $chunk.File
        $chunkHash = (Get-FileHash -LiteralPath $chunk.File -Algorithm SHA256).Hash.ToLowerInvariant()
        $seed = [ordered]@{
            source = 'verified_sequential_prefix'
            source_path = $prefixPath
            safe_prefix_length = $safePrefixLength
            witness_http_range_indices = $witnessIndices
            range = "bytes $($chunk.Start)-$($chunk.End)/$total"
            length = $chunk.Length
            sha256 = $chunkHash
        }
        [IO.File]::WriteAllText($chunk.Seed,
            ($seed | ConvertTo-Json -Depth 3), [Text.UTF8Encoding]::new($false))
        Write-Host ("[SEED {0:D3}] {1:N0} bayt" -f $chunk.Index, $chunk.Length)
    }
}
else {
    Write-Warning 'Guvenli prefix witness dogrulamasi gecmedi; seed kullanilmadi'
}

Write-Host "InspecSafe train: $($chunks.Count) kalici range, throttle=$Throttle"
$results = $chunks | ForEach-Object -Parallel {
    $chunk = $_
    $expectedRange = "bytes $($chunk.Start)-$($chunk.End)/$using:total"

    function Test-RangeFile([string]$file, [string]$header, [string]$seed,
                            [int64]$length, [string]$range) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return $false }
        if ((Get-Item -LiteralPath $file).Length -ne $length) { return $false }
        if (Test-Path -LiteralPath $header -PathType Leaf) {
            $raw = Get-Content -LiteralPath $header -Raw
            $match = [regex]::Match($raw, '(?im)^content-range:\s*([^\r\n]+)')
            if (($raw -match '(?im)^HTTP/\S+\s+206\b') -and
                $match.Success -and ($match.Groups[1].Value.Trim() -ieq $range)) {
                return $true
            }
        }
        if ($seed -and (Test-Path -LiteralPath $seed -PathType Leaf)) {
            try {
                $meta = Get-Content -LiteralPath $seed -Raw | ConvertFrom-Json
                $actualHash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
                return $meta.source -eq 'verified_sequential_prefix' -and
                    [int64]$meta.length -eq $length -and $meta.range -eq $range -and
                    $meta.sha256 -eq $actualHash
            }
            catch { return $false }
        }
        return $false
    }

    if (Test-RangeFile $chunk.File $chunk.Header $chunk.Seed $chunk.Length $expectedRange) {
        Write-Host ("[MEVCUT {0:D3}] {1:N0} bayt" -f $chunk.Index, $chunk.Length)
        return [pscustomobject]@{ Index = $chunk.Index; Ok = $true; Attempts = 0 }
    }

    $tmp = $chunk.File + '.tmp'
    $headerTmp = $chunk.Header + '.tmp'
    for ($attempt = 1; $attempt -le $using:MaxAttempts; $attempt++) {
        $range = "$($chunk.Start)-$($chunk.End)"
        $arguments = @(
            '-L', '--fail', '--silent', '--show-error',
            '--connect-timeout', '30', '--max-time', '900',
            '--speed-time', '90', '--speed-limit', '1024',
            '--header', 'Accept-Encoding: identity',
            '--range', $range,
            '--dump-header', $headerTmp,
            '--output', $tmp,
            $using:url
        )
        & curl.exe @arguments
        $exitCode = $LASTEXITCODE
        if ($exitCode -eq 0 -and
            (Test-RangeFile $tmp $headerTmp '' $chunk.Length $expectedRange)) {
            Move-Item -LiteralPath $tmp -Destination $chunk.File -Force
            Move-Item -LiteralPath $headerTmp -Destination $chunk.Header -Force
            Write-Host ("[TAMAM {0:D3}] deneme={1} {2:N0} bayt" -f
                $chunk.Index, $attempt, $chunk.Length)
            return [pscustomobject]@{
                Index = $chunk.Index; Ok = $true; Attempts = $attempt
            }
        }
        Write-Warning ("Range {0:D3} basarisiz: deneme={1}, curl={2}" -f
            $chunk.Index, $attempt, $exitCode)
        Start-Sleep -Seconds ([Math]::Min(20, 2 * $attempt))
    }
    return [pscustomobject]@{
        Index = $chunk.Index; Ok = $false; Attempts = $using:MaxAttempts
    }
} -ThrottleLimit $Throttle

$failed = @($results | Where-Object { -not $_.Ok })
if ($failed.Count -gt 0) {
    throw "Tamamlanamayan range: $($failed.Index -join ', ')"
}

$target = [IO.Path]::GetFullPath((Join-Path $downloadRoot 'train.ranges.tar.gz'))
if (-not $target.StartsWith($downloadRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) +
        [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Assembly target range dizini disinda: $target"
}

$output = [IO.File]::Open($target, [IO.FileMode]::Create, [IO.FileAccess]::Write,
    [IO.FileShare]::None)
try {
    foreach ($chunk in ($chunks | Sort-Object Index)) {
        $input = [IO.File]::OpenRead($chunk.File)
        try {
            $input.CopyTo($output, 4MB)
        }
        finally {
            $input.Dispose()
        }
    }
}
finally {
    $output.Dispose()
}

$actualSize = (Get-Item -LiteralPath $target).Length
if ($actualSize -ne $total) {
    throw "Assembly boyutu yanlis: $actualSize != $total"
}
$actualSha256 = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha256 -ne $expectedSha256) {
    throw "Assembly SHA-256 yanlis: $actualSha256"
}

Write-Host "TRAIN DOWNLOAD PASS"
Write-Host "PATH=$target"
Write-Host "SIZE=$actualSize"
Write-Host "SHA256=$actualSha256"
