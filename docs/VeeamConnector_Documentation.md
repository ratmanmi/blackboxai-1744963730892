# Documentazione Connettore Veeam per CMDBuild

## Indice
1. [Introduzione](#introduzione)
2. [Architettura](#architettura)
3. [Configurazione](#configurazione)
4. [Integrazione con CMDBuild](#integrazione-con-cmdbuild)
5. [Flusso di Esecuzione](#flusso-di-esecuzione)
6. [Gestione Errori](#gestione-errori)
7. [Manutenzione](#manutenzione)

## Introduzione

Il connettore Veeam per CMDBuild è uno strumento Python che sincronizza automaticamente l'inventario di Veeam Backup & Replication con l'asset management di CMDBuild. Lo script recupera informazioni su proxy, repository, job di backup e macchine virtuali da Veeam e le integra nell'asset management esistente.

### Caratteristiche Principali
- Sincronizzazione automatica via crontab
- Gestione intelligente dei server Veeam esistenti
- Logging dettagliato con rotazione
- Gestione errori con retry automatico
- Preservazione dei dati esistenti in CMDBuild

## Architettura

### Struttura del Progetto
```
veeam-connector/
├── bin/
│   └── sync_inventory.py    # Script principale
├── lib/
│   ├── veeam_client.py     # Client API Veeam
│   ├── cmdb_client.py      # Client API CMDBuild
│   └── cmdb_schema.py      # Schema dati CMDBuild
├── config/
│   └── config.json         # Configurazione
├── logs/                   # Directory log
└── requirements.txt        # Dipendenze Python
```

### Componenti
1. **VeeamClient** (lib/veeam_client.py)
   - Gestisce l'autenticazione OAuth2 con Veeam
   - Recupera l'inventario completo
   - Implementa retry automatico per le chiamate API

2. **CMDBuildClient** (lib/cmdb_client.py)
   - Gestisce l'autenticazione con CMDBuild
   - Aggiorna l'asset management
   - Gestisce le relazioni tra entità

3. **CMDBSchema** (lib/cmdb_schema.py)
   - Definisce la struttura dati in CMDBuild
   - Valida i dati prima dell'inserimento
   - Gestisce le relazioni tra classi

## Configurazione

### File config.json
```json
{
    "infrastructure_code": "VEEAM-BACKUP",
    
    "veeam": {
        "server": "https://veeam-server.example.com",
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "verify_ssl": false,
        "retry": {
            "max_attempts": 3,
            "delay_seconds": 5
        }
    },
    
    "cmdbuild": {
        "url": "https://cmdbuild-server.example.com/api",
        "username": "admin",
        "password": "admin",
        "verify_ssl": true
    },
    
    "logging": {
        "level": "INFO",
        "file": "/var/log/VeeamConnector/connector.log",
        "max_size": 10485760,
        "backup_count": 5,
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }
}
```

## Integrazione con CMDBuild

### Classi Aggiornate

1. **Infrastructure**
   - Rappresenta l'infrastruttura Veeam
   - Attributi:
     * Code: Identificativo univoco
     * Name: Nome descrittivo
     * Type: "VeeamBackup"
     * Status: Stato attivo/inattivo

2. **Proxy Server** (VirtualServer o PhysicalServer)
   - Logica di identificazione:
     1. Ricerca in VirtualServer esistenti
     2. Ricerca in PhysicalServer esistenti
     3. Creazione nuovo PhysicalServer se non trovato
   - Attributi aggiornati:
     * Type: "VeeamProxy"
     * Status: Stato attuale
     * LastUpdate: Data aggiornamento

3. **Storage** (Repository)
   - Attributi:
     * Code: ID repository
     * Name: Nome repository
     * Type: "VeeamRepository"
     * Capacity: Capacità totale
     * FreeSpace: Spazio disponibile

4. **BackupJob**
   - Attributi:
     * Code: ID job
     * Name: Nome job
     * Type: Tipo backup
     * Status: Stato
     * LastRun: Ultima esecuzione
     * NextRun: Prossima esecuzione

5. **VirtualServer** (VM Backuppate)
   - Attributi:
     * Code: ID VM
     * Hostname: Nome VM
     * Status: Stato
     * LastBackup: Ultimo backup
     * BackupJob: Riferimento al job

### Relazioni

1. **InfrastructureCI**
   - Infrastructure → Storage
   - Infrastructure → VirtualServer/PhysicalServer
   - Infrastructure → VirtualServer (VM)

2. **CIDependency**
   - BackupJob → Storage
   - VirtualServer → PhysicalServer

## Flusso di Esecuzione

1. **Inizializzazione**
   ```python
   # Carica configurazione
   config = load_config()
   
   # Configura logging
   setup_logging(config)
   
   # Inizializza client
   veeam_client = VeeamClient(config)
   cmdb_client = CMDBuildClient(config)
   ```

2. **Recupero Dati Veeam**
   ```python
   inventory = veeam_client.get_full_inventory()
   # Contiene: proxies, repositories, backup_jobs
   ```

3. **Sincronizzazione CMDBuild**
   ```python
   # Crea/aggiorna infrastruttura
   infrastructure = cmdb_client.get_infrastructure()
   
   # Sincronizza componenti
   cmdb_client.sync_veeam_inventory(inventory)
   ```

## Gestione Errori

1. **Retry Automatico**
   - Configurabile in config.json
   - Ritenta le operazioni fallite
   - Logging dettagliato degli errori

2. **Validazione Dati**
   - Verifica schema prima dell'inserimento
   - Controllo tipi di dati
   - Gestione valori mancanti

3. **Logging**
   - Rotazione automatica dei log
   - Livelli di logging configurabili
   - Tracciamento completo delle operazioni

## Manutenzione

### Installazione
```bash
# Clona il repository
git clone <repository-url>

# Installa dipendenze
pip install -r requirements.txt

# Configura config.json
cp config/config.example.json config/config.json
vim config/config.json

# Configura crontab
0 2 * * * /path/to/bin/sync_inventory.py
```

### Monitoraggio
- Controllare i log in /var/log/VeeamConnector/connector.log
- Verificare lo stato delle sincronizzazioni
- Monitorare lo spazio su disco per i log

### Troubleshooting
1. **Errori di Connessione**
   - Verificare configurazione SSL
   - Controllare credenziali
   - Verificare connettività di rete

2. **Errori di Sincronizzazione**
   - Controllare log per dettagli
   - Verificare permessi CMDBuild
   - Controllare schema dati

3. **Problemi di Performance**
   - Regolare batch_size in configurazione
   - Ottimizzare scheduling crontab
   - Monitorare utilizzo risorse

### Best Practices
1. **Backup Configurazione**
   - Mantenere backup di config.json
   - Documentare modifiche alla configurazione
   - Versionare le personalizzazioni

2. **Monitoraggio Proattivo**
   - Implementare alert su errori
   - Verificare regolarmente i log
   - Controllare spazio su disco

3. **Manutenzione Regolare**
   - Aggiornare dipendenze Python
   - Ruotare/archiviare log vecchi
   - Verificare performance

---

Per supporto o problemi:
1. Consultare i log
2. Verificare la configurazione
3. Contattare l'amministratore di sistema
