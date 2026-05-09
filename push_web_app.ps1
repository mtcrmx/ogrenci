$ErrorActionPreference = "Stop"
$git = "C:\Users\METE\AppData\Local\GitHubDesktop\app-3.5.8\resources\app\git\cmd\git.exe"
if (-not (Test-Path $git)) {
    $found = Get-ChildItem "C:\Users\METE\AppData\Local\GitHubDesktop" -Recurse -Filter "git.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "\\git\\cmd\\git\.exe$" } |
        Select-Object -First 1
    if ($found) { $git = $found.FullName }
}
$repo = "C:\Users\METE\OneDrive\Belgeler\GitHub\ogrenci-takip"
$log = Join-Path $repo "_push_log.txt"
function Invoke-RepoGit {
    param([string[]]$CommandArgs)
    $out = & $git "-C" $repo @CommandArgs 2>&1 | Out-String
    $out | Out-File -FilePath $log -Append -Encoding utf8
    return $LASTEXITCODE
}
"" | Out-File -FilePath $log -Encoding utf8
Invoke-RepoGit @("status", "-sb")
Invoke-RepoGit @("add", "web_app.py")
Invoke-RepoGit @("commit", "-m", "fix(web_app): restore Flask <int:...> routes for Render")
Invoke-RepoGit @("push", "origin", "main")
"LASTEXIT=$LASTEXITCODE" | Out-File -FilePath $log -Append -Encoding utf8
