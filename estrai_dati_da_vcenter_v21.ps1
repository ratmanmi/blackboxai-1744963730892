# --------------------------------------------------------------
# Script PowerShell per estrarre informazioni delle VM dai vCenter
# Versione 1.5
# Autore: manganiello Francesco
# Data: 27/09/2024
# --------------------------------------------------------------

# Inizia la trascrizione per registrare l'output
$transcriptPath = "C:\temp\vcenter\script_transcript.txt"
Start-Transcript -Path $transcriptPath -Force

# Imposta la configurazione di PowerCLI per ignorare i certificati non validi
Write-Host "Configurazione di PowerCLI..."
Set-PowerCLIConfiguration -InvalidCertificateAction Ignore -Confirm:$false
Set-PowerCLIConfiguration -DefaultVIServerMode Multiple -Confirm:$false
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
if (-not (Get-Module -ListAvailable -Name ImportExcel)) {
    Write-Host "Modulo ImportExcel non trovato, installazione in corso..."
    Install-Module -Name ImportExcel -Force -Scope CurrentUser
} else {
    Write-Host "Modulo ImportExcel già installato."
}

# Carica i moduli necessari
Write-Host "Caricamento dei moduli necessari..."
Import-Module VMware.PowerCLI
Import-Module ImportExcel

# Percorso del file delle credenziali
$credentialFile = "C:\temp\vcenter\mysecurecred.xml"

# Se il file delle credenziali non esiste, chiedi di crearne uno nuovo
if (-not (Test-Path -Path $credentialFile)) {
    Write-Host "File delle credenziali non trovato: $credentialFile"
    $cred = Get-Credential
    $cred | Export-Clixml -Path $credentialFile
} else {
    # Recupera le credenziali dal file
    Write-Host "Recupero delle credenziali dal file: $credentialFile"
    try {
        $cred = Import-Clixml -Path $credentialFile
    } catch {
        Write-Warning "Errore nel leggere il file delle credenziali: $($_.Exception.Message)"
        $cred = Get-Credential
        $cred | Export-Clixml -Path $credentialFile
    }
}

# Lista di vCenter
$vCenters = @(
   # "mi-ber-vlvc03.fastcloud.fwb", "mi-ber-vlvc04.fastcloud.fwb", "mi-ber-vlvc06.fastcloud.fwb",
   # "mi-ber-vlvc07.fastcloud.fwb", "mi-ber-vlvc08.fastcloud.fwb", "mi-ber-vlvc09.fastcloud.fwb",
    #"mi-ber-vlvc10.fastcloud.fwb", "mi-ber-vlvc11.fastcloud.fwb", "mi-ber-vlvc12.fastcloud.fwb",
    "mi-ber-vlvc14.fastcloud.fwb", "mi-ber-vlvc15.fastcloud.fwb", "mi-ber-vlvc16.fastcloud.fwb"
    #"mi-ber-vlvc17.fastcloud.fwb", "mi-ber-vlvc18.fastcloud.fwb", "mi-ber-vlvc20.fastcloud.fwb",
    #"mi-ber-vlvc21.fastcloud.fwb", "mi-ber-vlvc22.fastcloud.fwb", "mi-ber-vlvc23.fastcloud.fwb",
    #"mi-ber-vlvc25.fastcloud.fwb", "mi-ber-vlvc30.fastcloud.fwb", "mi-ber-vlvc40.fastcloud.fwb",
    #"mi-ber-vlvc60.fastcloud.fwb"
)

# Directory di output
$outputDirectory = "C:\temp\vcenter"
if (-not (Test-Path -Path $outputDirectory)) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

# File Excel finale
$finalOutputFile = "$outputDirectory\VM_Info_Consolidato.xlsx"

# Se il file Excel esiste già, eliminalo
if (Test-Path -Path $finalOutputFile) {
    Remove-Item -Path $finalOutputFile -Force
}

# Array per conservare tutte le informazioni delle VM
$allVMInfoList = @()

Write-Host "Inizio elaborazione dei vCenter..."

