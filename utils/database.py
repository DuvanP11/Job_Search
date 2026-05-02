#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE BASE DE DATOS CON JSON
Almacenamiento persistente sin SQLite
"""

import json
import hashlib
import secrets
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)


class Database:
    """Gestor de base de datos con archivos JSON"""
    
    def __init__(self, data_dir='data'):
        """Inicializar base de datos JSON"""
        self.data_dir = data_dir
        
        # Crear directorio si no existe
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Archivos de datos
        self.users_file = os.path.join(self.data_dir, 'users.json')
        self.credentials_file = os.path.join(self.data_dir, 'user_credentials.json')
        
        # Inicializar archivos si no existen
        self._init_files()
        logger.info("✅ Base de datos JSON inicializada")
    
    def _init_files(self):
        """Inicializar archivos JSON si no existen"""
        if not os.path.exists(self.users_file):
            with open(self.users_file, 'w') as f:
                json.dump({}, f)
        
        if not os.path.exists(self.credentials_file):
            with open(self.credentials_file, 'w') as f:
                json.dump({}, f)
    
    def _load_users(self):
        """Cargar usuarios desde JSON"""
        try:
            with open(self.users_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_users(self, users):
        """Guardar usuarios a JSON"""
        with open(self.users_file, 'w') as f:
            json.dump(users, f, indent=2)
    
    def _load_credentials(self):
        """Cargar credenciales desde JSON"""
        try:
            with open(self.credentials_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _save_credentials(self, credentials):
        """Guardar credenciales a JSON"""
        with open(self.credentials_file, 'w') as f:
            json.dump(credentials, f, indent=2)
    
    def hash_password(self, password):
        """Hash de contraseña con salt"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${pwd_hash.hex()}"
    
    def verify_password(self, password, password_hash):
        """Verificar contraseña contra hash"""
        try:
            salt, pwd_hash = password_hash.split('$')
            new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return new_hash.hex() == pwd_hash
        except:
            return False
    
    # ==================== MÉTODOS DE USUARIOS ====================
    
    def create_user(self, username, email, password, avatar='cat'):
        """Crear nuevo usuario"""
        try:
            users = self._load_users()
            
            # Verificar si ya existe
            for user_data in users.values():
                if user_data['email'] == email or user_data['username'] == username:
                    logger.error(f"❌ Usuario o email ya existe")
                    return None
            
            # Generar ID único
            user_id = str(len(users) + 1)
            
            # Hash de contraseña
            password_hash = self.hash_password(password)
            
            # Crear usuario
            users[user_id] = {
                'id': user_id,
                'username': username,
                'email': email,
                'password_hash': password_hash,
                'avatar': avatar,
                'created_at': datetime.now().isoformat(),
                'last_login': None
            }
            
            # Guardar
            self._save_users(users)
            
            logger.info(f"✅ Usuario creado: {username} (ID: {user_id})")
            return user_id
        
        except Exception as e:
            logger.error(f"❌ Error creando usuario: {str(e)}")
            return None
    
    def get_user_by_email(self, email):
        """Obtener usuario por email"""
        users = self._load_users()
        
        for user_data in users.values():
            if user_data['email'] == email:
                return user_data
        
        return None
    
    def get_user_by_id(self, user_id):
        """Obtener usuario por ID"""
        users = self._load_users()
        return users.get(str(user_id))
    
    def authenticate_user(self, email, password):
        """Autenticar usuario"""
        user = self.get_user_by_email(email)
        
        if not user:
            return None
        
        if self.verify_password(password, user['password_hash']):
            # Actualizar last_login
            users = self._load_users()
            users[user['id']]['last_login'] = datetime.now().isoformat()
            self._save_users(users)
            
            logger.info(f"✅ Login exitoso: {user['username']}")
            return user
        
        return None
    
    def update_user(self, user_id, user_data):
        """Actualizar datos de usuario"""
        try:
            users = self._load_users()
            
            if str(user_id) not in users:
                logger.error(f"❌ Usuario no encontrado: {user_id}")
                return False
            
            # Actualizar usuario
            users[str(user_id)] = user_data
            self._save_users(users)
            
            logger.info(f"✅ Usuario actualizado: {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error actualizando usuario: {str(e)}")
            return False
    
    # ==================== MÉTODOS DE CREDENCIALES ====================
    
    def save_user_credentials(self, user_id, portal, email, password_encrypted):
        """Guardar credenciales de portal para un usuario"""
        try:
            credentials = self._load_credentials()
            
            # Crear estructura si no existe
            user_id = str(user_id)
            if user_id not in credentials:
                credentials[user_id] = {}
            
            # Guardar credencial
            credentials[user_id][portal] = {
                'portal': portal,
                'email': email,
                'password_encrypted': password_encrypted,
                'enabled': True,
                'created_at': datetime.now().isoformat()
            }
            
            # Guardar archivo
            self._save_credentials(credentials)
            
            logger.info(f"✅ Credenciales guardadas para user_id={user_id}, portal={portal}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error guardando credenciales: {str(e)}")
            return False
    
    def get_user_credentials(self, user_id, portal):
        """Obtener credenciales de un portal para un usuario"""
        credentials = self._load_credentials()
        user_id = str(user_id)
        
        if user_id in credentials and portal in credentials[user_id]:
            cred = credentials[user_id][portal]
            if cred.get('enabled', True):
                return cred
        
        return None
    
    def list_user_credentials(self, user_id):
        """Listar todas las credenciales de un usuario"""
        credentials = self._load_credentials()
        user_id = str(user_id)
        
        if user_id not in credentials:
            return []
        
        result = []
        for portal, cred in credentials[user_id].items():
            result.append({
                'portal': portal,
                'email': cred['email'],
                'enabled': cred.get('enabled', True),
                'created_at': cred.get('created_at', '')
            })
        
        return result
    
    def delete_user_credentials(self, user_id, portal):
        """Eliminar credenciales de un portal"""
        try:
            credentials = self._load_credentials()
            user_id = str(user_id)
            
            if user_id in credentials and portal in credentials[user_id]:
                del credentials[user_id][portal]
                self._save_credentials(credentials)
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"❌ Error eliminando credenciales: {str(e)}")
            return False


# Instancia global
db = Database()
