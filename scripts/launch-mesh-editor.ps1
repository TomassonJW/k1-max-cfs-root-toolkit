[CmdletBinding()]
param(
    [switch]$NoOpen
)

$ErrorActionPreference = 'Stop'
$EditorUrl = 'http://127.0.0.1:7130/'
$SshHost = 'k1max-root'
# Le serveur de l'editeur ne survit pas a un redemarrage de l'imprimante.
# Le lanceur le relance lui-meme plutot que de renvoyer vers une ligne de commande.
$RemoteStart = "cd /usr/data/k1-control-mesh-editor && setsid nohup python3 -u server.py 7130 > /tmp/mesh-editor.log 2>&1 < /dev/null &"

function Get-EditorStatus {
    try {
        $request = [Net.HttpWebRequest]::Create($EditorUrl)
        $request.Method = 'GET'
        $request.AllowAutoRedirect = $false
        $request.Timeout = 3000
        $request.ReadWriteTimeout = 3000
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

# Windows laisse deux ssh ecouter le meme port local sans erreur : sans ce test,
# chaque lancement fait sur un serveur distant mort empilerait un tunnel de plus.
function Test-LocalForward {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $connect = $client.BeginConnect('127.0.0.1', 7130, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(1000)) { return $false }
        $client.EndConnect($connect)
        return $true
    }
    catch { return $false }
    finally { $client.Close() }
}

function Wait-LocalForward {
    param([int]$Attempts = 20)

    foreach ($attempt in 1..$Attempts) {
        Start-Sleep -Milliseconds 250
        if (Test-LocalForward) { return $true }
    }
    return Test-LocalForward
}

function Wait-EditorReady {
    param([int]$Attempts = 20)

    foreach ($attempt in 1..$Attempts) {
        Start-Sleep -Milliseconds 250
        $status = Get-EditorStatus
        if ($status -eq 200) { return $status }
    }
    return Get-EditorStatus
}

function Show-LauncherError {
    param([Parameter(Mandatory = $true)][string]$Message)

    Add-Type -AssemblyName PresentationFramework
    [void][Windows.MessageBox]::Show(
        $Message,
        'K1 Max - Editeur de maillage',
        [Windows.MessageBoxButton]::OK,
        [Windows.MessageBoxImage]::Error
    )
}

try {
    $status = Get-EditorStatus
    $source = 'existing-tunnel'

    if ($status -ne 200 -and -not (Test-LocalForward)) {
        $ssh = Get-Command 'ssh.exe' -ErrorAction Stop
        $arguments = @(
            '-N',
            '-L', '127.0.0.1:7130:127.0.0.1:7130',
            '-o', 'ExitOnForwardFailure=yes',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ServerAliveCountMax=3',
            '-o', 'BatchMode=yes',
            $SshHost
        )
        $tunnel = Start-Process `
            -FilePath $ssh.Source `
            -ArgumentList $arguments `
            -PassThru `
            -WindowStyle Hidden
        $source = "new-tunnel:$($tunnel.Id)"
        if (Wait-LocalForward) { $status = Wait-EditorReady -Attempts 4 }
    }

    # Tunnel debout mais rien derriere : l'imprimante a redemarre depuis la
    # derniere edition, le serveur est mort et se relance a distance.
    if ($status -ne 200) {
        $ssh = Get-Command 'ssh.exe' -ErrorAction Stop
        & $ssh.Source '-o' 'BatchMode=yes' '-o' 'ConnectTimeout=8' $SshHost $RemoteStart | Out-Null
        $source = "$source+restarted"
        $status = Wait-EditorReady
    }

    if ($status -ne 200) {
        throw "L'editeur de maillage ne repond pas (HTTP $status). Verifie que l'imprimante est allumee et joignable."
    }

    if ($NoOpen) {
        Write-Output "MESH_EDITOR_PREFLIGHT_OK source=$source http=$status url=$EditorUrl"
        exit 0
    }
    Start-Process $EditorUrl
}
catch {
    Show-LauncherError $_.Exception.Message
    exit 1
}
