[CmdletBinding()]
param(
    [switch]$NoOpen
)

$ErrorActionPreference = 'Stop'
$DashboardUrl = 'http://127.0.0.1:4409/'

function Get-DashboardStatus {
    try {
        $request = [Net.HttpWebRequest]::Create($DashboardUrl)
        $request.Method = 'GET'
        $request.AllowAutoRedirect = $false
        $request.Timeout = 2000
        $request.ReadWriteTimeout = 2000
        $request.UseDefaultCredentials = $false
        $response = $request.GetResponse()
        try { return [int]$response.StatusCode }
        finally { $response.Dispose() }
    }
    catch [Net.WebException] {
        if ($_.Exception.Response) {
            try { return [int]$_.Exception.Response.StatusCode }
            finally { $_.Exception.Response.Dispose() }
        }
        return 0
    }
}

function Show-LauncherError {
    param([Parameter(Mandatory = $true)][string]$Message)

    Add-Type -AssemblyName PresentationFramework
    [void][Windows.MessageBox]::Show(
        $Message,
        'K1 Max Control',
        [Windows.MessageBoxButton]::OK,
        [Windows.MessageBoxImage]::Error
    )
}

try {
    $status = Get-DashboardStatus
    $source = 'existing-tunnel'
    if ($status -ne 401) {
        $ssh = Get-Command 'ssh.exe' -ErrorAction Stop
        $arguments = @(
            '-N',
            '-L', '127.0.0.1:4409:127.0.0.1:4409',
            '-o', 'ExitOnForwardFailure=yes',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ServerAliveCountMax=3',
            '-o', 'BatchMode=yes',
            'k1max-root'
        )
        $tunnel = Start-Process `
            -FilePath $ssh.Source `
            -ArgumentList $arguments `
            -PassThru `
            -WindowStyle Hidden
        $source = "new-tunnel:$($tunnel.Id)"

        foreach ($attempt in 1..40) {
            Start-Sleep -Milliseconds 250
            $status = Get-DashboardStatus
            if ($status -eq 401) { break }
            if ($tunnel.HasExited) { break }
        }
    }

    if ($status -ne 401) {
        throw "Le tunnel SSH n'a pas atteint Mainsail (HTTP $status). Verifie que l'imprimante est allumee et joignable."
    }

    if ($NoOpen) {
        Write-Output "LAUNCHER_PREFLIGHT_OK source=$source http=401"
        exit 0
    }
    Start-Process $DashboardUrl
}
catch {
    Show-LauncherError $_.Exception.Message
    exit 1
}
