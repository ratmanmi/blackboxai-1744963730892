import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from .cmdb_schema import (
    get_class_schema,
    get_key_attribute,
    validate_data,
    get_domains
)

class CMDBuildClient:
    """Client per le API REST di CMDBuild"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config['cmdb_url']
        self.username = config['cmdb_username']
        self.password = config['cmdb_password']
        self.verify_ssl = config.get('verify_ssl', True)
        self.infrastructure_code = config.get('infrastructure_code', 'VEEAM-BACKUP')
        self.token = None
        self.session = requests.Session()
        
    def authenticate(self) -> None:
        """Esegue l'autenticazione su CMDBuild"""
        url = f"{self.base_url}/sessions"
        data = {
            "username": self.username,
            "password": self.password
        }
        try:
            response = self.session.post(url, json=data, verify=self.verify_ssl)
            response.raise_for_status()
            self.token = response.json()["data"]["_id"]
            self.session.headers.update({"CMDBuild-Authorization": self.token})
            logging.info("Autenticazione su CMDBuild completata con successo")
        except Exception as e:
            logging.error(f"Errore durante l'autenticazione su CMDBuild: {str(e)}")
            raise

    def _make_request(self, endpoint: str, method: str = 'GET', data: Dict = None, params: Dict = None) -> Dict:
        """Esegue una richiesta API a CMDBuild"""
        if not self.token:
            self.authenticate()
            
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Errore nella richiesta API CMDBuild {endpoint}: {str(e)}")
            raise

    def get_infrastructure(self) -> Optional[Dict]:
        """Recupera o crea l'infrastruttura Veeam"""
        try:
            # Cerca l'infrastruttura esistente
            filter_query = {
                "attribute": "Code",
                "operator": "equal",
                "value": self.infrastructure_code
            }
            
            result = self._make_request(
                "classes/Infrastructure/cards",
                params={"filter": filter_query}
            )
            
            if result["data"]:
                return result["data"][0]
            
            # Crea nuova infrastruttura se non esiste
            infra_data = {
                "Code": self.infrastructure_code,
                "Name": "Veeam Backup Infrastructure",
                "Type": "VeeamBackup",
                "Status": "A"  # Active
            }
            
            result = self._make_request(
                "classes/Infrastructure/cards",
                method="POST",
                data=infra_data
            )
            
            return result["data"]
        except Exception as e:
            logging.error(f"Errore nel recupero/creazione dell'infrastruttura: {str(e)}")
            raise

    def find_card_by_code(self, class_name: str, code: str) -> Optional[Dict]:
        """Cerca una card per codice"""
        try:
            filter_query = {
                "attribute": "Code",
                "operator": "equal",
                "value": code
            }
            
            result = self._make_request(
                f"classes/{class_name}/cards",
                params={"filter": filter_query}
            )
            
            return result["data"][0] if result["data"] else None
        except Exception as e:
            logging.error(f"Errore nella ricerca della card {class_name} con codice {code}: {str(e)}")
            return None

    def create_or_update_card(self, class_name: str, data: Dict) -> Dict:
        """Crea o aggiorna una card"""
        try:
            # Valida i dati contro lo schema
            validate_data(class_name, data)
            
            # Cerca la card esistente
            key_attr = get_key_attribute(class_name)
            existing = self.find_card_by_code(class_name, data[key_attr])
            
            if existing:
                # Aggiorna card esistente
                card_id = existing["_id"]
                return self._make_request(
                    f"classes/{class_name}/cards/{card_id}",
                    method="PUT",
                    data=data
                )["data"]
            else:
                # Crea nuova card
                return self._make_request(
                    f"classes/{class_name}/cards",
                    method="POST",
                    data=data
                )["data"]
        except Exception as e:
            logging.error(f"Errore nella creazione/aggiornamento della card {class_name}: {str(e)}")
            raise

    def create_relation(self, domain_name: str, class1: str, id1: int, class2: str, id2: int) -> Dict:
        """Crea una relazione tra due card"""
        try:
            data = {
                "_type": domain_name,
                "_sourceType": class1,
                "_sourceId": id1,
                "_destinationType": class2,
                "_destinationId": id2,
                "Status": "A"  # Active
            }
            
            return self._make_request(
                "domains/relations",
                method="POST",
                data=data
            )["data"]
        except Exception as e:
            logging.error(f"Errore nella creazione della relazione {domain_name}: {str(e)}")
            raise

    def sync_veeam_inventory(self, inventory: Dict[str, List[Dict]]) -> None:
        """Sincronizza l'inventario Veeam con CMDBuild"""
        try:
            logging.info("Inizio sincronizzazione inventario Veeam")
            
            # Recupera o crea l'infrastruttura
            infrastructure = self.get_infrastructure()
            infra_id = infrastructure["_id"]
            
            # Sincronizza Proxy
            for proxy in inventory["proxies"]:
                # Prima cerca il proxy tra i VirtualServer
                proxy_vm = self.find_card_by_code("VirtualServer", proxy["id"])
                
                if proxy_vm:
                    logging.info(f"Proxy {proxy['id']} trovato come VirtualServer esistente")
                    # Aggiorna solo gli attributi Veeam-specifici
                    proxy_data = {
                        "_id": proxy_vm["_id"],
                        "Type": "VeeamProxy",
                        "Status": "A",
                        "LastUpdate": datetime.now().isoformat()
                    }
                    proxy_card = self.create_or_update_card("VirtualServer", proxy_data)
                    server_type = "VirtualServer"
                else:
                    # Se non trovato come VM, cerca tra i PhysicalServer
                    proxy_physical = self.find_card_by_code("PhysicalServer", proxy["id"])
                    
                    if proxy_physical:
                        logging.info(f"Proxy {proxy['id']} trovato come PhysicalServer esistente")
                        proxy_data = {
                            "_id": proxy_physical["_id"],
                            "Type": "VeeamProxy",
                            "Status": "A",
                            "LastUpdate": datetime.now().isoformat()
                        }
                        proxy_card = self.create_or_update_card("PhysicalServer", proxy_data)
                        server_type = "PhysicalServer"
                    else:
                        # Se non trovato da nessuna parte, crea un nuovo PhysicalServer
                        logging.warning(f"Proxy {proxy['id']} non trovato in asset, creazione nuovo PhysicalServer")
                        proxy_data = {
                            "Code": proxy["id"],
                            "Hostname": proxy.get("name", ""),
                            "Type": "VeeamProxy",
                            "Status": "A",
                            "OS": proxy.get("os", ""),
                            "OSVersion": proxy.get("osVersion", ""),
                            "LastUpdate": datetime.now().isoformat()
                        }
                        proxy_card = self.create_or_update_card("PhysicalServer", proxy_data)
                        server_type = "PhysicalServer"
                
                # Crea relazione con l'infrastruttura
                self.create_relation(
                    "InfrastructureCI",
                    "Infrastructure",
                    infra_id,
                    server_type,
                    proxy_card["_id"]
                )
            
            # Sincronizza Repository
            for repo in inventory["repositories"]:
                repo_data = {
                    "Code": repo["id"],
                    "Name": repo.get("name", ""),
                    "Type": "VeeamRepository",
                    "Capacity": repo.get("capacity", 0),
                    "FreeSpace": repo.get("freeSpace", 0),
                    "Status": "A"
                }
                repo_card = self.create_or_update_card("Storage", repo_data)
                
                # Crea relazione con l'infrastruttura
                self.create_relation(
                    "InfrastructureCI",
                    "Infrastructure",
                    infra_id,
                    "Storage",
                    repo_card["_id"]
                )
            
            # Sincronizza Backup Jobs e VM
            for job in inventory["backup_jobs"]:
                # Crea il job
                job_data = {
                    "Code": job["id"],
                    "Name": job.get("name", ""),
                    "Type": "VeeamBackup",
                    "Status": job.get("status", "Unknown"),
                    "LastRun": job.get("lastRun", ""),
                    "NextRun": job.get("nextRun", ""),
                    "Repository": job.get("repositoryId", "")
                }
                job_card = self.create_or_update_card("BackupJob", job_data)
                
                # Crea relazione con il repository
                if job.get("repositoryId"):
                    repo = self.find_card_by_code("Storage", job["repositoryId"])
                    if repo:
                        self.create_relation(
                            "CIDependency",
                            "BackupJob",
                            job_card["_id"],
                            "Storage",
                            repo["_id"]
                        )
                
                # Sincronizza VM del job
                for vm in job.get("vms", []):
                    vm_data = {
                        "Code": vm["id"],
                        "Hostname": vm.get("name", ""),
                        "Status": "A",
                        "LastBackup": vm.get("lastBackup", ""),
                        "BackupJob": job["id"]
                    }
                    vm_card = self.create_or_update_card("VirtualServer", vm_data)
                    
                    # Crea relazione con l'infrastruttura
                    self.create_relation(
                        "InfrastructureCI",
                        "Infrastructure",
                        infra_id,
                        "VirtualServer",
                        vm_card["_id"]
                    )
            
            logging.info("Sincronizzazione inventario Veeam completata con successo")
            
        except Exception as e:
            logging.error(f"Errore durante la sincronizzazione dell'inventario: {str(e)}")
            raise
