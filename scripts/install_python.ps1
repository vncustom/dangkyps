# Tai va cai Python cho TAT CA nguoi dung (can quyen Administrator). Dung boi setup.bat.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $ver = '3.12.8'
    $url = "https://www.python.org/ftp/python/$ver/python-$ver-amd64.exe"
    $out = Join-Path $env:TEMP "python-$ver-amd64.exe"
    Write-Host "      Dang tai $url"
    Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
    Write-Host "      Dang cai Python $ver (vai phut, vui long cho)..."
    $p = Start-Process -FilePath $out -ArgumentList '/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_test=0', 'Include_launcher=0' -Wait -PassThru
    Remove-Item $out -Force -ErrorAction SilentlyContinue
    if ($p.ExitCode -ne 0) { throw "Trinh cai Python tra ma loi $($p.ExitCode)" }
} catch {
    Write-Host "      [loi] $($_.Exception.Message)"
    exit 1
}
