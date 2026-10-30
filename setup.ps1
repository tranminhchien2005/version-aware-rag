param([string]$Python = "py")
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if ($Python -eq 'py') {
    & py -3.11 -c "import sys; assert sys.version_info >= (3,11)"
    if ($LASTEXITCODE -ne 0) { throw 'Cần Python 3.11+. Cài từ python.org hoặc truyền -Python đường_dẫn_python.exe.' }
    & py -3.11 -m venv .venv
} else {
    & $Python -c "import sys; assert sys.version_info >= (3,11)"
    if ($LASTEXITCODE -ne 0) { throw 'Trình thông dịch phải là Python 3.11 trở lên.' }
    & $Python -m venv .venv
}
if ($LASTEXITCODE -ne 0) { throw 'Không tạo được .venv.' }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Không cập nhật được pip. Kiểm tra kết nối mạng.' }
$taskRequirements = if (Test-Path -LiteralPath 'requirements.lock.txt') { 'requirements.lock.txt' } else { 'requirements.txt' }
& .\.venv\Scripts\python.exe -m pip install -r $taskRequirements
if ($LASTEXITCODE -ne 0) { throw 'Cài thư viện chưa hoàn tất.' }
& .\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Các thư viện chưa tương thích.' }
& .\.venv\Scripts\python.exe -m pip freeze | Set-Content -Encoding utf8 requirements.lock.txt
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
Write-Host 'Đã cài môi trường. Điền .env trên máy; không chia sẻ API key.'
& .\.venv\Scripts\python.exe -m scripts.check_environment