foreach ($vCenter in $vCenters) {
    Write-Host "`nConnessione a vCenter: ${vCenter}"
    try {
        Connect-VIServer -Server $vCenter -Credential $cred -ErrorAction Stop
        Write-Host "Connesso con successo a ${vCenter}"

        # Recupera tutte le VM
        $vmViews = Get-View -ViewType VirtualMachine -Property Name, Runtime.PowerState, Guest, Config, Parent

        foreach ($vmView in $vmViews) {
            try {
                Write-Host "Elaborazione della VM: $($vmView.Name)"
                
                # Dettagli VM
                $vmName = $vmView.Name
                $vmMoid = $vmView.MoRef.Value
                $dnsName = $vmView.Guest.HostName
                $powerState = $vmView.Runtime.PowerState
                $ipv4Addresses = if ($vmView.Guest.Net) {
                    ($vmView.Guest.Net | Where-Object { $_.IpAddress -match '^\d{1,3}(\.\d{1,3}){3}$' }).IpAddress -join ", "
                } else {
                    "N/A"
                }

                # Estrai altri dettagli
                $sqName = $dnsName -replace '\..*$', ''  # Rimuove tutto dopo il primo punto
                $vmwareToolsVersion = $vmView.Guest.ToolsVersion
                $vmwareToolsStatus = $vmView.Guest.ToolsStatus
                $vmtoolsDescription = ($vmView.Config.ExtraConfig | Where-Object { $_.Key -eq 'guestinfo.vmtools.description' }).Value

                # Ottieni il nome della cartella
                $folderName = "N/A"
                try {
                    if ($vmView.Parent) {
                        $folderView = Get-View -Id $vmView.Parent
                        $folderName = $folderView.Name
                    }
                } catch {
                    Write-Warning "FOLDER - Errore nel recuperare il nome della cartella per la VM '$($vmView.Name)': $($_.Exception.Message)"
                }

								# Ottieni i tag assegnati alla VM
				$vmTagNames = "Nessun tag assegnato"
				$vmTagCategories = "Nessun tag assegnato"
				try {
					$tags = Get-TagAssignment -Entity $vmView.Name
					if ($tags -ne $null -and $tags.Count -gt 0) {
						$vmTagNames = ($tags.Tag | Select-Object -ExpandProperty Name) -join ", "
						$vmTagCategories = ($tags.Tag | Select-Object -ExpandProperty Category.Name) -join ", "
					}
				} catch {
					Write-Warning "TAG - Errore nel recupero dei tag per la VM '$($vmView.Name)': $($_.Exception.Message)"
					 
					Write-Warning "Impossibile trovare tag per la VM con nome: '$($vmView.Name)'. Assicurati che il nome sia corretto e che la VM sia attiva."
					Write-Warning "Impossibile trovare tag per la VM con nome: '$($vmView.Name)'. Assicurati che il nome sia corretto e che la VM sia attiva."
				}

                # Ottieni il nome dell'host
                $hostName = "N/A"
                try {
                    if ($vmView.Runtime.Host) {
                        $hostView = Get-View -Id $vmView.Runtime.Host.Value
                        $hostName = $hostView.Name
                    }
                } catch {
                    Write-Warning "ESXI HOST - Errore nel recupero dell'host per la VM '$($vmView.Name)': $($_.Exception.Message)"
                }

                # Ottieni il nome del cluster
                $clusterName = "N/A"
                try {
                    if ($vmView.Runtime.Host) {
                        $hostMoRef = $vmView.Runtime.Host.Value
                        $clusterView = Get-Cluster -VM $vmView | Select-Object -First 1 -ErrorAction Stop
                        if ($clusterView) {
                            $clusterName = $clusterView.Name
                        }
                    }
                } catch {
                    Write-Warning "CLUSTER - Errore durante il recupero del cluster per la VM '$($vmView.Name)': $($_.Exception.Message)"
                }

                # Risali la gerarchia per trovare il Datacenter
                $datacenterName = "N/A"
                $currentParent = $vmView.Parent
                while ($currentParent) {
                    try {
                        $parentView = Get-View -Id $currentParent -Property Name, Parent
                        if ($parentView.GetType().Name -eq "Datacenter") {
                            $datacenterName = $parentView.Name
                            break
                        }
                        $currentParent = $parentView.Parent
                    } catch {
                        Write-Warning "DATACENTER - Errore nel recuperare il parent per la VM '$($vmView.Name)': $($_.Exception.Message)"
                        break
                    }
                }

                # Prepara l'oggetto vmInfo
                $vmInfo = [PSCustomObject]@{
                    "VMName"                = $vmName
                    "DNSName"               = $dnsName
                    "VMId"                  = $vmMoid
                    "PowerState"            = $powerState
                    "IPv4Addresses"         = $ipv4Addresses
                    "sqName"                = $sqName
                    "VMUUID"                = $vmView.Config.InstanceUuid
                    "SMBIOSUUID"            = $vmView.Config.Uuid
                    "VMwareToolsVersion"    = $vmwareToolsVersion
                    "VMwareToolsStatus"     = $vmwareToolsStatus
                    "VMToolsDescription"    = $vmtoolsDescription
                    "Host"                  = $hostName
                    "Cluster"               = $clusterName
                    "Folder"                = $folderName
                    "Datacenter"            = $datacenterName
                    "vCenter"               = ${vCenter}
                    "TotalClusters"         = (Get-Cluster).Count
                    "TotalHosts"            = (Get-VMHost).Count
                    "TotalVMs"              = (Get-VM).Count
                    "vCenterVersion"        = (Get-View -Id (Get-Cluster | Select-Object -First 1).MoRef).Version
                    "VMTags"                = $vmTagNames
                    "VMTagsCategory"        = $vmTagCategories
                }

                $allVMInfoList += $vmInfo
                # Controllo dell'aggiornamento della lista
                if ($allVMInfoList.Count -eq 0) {
                    Write-Warning "Attenzione: $($vmView.Name) non ha aggiornato allVMInfoList."
                }
            } catch {
                Write-Warning "LOOP - Errore durante l'elaborazione della VM '$($vmView.Name)': $($_.Exception.Message)"
            }
        }
    } catch {
        Write-Warning "Errore durante la connessione a vCenter: $($_.Exception.Message)"
        Stop-Transcript
        exit

    } finally {
        if (Get-VIServer -Server ${vCenter} -ErrorAction SilentlyContinue) {
            Disconnect-VIServer -Server ${vCenter} -Confirm:$false | Out-Null
            Write-Host "Disconnesso da ${vCenter}"
        } else {
            Write-Warning "ERRORE: Il server ${vCenter} non è connesso, impossibile disconnettere."
         
        }
    }
}

# Esporta tutte le informazioni in un unico foglio di lavoro
if ($allVMInfoList.Count -gt 0) {
    Write-Host "`nCreazione del file Excel consolidato..."
    try {
        $allVMInfoList | Export-Excel -Path $finalOutputFile -WorksheetName "VM_Info_Consolidato" -TableName "VMInfo_Consolidato" -AutoSize
        Write-Host "File Excel creato con successo: $finalOutputFile"
    } catch {
        Write-Warning "Errore durante la creazione del file Excel: $($_.Exception.Message)"
    }
} else {
    Write-Warning "Nessuna informazione VM trovata per esportare."
}

Write-Host "`nProcesso completato. I dati sono stati salvati in $finalOutputFile."

# Termina la trascrizione
Stop-Transcript
