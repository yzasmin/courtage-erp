# Capture la fenetre d'un processus (par defaut Power BI Desktop) dans un fichier PNG.
# Usage : .\scripts\capturer_fenetre.ps1 -Sortie docs\captures\08-powerbi-synthese.png [-Processus PBIDesktop]
param(
    [Parameter(Mandatory = $true)][string]$Sortie,
    [string]$Processus = "PBIDesktop",
    # Clic prealable, en pixels relatifs a la fenetre : "x,y". Sert a changer de page du rapport.
    [string]$Clic = ""
)

Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Fenetre {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
}
"@
[Fenetre]::SetProcessDPIAware() | Out-Null
$p = Get-Process $Processus | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { throw "Aucune fenetre pour le processus $Processus." }
[Fenetre]::ShowWindow($p.MainWindowHandle, 9) | Out-Null   # restaure si reduite
[Fenetre]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 1500
$r = New-Object Fenetre+RECT
[Fenetre]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
if ($Clic -ne "") {
    $xy = $Clic.Split(",")
    [Fenetre]::SetCursorPos($r.Left + [int]$xy[0], $r.Top + [int]$xy[1]) | Out-Null
    Start-Sleep -Milliseconds 300
    [Fenetre]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)   # bouton gauche enfonce
    [Fenetre]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)   # bouton gauche relache
    Start-Sleep -Milliseconds 3500
}
$largeur = $r.Right - $r.Left
$hauteur = $r.Bottom - $r.Top
$image = New-Object System.Drawing.Bitmap $largeur, $hauteur
$g = [System.Drawing.Graphics]::FromImage($image)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, $image.Size)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Sortie) | Out-Null
$image.Save((Join-Path (Get-Location) $Sortie), [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $image.Dispose()
Write-Output "Capture : $Sortie ($largeur x $hauteur)"
