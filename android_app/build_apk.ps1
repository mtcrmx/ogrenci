param(
    [string]$SdkRoot = "C:\Program Files (x86)\Android\android-sdk",
    [string]$BuildToolsVersion = "35.0.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildDir = Join-Path $Root "build"
$Package = "com.akademipuan.takip"
$PackagePath = "com\akademipuan\takip"
$BuildTools = Join-Path $SdkRoot "build-tools\$BuildToolsVersion"
$PlatformJar = Join-Path $SdkRoot "platforms\android-35\android.jar"
$Aapt2 = Join-Path $BuildTools "aapt2.exe"
$Aapt = Join-Path $BuildTools "aapt.exe"
$D8 = Join-Path $BuildTools "d8.bat"
$ZipAlign = Join-Path $BuildTools "zipalign.exe"
$ApkSigner = Join-Path $BuildTools "apksigner.bat"
$JavaHomeCandidates = @(
    "C:\Program Files\Android\Android Studio1\jbr",
    "C:\Program Files\Android\Android Studio\jbr",
    "C:\Program Files\Android\jdk",
    "C:\Program Files (x86)\Android\openjdk"
)
$JavaHome = $JavaHomeCandidates | Where-Object { Test-Path (Join-Path $_ "bin\javac.exe") } | Select-Object -First 1
if (-not $JavaHome) { throw "JDK bulunamadi. Android Studio icindeki JDK veya javac gerekli." }
$Javac = Join-Path $JavaHome "bin\javac.exe"
$Keytool = Join-Path $JavaHome "bin\keytool.exe"
$env:JAVA_HOME = $JavaHome
$env:PATH = (Join-Path $JavaHome "bin") + ";" + $env:PATH

foreach ($Tool in @($Aapt2, $Aapt, $D8, $ZipAlign, $ApkSigner, $PlatformJar, $Javac, $Keytool)) {
    if (-not (Test-Path $Tool)) { throw "Eksik arac: $Tool" }
}

$ResolvedRoot = [System.IO.Path]::GetFullPath($Root)
$ResolvedBuild = [System.IO.Path]::GetFullPath($BuildDir)
if (-not $ResolvedBuild.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Guvenlik icin build klasoru proje disinda olamaz: $ResolvedBuild"
}
if (Test-Path $BuildDir) {
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path `
    (Join-Path $BuildDir "compiled"), `
    (Join-Path $BuildDir "gen"), `
    (Join-Path $BuildDir "classes"), `
    (Join-Path $BuildDir "dex"), `
    (Join-Path $BuildDir "out") | Out-Null

& $Aapt2 compile --dir (Join-Path $Root "res") -o (Join-Path $BuildDir "compiled")
if ($LASTEXITCODE -ne 0) { throw "aapt2 compile basarisiz." }

$FlatFiles = Get-ChildItem -Path (Join-Path $BuildDir "compiled") -Filter "*.flat" | ForEach-Object { $_.FullName }
& $Aapt2 link `
    -o (Join-Path $BuildDir "unsigned.apk") `
    -I $PlatformJar `
    --manifest (Join-Path $Root "AndroidManifest.xml") `
    --java (Join-Path $BuildDir "gen") `
    --min-sdk-version 23 `
    --target-sdk-version 35 `
    --version-code 2 `
    --version-name "1.1" `
    $FlatFiles
if ($LASTEXITCODE -ne 0) { throw "aapt2 link basarisiz." }

$SourceFiles = @(
    (Join-Path $Root "src\$PackagePath\MainActivity.java"),
    (Join-Path $Root "src\$PackagePath\VeliDinleServisi.java"),
    (Join-Path $Root "src\$PackagePath\BootReceiver.java"),
    (Join-Path $BuildDir "gen\$PackagePath\R.java")
)
& $Javac -encoding UTF-8 -source 1.8 -target 1.8 -bootclasspath $PlatformJar -d (Join-Path $BuildDir "classes") $SourceFiles
if ($LASTEXITCODE -ne 0) { throw "javac basarisiz." }

$ClassFiles = Get-ChildItem -Path (Join-Path $BuildDir "classes") -Recurse -Filter "*.class" | ForEach-Object { $_.FullName }
if (-not $ClassFiles) { throw "Derlenmis .class dosyasi bulunamadi." }
& $D8 --min-api 23 --lib $PlatformJar --output (Join-Path $BuildDir "dex") $ClassFiles
if ($LASTEXITCODE -ne 0) { throw "d8 basarisiz." }

$UnsignedWithDex = Join-Path $BuildDir "unsigned-with-dex.apk"
Copy-Item -LiteralPath (Join-Path $BuildDir "unsigned.apk") -Destination $UnsignedWithDex -Force
Push-Location (Join-Path $BuildDir "dex")
try {
    & $Aapt add $UnsignedWithDex "classes.dex"
    if ($LASTEXITCODE -ne 0) { throw "aapt add basarisiz." }
} finally {
    Pop-Location
}

$Aligned = Join-Path $BuildDir "out\AkademiPuan-unsigned-aligned.apk"
& $ZipAlign -f -p 4 $UnsignedWithDex $Aligned
if ($LASTEXITCODE -ne 0) { throw "zipalign basarisiz." }

$Keystore = Join-Path $BuildDir "debug.keystore"
& $Keytool -genkeypair -v `
    -keystore $Keystore `
    -storepass android `
    -alias androiddebugkey `
    -keypass android `
    -keyalg RSA `
    -keysize 2048 `
    -validity 10000 `
    -dname "CN=Android Debug,O=Android,C=US"
if ($LASTEXITCODE -ne 0) { throw "debug keystore olusturulamadi." }

$OutputApk = Join-Path $BuildDir "out\AkademiPuan-debug.apk"
& $ApkSigner sign `
    --ks $Keystore `
    --ks-pass pass:android `
    --key-pass pass:android `
    --out $OutputApk `
    $Aligned
if ($LASTEXITCODE -ne 0) { throw "apksigner sign basarisiz." }

& $ApkSigner verify --verbose $OutputApk
if ($LASTEXITCODE -ne 0) { throw "apksigner verify basarisiz." }

Write-Host "APK hazir: $OutputApk"
