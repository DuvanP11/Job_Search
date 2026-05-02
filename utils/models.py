#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODELOS DE BASE DE DATOS POSTGRESQL
Modelos SQLAlchemy para usuarios y credenciales
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class User(Base):
    """Modelo de Usuario"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(500), nullable=False)
    avatar = Column(String(50), default='cat')
    nombre = Column(String(100))
    apellido = Column(String(100))
    edad = Column(Integer)
    nacionalidad = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    def to_dict(self):
        """Convertir a diccionario para compatibilidad con código existente"""
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'password_hash': self.password_hash,
            'avatar': self.avatar,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'edad': self.edad,
            'nacionalidad': self.nacionalidad,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class UserCredential(Base):
    """Modelo de Credenciales de Usuario"""
    __tablename__ = 'user_credentials'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    portal = Column(String(100), nullable=False)
    username = Column(String(255))
    password = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convertir a diccionario"""
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'portal': self.portal,
            'username': self.username,
            'password': self.password,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


def get_engine():
    """Obtener engine de PostgreSQL"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL no encontrada en variables de entorno")
    
    # Railway usa postgresql:// pero SQLAlchemy necesita postgresql+psycopg2://
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    
    return create_engine(database_url)


def init_db():
    """Inicializar base de datos - crear tablas"""
    try:
        engine = get_engine()
        Base.metadata.create_all(engine)
        return True
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        return False


def get_session():
    """Obtener sesión de base de datos"""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
