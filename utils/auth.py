#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE AUTENTICACIÓN
Login, logout, decoradores, avatares
"""

from functools import wraps
from flask import session, redirect, url_for, flash
import logging

logger = logging.getLogger(__name__)


# ==================== AVATARES ANIMADOS ====================

AVATARES = {
    'cat': '🐱',
    'dog': '🐶',
    'fox': '🦊',
    'bear': '🐻',
    'panda': '🐼',
    'koala': '🐨',
    'tiger': '🐯',
    'lion': '🦁',
    'cow': '🐮',
    'pig': '🐷',
    'frog': '🐸',
    'monkey': '🐵',
    'chicken': '🐔',
    'penguin': '🐧',
    'bird': '🐦',
    'duck': '🦆',
    'owl': '🦉',
    'bat': '🦇',
    'wolf': '🐺',
    'unicorn': '🦄',
    'zebra': '🦓',
    'giraffe': '🦒',
    'elephant': '🐘',
    'rhino': '🦏',
    'hippo': '🦛',
    'mouse': '🐭',
    'hamster': '🐹',
    'rabbit': '🐰',
    'chipmunk': '🐿️',
    'hedgehog': '🦔',
    'deer': '🦌',
    'horse': '🐴',
    'ram': '🐏',
    'goat': '🐐',
    'camel': '🐫',
    'llama': '🦙',
    'sloth': '🦥',
    'otter': '🦦',
    'skunk': '🦨',
    'kangaroo': '🦘',
    'badger': '🦡',
    'turkey': '🦃',
    'dove': '🕊️',
    'eagle': '🦅',
    'swan': '🦢',
    'parrot': '🦜',
    'flamingo': '🦩',
    'peacock': '🦚',
    'shark': '🦈'
}


# ==================== DECORADORES ====================

def login_required(f):
    """Decorador para requerir login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('⚠️ Debes iniciar sesión para acceder', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== FUNCIONES DE AUTENTICACIÓN ====================

def get_current_user():
    """Obtener usuario actual desde sesión"""
    from utils.database import db
    
    if 'user_id' not in session:
        return None
    
    user_id = session['user_id']
    user = db.get_user_by_id(user_id)
    
    if not user:
        # Sesión inválida
        session.clear()
        return None
    
    return user


def login_user(user):
    """Crear sesión de usuario"""
    session.permanent = True  # Sesión persistente por 30 días
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['email'] = user['email']
    session['avatar'] = user['avatar']
    logger.info(f"✅ Sesión creada para: {user['username']}")


def logout_user():
    """Cerrar sesión de usuario"""
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"✅ Sesión cerrada para: {username}")


def get_avatar_emoji(avatar_key):
    """Obtener emoji de avatar"""
    return AVATARES.get(avatar_key, '🐱')
