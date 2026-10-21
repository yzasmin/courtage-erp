# Execute les requetes DAX de powerbi/controles/ sur le modele ouvert dans Power BI Desktop
# et ecrit les resultats dans results/powerbi/*.csv.
#
# Pre-requis : powerbi/Pilotage-Courtage.pbip est ouvert dans Power BI Desktop. Le moteur local
# (msmdsrv.exe) ecoute sur un port dynamique, retrouve ici par son processus.
#
# Option -Actualiser : lance un rafraichissement complet du modele par une commande TMSL, ce qui
# evite de cliquer sur Accueil > Actualiser. Les donnees sont lues dans powerbi/donnees (parametre
# DossierDonnees du modele).
#
# Usage (PowerShell, depuis la racine du depot) : .\scripts\executer_dax.ps1 [-Actualiser]
param([switch]$Actualiser)

$racine = Split-Path -Parent $PSScriptRoot
$sortie = Join-Path $racine "results\powerbi"
New-Item -ItemType Directory -Force -Path $sortie | Out-Null

$bin = (Get-AppxPackage -Name Microsoft.MicrosoftPowerBIDesktop).InstallLocation + "\bin"
if (-not (Test-Path "$bin\Microsoft.PowerBI.AdomdClient.dll")) {
    throw "Client ADOMD introuvable : Power BI Desktop (version Microsoft Store) n'est pas installe."
}
Add-Type -Path "$bin\Microsoft.PowerBI.AdomdClient.dll"

$moteur = Get-Process msmdsrv -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $moteur) { throw "Aucun moteur Analysis Services : ouvrir powerbi/Pilotage-Courtage.pbip dans Power BI Desktop." }
$port = (Get-NetTCPConnection -OwningProcess $moteur.Id |
         Where-Object { $_.State -eq "Listen" -and $_.LocalAddress -eq "127.0.0.1" } |
         Select-Object -First 1).LocalPort

$connexion = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
$connexion.Open()
Write-Output "Modele : $($connexion.Database) (port $port)"

if ($Actualiser) {
    $base = $connexion.Database
    $tmsl = '{"refresh":{"type":"full","objects":[{"database":"' + $base + '"}]}}'
    $commande = $connexion.CreateCommand()
    $commande.CommandText = $tmsl
    $commande.ExecuteNonQuery() | Out-Null
    Write-Output "Actualisation complete du modele terminee."
}

foreach ($requete in Get-ChildItem (Join-Path $racine "powerbi\controles") -Filter "*.dax" | Sort-Object Name) {
    $commande = $connexion.CreateCommand()
    $commande.CommandText = Get-Content -Raw -Encoding UTF8 $requete.FullName
    # L'adaptateur remplit la table sans appliquer de contraintes : certaines mesures renvoient BLANK.
    $adaptateur = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdDataAdapter($commande)
    $table = New-Object System.Data.DataTable
    $adaptateur.Fill($table) | Out-Null
    $cible = Join-Path $sortie ($requete.BaseName + ".csv")
    $table | Export-Csv -Path $cible -NoTypeInformation -Encoding UTF8
    Write-Output "$($requete.Name) : $($table.Rows.Count) lignes -> results/powerbi/$($requete.BaseName).csv"
}
$connexion.Close()
