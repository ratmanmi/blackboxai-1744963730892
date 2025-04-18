"""Schema delle classi CMDBuild per il connettore Veeam"""

CMDB_CLASSES = {
    "Infrastructure": {
        "key_attribute": "Code",
        "attributes": {
            "Name": str,
            "Type": str,  # LOOKUP
            "Status": str
        }
    },
    "PhysicalServer": {  # Per i Veeam Proxy
        "key_attribute": "Code",
        "attributes": {
            "Hostname": str,
            "Brand": str,
            "Model": str,
            "OS": str,
            "OSVersion": str,
            "Status": str,
            "Type": "VeeamProxy"  # Identificatore per i server Veeam
        }
    },
    "VirtualServer": {  # Per le VM backuppate
        "key_attribute": "Code",
        "attributes": {
            "Hostname": str,
            "OS": str,
            "OSVersion": str,
            "Status": str,
            "LastBackup": str,
            "BackupJob": str,  # Riferimento al job di backup
            "Repository": str  # Riferimento al repository
        }
    },
    "Storage": {  # Per i Repository Veeam
        "key_attribute": "Code",
        "attributes": {
            "Name": str,
            "Type": "VeeamRepository",
            "Capacity": int,
            "FreeSpace": int,
            "Status": str
        }
    },
    "BackupJob": {  # Nuova classe per i job di backup
        "key_attribute": "Code",
        "attributes": {
            "Name": str,
            "Type": str,
            "Status": str,
            "LastRun": str,
            "NextRun": str,
            "Repository": str,  # Riferimento al repository
            "Description": str
        }
    }
}

CMDB_DOMAINS = {
    "InfrastructureCI": [
        ("Infrastructure", "Storage"),  # Infrastructure -> Repository
        ("Infrastructure", "PhysicalServer"),  # Infrastructure -> Proxy
        ("Infrastructure", "VirtualServer")  # Infrastructure -> VM
    ],
    "CIDependency": [
        ("VirtualServer", "PhysicalServer"),  # VM -> Proxy
        ("BackupJob", "Storage")  # Job -> Repository
    ]
}

def get_class_schema(class_name):
    """Restituisce lo schema di una classe"""
    return CMDB_CLASSES.get(class_name, {})

def get_key_attribute(class_name):
    """Restituisce l'attributo chiave di una classe"""
    schema = get_class_schema(class_name)
    return schema.get("key_attribute")

def get_attributes(class_name):
    """Restituisce gli attributi di una classe"""
    schema = get_class_schema(class_name)
    return schema.get("attributes", {})

def get_domains():
    """Restituisce tutti i domini definiti"""
    return CMDB_DOMAINS

def validate_data(class_name, data):
    """Valida i dati rispetto allo schema della classe"""
    schema = get_class_schema(class_name)
    if not schema:
        raise ValueError(f"Classe {class_name} non trovata nello schema")
    
    key_attr = schema["key_attribute"]
    if key_attr not in data:
        raise ValueError(f"Attributo chiave {key_attr} mancante per la classe {class_name}")
    
    attributes = schema["attributes"]
    for attr, value in data.items():
        if attr not in attributes and attr != key_attr:
            raise ValueError(f"Attributo {attr} non definito nello schema per la classe {class_name}")
        
        expected_type = attributes.get(attr)
        if expected_type and not isinstance(value, expected_type) and value is not None:
            try:
                # Tenta la conversione del tipo
                data[attr] = expected_type(value)
            except (ValueError, TypeError):
                raise ValueError(f"Tipo non valido per l'attributo {attr} in {class_name}. Atteso {expected_type}, ricevuto {type(value)}")
    
    return True
