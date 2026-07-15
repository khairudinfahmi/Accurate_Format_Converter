$ErrorActionPreference = "Stop"

Write-Host "1. Membersihkan sisa build lama..."
Remove-Item build, dist, Output -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path Output | Out-Null

Write-Host "2. Kompilasi Aplikasi (Main App & Launcher)..."
& .\.venv\Scripts\python.exe -m PyInstaller accurate_format_converter.spec --clean
if ($LASTEXITCODE -ne 0) { throw "Gagal kompilasi Aplikasi" }

Write-Host "3. Menyalin version.txt..."
Copy-Item version.txt dist\Accurate_Format_Converter\version.txt -Force

Write-Host "4. Menandatangani File Eksekutabel secara Digital (Tahap 1)..."
$pfxPath = "assets\khairudinfahmi.pfx"
$password = "rensa2026"
$securePassword = ConvertTo-SecureString -String $password -Force -AsPlainText
$cert = Import-PfxCertificate -FilePath $pfxPath -CertStoreLocation Cert:\CurrentUser\My -Password $securePassword
Set-AuthenticodeSignature -FilePath "dist\Accurate_Format_Converter\Accurate_Format_Converter.exe" -Certificate $cert -TimestampServer "http://timestamp.digicert.com"
Set-AuthenticodeSignature -FilePath "dist\Accurate_Format_Converter\Launcher.exe" -Certificate $cert -TimestampServer "http://timestamp.digicert.com"

Write-Host "5. Membuat Installer dengan Inno Setup..."
$iscc = (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
if (!$iscc) {
    $possiblePaths = @(
        "C:\Users\Dina\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "C:\Users\Administrator\AppData\Local\Programs\Antigravity IDE\resources\app\node_modules\innosetup\bin\ISCC.exe"
    )
    foreach ($p in $possiblePaths) {
        if (Test-Path $p) { $iscc = $p; break }
    }
}
if (!$iscc -or !(Test-Path $iscc)) {
    $found = Get-ChildItem -Path $env:LOCALAPPDATA, "C:\Program Files (x86)", "C:\Program Files" -Filter "ISCC.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    if ($found) { $iscc = $found } else { throw "ISCC.exe tidak ditemukan di sistem ini. Harap install Inno Setup 6." }
}
Write-Host "Menggunakan ISCC dari: $iscc"
& $iscc accurate_converter_installer.iss
if ($LASTEXITCODE -ne 0) { throw "Gagal membuat installer" }

Write-Host "6. Menandatangani Installer Final (Tahap 2)..."
Get-ChildItem -Path "Output" -Filter "*.exe" | ForEach-Object {
    Write-Host "Signing installer: $($_.Name)..."
    Set-AuthenticodeSignature -FilePath $_.FullName -Certificate $cert -TimestampServer "http://timestamp.digicert.com"
}

Write-Host "=== BUILD SELESAI DENGAN SUKSES ==="
