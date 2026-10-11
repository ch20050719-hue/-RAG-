$ErrorActionPreference = 'Stop'

$productKey = $env:GIZWITS_PRODUCT_KEY
$productSecret = $env:GIZWITS_PRODUCT_SECRET

if ($productKey -notmatch '^[A-Za-z0-9]{32}$') {
    throw 'GIZWITS_PRODUCT_KEY must contain exactly 32 letters or digits.'
}
if ($productSecret -notmatch '^[A-Za-z0-9]{32}$') {
    throw 'GIZWITS_PRODUCT_SECRET must contain exactly 32 letters or digits.'
}

$outputPath = Join-Path $PSScriptRoot 'gizwits_credentials.h'
$header = @"
#ifndef GIZWITS_CREDENTIALS_H
#define GIZWITS_CREDENTIALS_H

#define PRODUCT_KEY "$productKey"
#define PRODUCT_SECRET "$productSecret"

typedef char gizwits_product_key_must_be_32_chars[(sizeof(PRODUCT_KEY) == 33u) ? 1 : -1];
typedef char gizwits_product_secret_must_be_32_chars[(sizeof(PRODUCT_SECRET) == 33u) ? 1 : -1];

#endif
"@
[System.IO.File]::WriteAllText($outputPath, $header + [System.Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Output 'Created local Gizwits credentials header.'
