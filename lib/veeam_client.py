import requests
import logging
from typing import Dict, List, Any
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning

# Disabilita warning per SSL non verificato
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

class VeeamClient:
    """Client per le API Veeam"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config['veeam']
        self.base_url = self.config['server']
        self.verify_ssl = self.config.get('verify_ssl', False)
        self.token = None
        self.session = requests.Session()
        
    def get_token(self) -> str:
        """Ottiene il token di autenticazione"""
        url = f"{self.base_url}/api/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.config["client_id"],
            "client_secret": self.config["client_secret"]
        }
        try:
            response = self.session.post(url, data=data, verify=self.verify_ssl)
            response.raise_for_status()
            self.token = response.json()["access_token"]
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            logging.info("Token Veeam ottenuto con successo")
            return self.token
        except Exception as e:
            logging.error(f"Errore durante l'ottenimento del token Veeam: {str(e)}")
            raise

    def _make_request(self, endpoint: str, method: str = 'GET', params: Dict = None) -> Dict:
        """Esegue una richiesta API"""
        if not self.token:
            self.get_token()
            
        url = f"{self.base_url}/api/v1/{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if response.status_code == 401:
                # Token scaduto, riprova con nuovo token
                self.token = None
                return self._make_request(endpoint, method, params)
            logging.error(f"Errore nella richiesta API Veeam {endpoint}: {str(e)}")
            raise

    def get_proxies(self) -> List[Dict]:
        """Ottiene la lista dei proxy configurati"""
        logging.info("Recupero lista proxy Veeam")
        try:
            proxies = self._make_request("proxies")
            for proxy in proxies:
                # Arricchisce i dati del proxy con informazioni dettagliate
                details = self._make_request(f"proxies/{proxy['id']}")
                proxy.update(details)
            return proxies
        except Exception as e:
            logging.error(f"Errore nel recupero dei proxy: {str(e)}")
            raise

    def get_repositories(self) -> List[Dict]:
        """Ottiene la lista dei repository"""
        logging.info("Recupero lista repository Veeam")
        try:
            repos = self._make_request("repositories")
            for repo in repos:
                # Arricchisce i dati del repository con informazioni dettagliate
                details = self._make_request(f"repositories/{repo['id']}/info")
                repo.update(details)
            return repos
        except Exception as e:
            logging.error(f"Errore nel recupero dei repository: {str(e)}")
            raise

    def get_backup_jobs(self) -> List[Dict]:
        """Ottiene la lista dei backup jobs"""
        logging.info("Recupero lista backup jobs Veeam")
        try:
            jobs = self._make_request("jobs")
            for job in jobs:
                # Arricchisce i dati del job con informazioni dettagliate
                details = self._make_request(f"jobs/{job['id']}")
                job.update(details)
                # Aggiunge le VM associate al job
                job['vms'] = self.get_vms_in_backup(job['id'])
            return jobs
        except Exception as e:
            logging.error(f"Errore nel recupero dei backup jobs: {str(e)}")
            raise

    def get_vms_in_backup(self, job_id: str) -> List[Dict]:
        """Ottiene la lista delle VM incluse in un backup"""
        logging.info(f"Recupero VM del job {job_id}")
        try:
            vms = self._make_request(f"jobs/{job_id}/objects")
            for vm in vms:
                # Arricchisce i dati della VM con l'ultimo backup
                last_backup = self._make_request(f"jobs/{job_id}/objects/{vm['id']}/lastbackup")
                vm['lastBackup'] = last_backup.get('endTime', '')
            return vms
        except Exception as e:
            logging.error(f"Errore nel recupero delle VM del job {job_id}: {str(e)}")
            return []

    def get_full_inventory(self) -> Dict[str, List[Dict]]:
        """Ottiene l'inventario completo di tutte le risorse"""
        logging.info("Inizio recupero inventario completo Veeam")
        try:
            inventory = {
                "proxies": self.get_proxies(),
                "repositories": self.get_repositories(),
                "backup_jobs": self.get_backup_jobs()
            }
            
            logging.info("Inventario Veeam recuperato con successo")
            return inventory
            
        except Exception as e:
            logging.error(f"Errore durante il recupero dell'inventario completo: {str(e)}")
            raise

    def get_backup_sessions(self, job_id: str = None, limit: int = 100) -> List[Dict]:
        """Ottiene le sessioni di backup"""
        try:
            params = {"limit": limit}
            if job_id:
                return self._make_request(f"jobs/{job_id}/sessions", params=params)
            return self._make_request("sessions", params=params)
        except Exception as e:
            logging.error(f"Errore nel recupero delle sessioni di backup: {str(e)}")
            return []

    def get_backup_statistics(self, job_id: str = None) -> Dict:
        """Ottiene le statistiche dei backup"""
        try:
            if job_id:
                return self._make_request(f"jobs/{job_id}/statistics")
            return self._make_request("statistics")
        except Exception as e:
            logging.error(f"Errore nel recupero delle statistiche: {str(e)}")
            return {}
