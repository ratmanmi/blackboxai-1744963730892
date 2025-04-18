#!/usr/bin/env python3

import os
import sys
import json
import logging
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Dict, Any

# Aggiungiamo il path per i moduli custom
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.veeam_client import VeeamClient
from lib.cmdb_client import CMDBuildClient

def setup_logging(config: Dict[str, Any]) -> None:
    """Configura il sistema di logging"""
    log_config = config.get('logging', {})
    
    # Crea la directory dei log se non esiste
    log_file = log_config.get('file', '/var/log/VeeamConnector/connector.log')
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Configura il rotating file handler
    handler = RotatingFileHandler(
        log_file,
        maxBytes=log_config.get('max_size', 10485760),  # 10MB default
        backupCount=log_config.get('backup_count', 5)
    )
    
    # Formattazione del log
    formatter = logging.Formatter(
        log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    handler.setFormatter(formatter)
    
    # Configura il logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(log_config.get('level', 'INFO'))
    root_logger.addHandler(handler)

def load_config() -> Dict[str, Any]:
    """Carica la configurazione dal file JSON"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config',
        'config.json'
    )
    
    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception as e:
        raise Exception(f"Errore nel caricamento della configurazione: {str(e)}")

def retry_operation(operation, max_attempts: int, delay: int):
    """
    Esegue un'operazione con retry in caso di errore
    
    Args:
        operation: Funzione da eseguire
        max_attempts: Numero massimo di tentativi
        delay: Ritardo tra i tentativi in secondi
    """
    last_error = None
    
    for attempt in range(max_attempts):
        try:
            return operation()
        except Exception as e:
            last_error = e
            if attempt < max_attempts - 1:
                logging.warning(
                    f"Tentativo {attempt + 1} fallito: {str(e)}. "
                    f"Nuovo tentativo tra {delay} secondi..."
                )
                time.sleep(delay)
            else:
                logging.error(
                    f"Tutti i tentativi falliti. Ultimo errore: {str(e)}"
                )
                raise last_error

def sync_inventory(veeam_client: VeeamClient, cmdb_client: CMDBuildClient, config: Dict[str, Any]) -> None:
    """
    Sincronizza l'inventario tra Veeam e CMDBuild
    
    Args:
        veeam_client: Client per le API Veeam
        cmdb_client: Client per le API CMDBuild
        config: Configurazione del connettore
    """
    try:
        # Recupera l'inventario da Veeam
        inventory = veeam_client.get_full_inventory()
        
        # Sincronizza con CMDBuild
        cmdb_client.sync_veeam_inventory(inventory)
        
        logging.info("Sincronizzazione completata con successo")
        
    except Exception as e:
        logging.error(f"Errore durante la sincronizzazione: {str(e)}")
        raise

def main():
    try:
        # Carica la configurazione
        config = load_config()
        
        # Configura il logging
        setup_logging(config)
        
        logging.info("Avvio sincronizzazione Veeam con CMDBuild")
        
        # Inizializza i client
        veeam_client = VeeamClient(config)
        cmdb_client = CMDBuildClient(config)
        
        # Configurazione retry
        retry_config = config['veeam'].get('retry', {})
        max_attempts = retry_config.get('max_attempts', 3)
        retry_delay = retry_config.get('delay_seconds', 5)
        
        # Esegue la sincronizzazione con retry
        retry_operation(
            lambda: sync_inventory(veeam_client, cmdb_client, config),
            max_attempts,
            retry_delay
        )
        
        logging.info("Processo di sincronizzazione completato con successo")
        
    except Exception as e:
        logging.error(f"Errore fatale durante l'esecuzione: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
