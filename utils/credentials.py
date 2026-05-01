#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE MANEJO DE CREDENCIALES
Almacena credenciales de portales de forma segura y encriptada
"""

from cryptography.fernet import Fernet
import json
import os
import logging

logger = logging.getLogger(__name__)


class CredentialManager:
    """Gestor de credenciales encriptadas para portales de empleo"""
    
    def __init__(self):
        """Inicializar gestor de credenciales"""
        # Obtener o generar clave de encriptación
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
        
        # Directorio para credenciales
        self.creds_dir = os.path.join(os.path.dirname(__file__), '..', 'credentials')
        os.makedirs(self.creds_dir, exist_ok=True)
        
        logger.info("✅ CredentialManager inicializado")
    
    def _get_or_create_key(self):
        """Obtener o crear clave de encriptación"""
        key_file = os.path.join(os.path.dirname(__file__), '..', '.encryption_key')
        
        # Si existe, leer
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        
        # Si no existe, crear
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        
        logger.info("🔑 Nueva clave de encriptación generada")
        return key
    
    def save_credentials(self, portal, email, password):
        """
        Guardar credenciales de un portal de forma encriptada
        
        Args:
            portal (str): Nombre del portal ('elempleo', 'indeed', etc)
            email (str): Email del usuario
            password (str): Contraseña del usuario
        
        Returns:
            bool: True si se guardó exitosamente
        """
        try:
            # Encriptar contraseña
            encrypted_pwd = self.cipher.encrypt(password.encode())
            
            # Estructura de credenciales
            credentials = {
                'portal': portal,
                'email': email,
                'password': encrypted_pwd.decode(),
                'enabled': True
            }
            
            # Guardar en archivo JSON
            cred_file = os.path.join(self.creds_dir, f'{portal}.json')
            with open(cred_file, 'w') as f:
                json.dump(credentials, f, indent=2)
            
            logger.info(f"✅ Credenciales guardadas para {portal}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error guardando credenciales de {portal}: {str(e)}")
            return False
    
    def get_credentials(self, portal):
        """
        Obtener credenciales de un portal (desencriptadas)
        
        Args:
            portal (str): Nombre del portal
        
        Returns:
            dict: {'email': str, 'password': str} o None si no existen
        """
        try:
            cred_file = os.path.join(self.creds_dir, f'{portal}.json')
            
            # Verificar si existen credenciales
            if not os.path.exists(cred_file):
                logger.warning(f"⚠️ No hay credenciales para {portal}")
                return None
            
            # Leer archivo
            with open(cred_file, 'r') as f:
                creds = json.load(f)
            
            # Verificar si están habilitadas
            if not creds.get('enabled', False):
                logger.warning(f"⚠️ Credenciales de {portal} deshabilitadas")
                return None
            
            # Desencriptar contraseña
            password = self.cipher.decrypt(creds['password'].encode()).decode()
            
            return {
                'email': creds['email'],
                'password': password
            }
        
        except Exception as e:
            logger.error(f"❌ Error obteniendo credenciales de {portal}: {str(e)}")
            return None
    
    def list_portals(self):
        """
        Listar portales con credenciales configuradas
        
        Returns:
            list: Lista de portales configurados
        """
        try:
            files = os.listdir(self.creds_dir)
            portales = []
            
            for file in files:
                if file.endswith('.json'):
                    portal_name = file.replace('.json', '')
                    
                    # Leer estado
                    with open(os.path.join(self.creds_dir, file), 'r') as f:
                        data = json.load(f)
                    
                    portales.append({
                        'portal': portal_name,
                        'email': data.get('email', ''),
                        'enabled': data.get('enabled', False)
                    })
            
            return portales
        
        except Exception as e:
            logger.error(f"❌ Error listando portales: {str(e)}")
            return []
    
    def delete_credentials(self, portal):
        """
        Eliminar credenciales de un portal
        
        Args:
            portal (str): Nombre del portal
        
        Returns:
            bool: True si se eliminó exitosamente
        """
        try:
            cred_file = os.path.join(self.creds_dir, f'{portal}.json')
            
            if os.path.exists(cred_file):
                os.remove(cred_file)
                logger.info(f"✅ Credenciales de {portal} eliminadas")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"❌ Error eliminando credenciales de {portal}: {str(e)}")
            return False
    
    def toggle_portal(self, portal, enabled):
        """
        Habilitar/deshabilitar portal
        
        Args:
            portal (str): Nombre del portal
            enabled (bool): True para habilitar, False para deshabilitar
        
        Returns:
            bool: True si se actualizó exitosamente
        """
        try:
            cred_file = os.path.join(self.creds_dir, f'{portal}.json')
            
            if not os.path.exists(cred_file):
                return False
            
            # Leer credenciales actuales
            with open(cred_file, 'r') as f:
                creds = json.load(f)
            
            # Actualizar estado
            creds['enabled'] = enabled
            
            # Guardar
            with open(cred_file, 'w') as f:
                json.dump(creds, f, indent=2)
            
            status = "habilitado" if enabled else "deshabilitado"
            logger.info(f"✅ Portal {portal} {status}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error actualizando estado de {portal}: {str(e)}")
            return False


# Instancia global
credential_manager = CredentialManager()
