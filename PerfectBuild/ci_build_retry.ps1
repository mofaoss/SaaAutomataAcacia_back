param(
    [Parameter(Mandatory = $true)]
    [string]$CondaEnvName
)

$maxRetries = 1
$success = $false

for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
    Write-Host ("===== Build attempt {0}/{1} =====" -f $attempt, $maxRetries)
    conda run -n $CondaEnvName python .\PerfectBuild\build.py --n

    if ($LASTEXITCODE -eq 0) {
        $success = $true
        break
    }

    if ($attempt -lt $maxRetries) {
        Write-Warning "Build failed, installing extra dependencies and retrying..."
        conda run -n $CondaEnvName pip install --no-input --upgrade nuitka ordered-set zstandard pyinstaller
        Start-Sleep -Seconds 20
    }
}

if (-not $success) {
    throw "Build failed after $maxRetries attempts"
}
