#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALMACÉN CLAVE-VALOR CON EXPIRACIÓN

En un servidor tradicional basta un diccionario en memoria para guardar cosas
temporales (el CV de la sesión, el caché de resultados, los códigos de
recuperación). En un entorno serverless como Vercel cada petición puede
atenderla un proceso distinto, así que ese diccionario se pierde entre una
petición y la siguiente.

Este módulo guarda esos datos en PostgreSQL cuando hay DATABASE_URL, y cae a
un diccionario en memoria cuando no la hay (desarrollo local).
"""

import json
import logging
import os
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

TABLA = 'kv_store'
TTL_POR_DEFECTO = 60 * 60 * 6  # 6 horas


class _AlmacenMemoria:
    """Respaldo en memoria para desarrollo local y para cuando falla Postgres."""

    def __init__(self):
        self._datos = {}
        self._lock = threading.Lock()

    def set(self, clave: str, valor: Any, ttl: int = TTL_POR_DEFECTO) -> None:
        with self._lock:
            self._datos[clave] = (valor, time.time() + ttl)

    def get(self, clave: str) -> Optional[Any]:
        with self._lock:
            entrada = self._datos.get(clave)
            if not entrada:
                return None
            valor, expira = entrada
            if time.time() > expira:
                del self._datos[clave]
                return None
            return valor

    def delete(self, clave: str) -> None:
        with self._lock:
            self._datos.pop(clave, None)


class _AlmacenPostgres:
    """Guarda los valores como JSON en una tabla de PostgreSQL."""

    def __init__(self, database_url: str):
        from sqlalchemy import create_engine, text

        # Railway y Vercel entregan la URL con el esquema que SQLAlchemy no usa
        if database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
        elif database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql+psycopg2://', 1)

        self._text = text
        # pool_pre_ping evita reutilizar conexiones que el proveedor ya cerró,
        # algo habitual cuando las funciones quedan inactivas entre peticiones.
        self._engine = create_engine(database_url, pool_pre_ping=True, pool_size=2, max_overflow=3)
        self._crear_tabla()

    def _crear_tabla(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(self._text(f"""
                CREATE TABLE IF NOT EXISTS {TABLA} (
                    clave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL,
                    expira_en DOUBLE PRECISION NOT NULL
                )
            """))

    def set(self, clave: str, valor: Any, ttl: int = TTL_POR_DEFECTO) -> None:
        with self._engine.begin() as conn:
            conn.execute(self._text(f"""
                INSERT INTO {TABLA} (clave, valor, expira_en)
                VALUES (:clave, :valor, :expira_en)
                ON CONFLICT (clave) DO UPDATE
                SET valor = EXCLUDED.valor, expira_en = EXCLUDED.expira_en
            """), {'clave': clave, 'valor': json.dumps(valor), 'expira_en': time.time() + ttl})

    def get(self, clave: str) -> Optional[Any]:
        with self._engine.begin() as conn:
            fila = conn.execute(
                self._text(f"SELECT valor, expira_en FROM {TABLA} WHERE clave = :clave"),
                {'clave': clave}
            ).fetchone()

            if not fila:
                return None
            if time.time() > fila[1]:
                conn.execute(self._text(f"DELETE FROM {TABLA} WHERE clave = :clave"), {'clave': clave})
                return None
            return json.loads(fila[0])

    def delete(self, clave: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(self._text(f"DELETE FROM {TABLA} WHERE clave = :clave"), {'clave': clave})

    def limpiar_expirados(self) -> None:
        """Borra las entradas vencidas. Se llama de forma oportunista."""
        with self._engine.begin() as conn:
            conn.execute(self._text(f"DELETE FROM {TABLA} WHERE expira_en < :ahora"), {'ahora': time.time()})


class KVStore:
    """Fachada que elige el respaldo y nunca deja caer la petición.

    Si Postgres falla en mitad de una operación, se degrada a memoria en vez
    de devolver un error 500: perder un CV temporal es preferible a romper la
    página entera.
    """

    def __init__(self):
        self._memoria = _AlmacenMemoria()
        self._postgres = None
        self._contador = 0

        database_url = os.getenv('DATABASE_URL')
        if database_url:
            try:
                self._postgres = _AlmacenPostgres(database_url)
                logger.info("🗄️ KV store usando PostgreSQL")
            except Exception as e:
                logger.error(f"❌ KV store no pudo usar PostgreSQL, usando memoria: {e}")
        else:
            logger.info("🗄️ KV store en memoria (sin DATABASE_URL)")

    @property
    def persistente(self) -> bool:
        """True si el estado sobrevive entre peticiones."""
        return self._postgres is not None

    def set(self, clave: str, valor: Any, ttl: int = TTL_POR_DEFECTO) -> None:
        if self._postgres:
            try:
                self._postgres.set(clave, valor, ttl)
                self._limpiar_de_vez_en_cuando()
                return
            except Exception as e:
                logger.error(f"KV set falló en PostgreSQL: {e}")
        self._memoria.set(clave, valor, ttl)

    def get(self, clave: str) -> Optional[Any]:
        if self._postgres:
            try:
                return self._postgres.get(clave)
            except Exception as e:
                logger.error(f"KV get falló en PostgreSQL: {e}")
        return self._memoria.get(clave)

    def delete(self, clave: str) -> None:
        if self._postgres:
            try:
                self._postgres.delete(clave)
                return
            except Exception as e:
                logger.error(f"KV delete falló en PostgreSQL: {e}")
        self._memoria.delete(clave)

    def _limpiar_de_vez_en_cuando(self) -> None:
        """Purga las entradas vencidas cada 50 escrituras.

        No hay proceso de fondo en serverless, así que la limpieza viaja
        pegada al tráfico normal.
        """
        self._contador += 1
        if self._contador % 50 != 0:
            return
        try:
            self._postgres.limpiar_expirados()
        except Exception as e:
            logger.warning(f"No se pudieron limpiar las claves vencidas: {e}")


_store = None


def get_kv_store() -> KVStore:
    """Instancia compartida del almacén."""
    global _store
    if _store is None:
        _store = KVStore()
    return _store
