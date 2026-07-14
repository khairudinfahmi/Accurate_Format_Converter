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
$iscc = "C:\Users\Dina\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
& $iscc accurate_converter_installer.iss
if ($LASTEXITCODE -ne 0) { throw "Gagal membuat installer" }

Write-Host "6. Menandatangani Installer Final (Tahap 2)..."
Set-AuthenticodeSignature -FilePath "Output\Accurate_Converter_Setup_v4.1.exe" -Certificate $cert -TimestampServer "http://timestamp.digicert.com"

Write-Host "=== BUILD SELESAI DENGAN SUKSES ==="
