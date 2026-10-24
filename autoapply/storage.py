#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Almacenamiento persistente del módulo de postulación.

Reutiliza el engine de PostgreSQL que ya inicializa utils/database.py cuando
la aplicación corre en producción, y usa archivos JSON atómicos en desarrollo
local. Las tablas se crean solas al arrancar; no hay migraciones manuales.

El almacén es genérico: cada registro es un documento JSON dentro de una
colección (profiles, jobs, runs, cvs, candidate...). Así el módulo no obliga a
cambiar los modelos existentes de usuarios y credenciales.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

TABLA = 'autoapply_records'


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex


def _slug_owner(owner_id: Any) -> str:
    texto = re.sub(r'[^A-Za-z0-9_.-]', '_', str(owner_id))[:80]
    return texto or 'anon'


def _normalizar_url(url: str) -> str:
    """Quita parámetros de seguimiento para que la misma oferta no se duplique."""
    if not url:
        return ''
    base = url.strip().split('#', 1)[0]
    if '?' in base:
        limpio, query = base.split('?', 1)
        utiles = [
            parte for parte in query.split('&')
            if parte and not parte.lower().startswith(('utm_', 'ref=', 'source=', 'trk='))
        ]
        return limpio + ('?' + '&'.join(utiles) if utiles else '')
    return base


class _FicheroJSON:
    """Almacén local por propietario y colección, con escritura atómica."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self._lock = threading.RLock()
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except OSError as exc:
            respaldo = os.path.join(tempfile.gettempdir(), 'job_search_autoapply')
            logger.error(
                "No se pudo usar '%s' (%s). Se usa '%s'; los datos no serán "
                "persistentes en este entorno.", data_dir, exc, respaldo,
            )
            self.data_dir = respaldo
            os.makedirs(self.data_dir, exist_ok=True)

    def _ruta(self, owner_id: Any, collection: str) -> str:
        carpeta = os.path.join(self.data_dir, _slug_owner(owner_id))
        os.makedirs(carpeta, exist_ok=True)
        seguro = re.sub(r'[^A-Za-z0-9_.-]', '_', collection)[:60]
        return os.path.join(carpeta, f'{seguro}.json')

    def _leer(self, ruta: str) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(ruta):
            return {}
        try:
            with open(ruta, 'r', encoding='utf-8') as fh:
                datos = json.load(fh)
            return datos if isinstance(datos, dict) else {}
        except (OSError, ValueError) as exc:
            logger.error("No se pudo leer %s: %s", ruta, exc)
            return {}

    def _escribir(self, ruta: str, datos: Dict[str, Dict[str, Any]]) -> None:
        carpeta = os.path.dirname(ruta)
        fd, temporal = tempfile.mkstemp(dir=carpeta, prefix='.tmp-', suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                json.dump(datos, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temporal, ruta)
        finally:
            if os.path.exists(temporal):
                os.unlink(temporal)

    def get(self, owner_id: Any, collection: str, record_id: str) -> Optional[Dict]:
        with self._lock:
            return copy.deepcopy(self._leer(self._ruta(owner_id, collection)).get(record_id))

    def list(self, owner_id: Any, collection: str) -> List[Dict]:
        with self._lock:
            return [copy.deepcopy(v) for v in self._leer(self._ruta(owner_id, collection)).values()]

    def save(self, owner_id: Any, collection: str, record: Dict,
             unique_fingerprint: bool = False) -> Tuple[Dict, bool]:
        with self._lock:
            ruta = self._ruta(owner_id, collection)
            datos = self._leer(ruta)
            fingerprint = record.get('fingerprint')
            if unique_fingerprint and fingerprint:
                for existente in datos.values():
                    if existente.get('fingerprint') == fingerprint:
                        return copy.deepcopy(existente), False
            datos[record['id']] = copy.deepcopy(record)
            self._escribir(ruta, datos)
            return copy.deepcopy(record), True

    def mutate(self, owner_id: Any, collection: str, record_id: str,
               fn: Callable[[Dict], Dict]) -> Optional[Dict]:
        with self._lock:
            ruta = self._ruta(owner_id, collection)
            datos = self._leer(ruta)
            actual = datos.get(record_id)
            if not actual:
                return None
            nuevo = fn(copy.deepcopy(actual))
            nuevo['id'] = record_id
            nuevo['updated_at'] = ahora_iso()
            datos[record_id] = nuevo
            self._escribir(ruta, datos)
            return copy.deepcopy(nuevo)

    def delete(self, owner_id: Any, collection: str, record_id: str) -> bool:
        with self._lock:
            ruta = self._ruta(owner_id, collection)
            datos = self._leer(ruta)
            if record_id not in datos:
                return False
            del datos[record_id]
            self._escribir(ruta, datos)
            return True

    def delete_collection(self, owner_id: Any, collection: str) -> int:
        with self._lock:
            ruta = self._ruta(owner_id, collection)
            datos = self._leer(ruta)
            total = len(datos)
            self._escribir(ruta, {})
            return total

    def ping(self) -> bool:
        return True


class _Postgres:
    """Tabla única de documentos JSON con restricción de huella por usuario."""

    def __init__(self, engine):
        from sqlalchemy import (
            JSON, Column, DateTime, MetaData, String, Table, UniqueConstraint,
            select,
        )

        self._select = select
        self.engine = engine
        metadata = MetaData()
        self.tabla = Table(
            TABLA, metadata,
            Column('collection', String(40), primary_key=True),
            Column('record_id', String(64), primary_key=True),
            Column('owner_id', String(80), nullable=False, index=True),
            Column('fingerprint', String(128), nullable=True, index=True),
            Column('status', String(40), nullable=True, index=True),
            Column('data', JSON, nullable=False),
            Column('created_at', DateTime(timezone=True), nullable=False),
            Column('updated_at', DateTime(timezone=True), nullable=False),
            UniqueConstraint('owner_id', 'collection', 'fingerprint',
                             name='uq_autoapply_owner_fingerprint'),
        )
        metadata.create_all(self.engine)

    def _fila(self, fila) -> Optional[Dict]:
        if not fila:
            return None
        datos = fila._mapping['data']
        return copy.deepcopy(datos)

    def get(self, owner_id: Any, collection: str, record_id: str) -> Optional[Dict]:
        with self.engine.connect() as conn:
            fila = conn.execute(
                self._select(self.tabla).where(
                    self.tabla.c.owner_id == str(owner_id),
                    self.tabla.c.collection == collection,
                    self.tabla.c.record_id == record_id,
                )
            ).first()
            return self._fila(fila)

    def list(self, owner_id: Any, collection: str) -> List[Dict]:
        with self.engine.connect() as conn:
            filas = conn.execute(
                self._select(self.tabla).where(
                    self.tabla.c.owner_id == str(owner_id),
                    self.tabla.c.collection == collection,
                )
            ).all()
            return [self._fila(f) for f in filas]

    def _insertar(self, conn, record: Dict, collection: str) -> None:
        from sqlalchemy import insert

        conn.execute(insert(self.tabla).values(
            collection=collection,
            record_id=record['id'],
            owner_id=str(record['owner_id']),
            fingerprint=record.get('fingerprint'),
            status=record.get('status'),
            data=record,
            created_at=datetime.fromisoformat(record['created_at']),
            updated_at=datetime.fromisoformat(record['updated_at']),
        ))

    def save(self, owner_id: Any, collection: str, record: Dict,
             unique_fingerprint: bool = False) -> Tuple[Dict, bool]:
        from sqlalchemy import update
        from sqlalchemy.exc import IntegrityError

        record = copy.deepcopy(record)
        try:
            with self.engine.begin() as conn:
                self._insertar(conn, record, collection)
            return record, True
        except IntegrityError:
            if unique_fingerprint and record.get('fingerprint'):
                existente = self.find_by_fingerprint(owner_id, collection, record['fingerprint'])
                if existente:
                    return existente, False
            with self.engine.begin() as conn:
                conn.execute(update(self.tabla).where(
                    self.tabla.c.owner_id == str(owner_id),
                    self.tabla.c.collection == collection,
                    self.tabla.c.record_id == record['id'],
                ).values(
                    fingerprint=record.get('fingerprint'),
                    status=record.get('status'),
                    data=record,
                    updated_at=datetime.fromisoformat(record['updated_at']),
                ))
            return record, True

    def find_by_fingerprint(self, owner_id: Any, collection: str, fingerprint: str) -> Optional[Dict]:
        with self.engine.connect() as conn:
            fila = conn.execute(
                self._select(self.tabla).where(
                    self.tabla.c.owner_id == str(owner_id),
                    self.tabla.c.collection == collection,
                    self.tabla.c.fingerprint == fingerprint,
                )
            ).first()
            return self._fila(fila)

    def mutate(self, owner_id: Any, collection: str, record_id: str,
               fn: Callable[[Dict], Dict]) -> Optional[Dict]:
        from sqlalchemy import update

        with self.engine.begin() as conn:
            fila = conn.execute(
                self._select(self.tabla).where(
                    self.tabla.c.owner_id == str(owner_id),
                    self.tabla.c.collection == collection,
                    self.tabla.c.record_id == record_id,
                ).with_for_update()
            ).first()
            if not fila:
                return None
            actual = self._fila(fila)
            nuevo = fn(copy.deepcopy(actual))
            nuevo['id'] = record_id
            nuevo['owner_id'] = actual.get('owner_id', owner_id)
            nuevo['created_at'] = actual.get('created_at', ahora_iso())
            nuevo['updated_at'] = ahora_iso()
            conn.execute(update(self.tabla).where(
                self.tabla.c.owner_id == str(owner_id),
                self.tabla.c.collection == collection,
                self.tabla.c.record_id == record_id,
            ).values(
                fingerprint=nuevo.get('fingerprint'),
                status=nuevo.get('status'),
                data=nuevo,
                updated_at=datetime.fromisoformat(nuevo['updated_at']),
            ))
            return nuevo

    def delete(self, owner_id: Any, collection: str, record_id: str) -> bool:
        from sqlalchemy import delete

        with self.engine.begin() as conn:
            resultado = conn.execute(delete(self.tabla).where(
                self.tabla.c.owner_id == str(owner_id),
                self.tabla.c.collection == collection,
                self.tabla.c.record_id == record_id,
            ))
            return resultado.rowcount > 0

    def delete_collection(self, owner_id: Any, collection: str) -> int:
        from sqlalchemy import delete

        with self.engine.begin() as conn:
            resultado = conn.execute(delete(self.tabla).where(
                self.tabla.c.owner_id == str(owner_id),
                self.tabla.c.collection == collection,
            ))
            return resultado.rowcount or 0

    def ping(self) -> bool:
        from sqlalchemy import text

        with self.engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return True


class Store:
    """Fachada de almacenamiento usada por rutas, motor y worker."""

    def __init__(self, data_dir: Optional[str] = None, database_url: Optional[str] = None):
        self.data_dir = data_dir or os.getenv('AUTOAPPLY_DATA_DIR') or os.path.join('data', 'autoapply')
        self._pg = None
        self._json = None

        engine = None
        if database_url:
            try:
                from sqlalchemy import create_engine
                url = database_url
                if url.startswith('postgres://'):
                    url = url.replace('postgres://', 'postgresql+psycopg2://', 1)
                elif url.startswith('postgresql://'):
                    url = url.replace('postgresql://', 'postgresql+psycopg2://', 1)
                engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=3)
            except Exception as exc:  # noqa: BLE001
                logger.error('AutoApply: no se pudo preparar PostgreSQL (%s)', exc)
        elif database_url is None:
            try:
                from utils.database import db as base_db
                engine = getattr(base_db, 'engine', None)
            except Exception:
                engine = None

        if engine is not None:
            try:
                self._pg = _Postgres(engine)
                logger.info('AutoApply: almacenamiento PostgreSQL')
            except Exception as exc:  # noqa: BLE001 - se degrada a JSON
                logger.error('AutoApply: PostgreSQL no disponible (%s); usando JSON', exc)
        if self._pg is None:
            self._json = _FicheroJSON(self.data_dir)
            logger.info('AutoApply: almacenamiento JSON en %s', self._json.data_dir)

    @property
    def persistente(self) -> bool:
        return self._pg is not None

    def save(self, collection: str, owner_id: Any, record: Dict,
             record_id: Optional[str] = None,
             unique_fingerprint: bool = False) -> Tuple[Dict, bool]:
        ahora = ahora_iso()
        record = copy.deepcopy(record)
        record.setdefault('id', record_id or _id())
        record['owner_id'] = str(owner_id)
        record.setdefault('created_at', ahora)
        record['updated_at'] = ahora

        if self._pg:
            return self._pg.save(owner_id, collection, record, unique_fingerprint)
        return self._json.save(owner_id, collection, record, unique_fingerprint)

    def get(self, collection: str, owner_id: Any, record_id: str) -> Optional[Dict]:
        if self._pg:
            return self._pg.get(owner_id, collection, record_id)
        return self._json.get(owner_id, collection, record_id)

    def list(self, collection: str, owner_id: Any,
             where: Optional[Callable[[Dict], bool]] = None,
             limit: Optional[int] = None) -> List[Dict]:
        if self._pg:
            registros = self._pg.list(owner_id, collection)
        else:
            registros = self._json.list(owner_id, collection)
        if where:
            registros = [r for r in registros if where(r)]
        registros.sort(key=lambda r: r.get('created_at', ''), reverse=True)
        return registros[:limit] if limit else registros

    def find_by_fingerprint(self, collection: str, owner_id: Any, fingerprint: str) -> Optional[Dict]:
        if self._pg:
            return self._pg.find_by_fingerprint(owner_id, collection, fingerprint)
        for registro in self._json.list(owner_id, collection):
            if registro.get('fingerprint') == fingerprint:
                return registro
        return None

    def mutate(self, collection: str, owner_id: Any, record_id: str,
               fn: Callable[[Dict], Dict]) -> Optional[Dict]:
        if self._pg:
            return self._pg.mutate(owner_id, collection, record_id, fn)
        return self._json.mutate(owner_id, collection, record_id, fn)

    def delete(self, collection: str, owner_id: Any, record_id: str) -> bool:
        if self._pg:
            return self._pg.delete(owner_id, collection, record_id)
        return self._json.delete(owner_id, collection, record_id)

    def delete_collection(self, collection: str, owner_id: Any) -> int:
        if self._pg:
            return self._pg.delete_collection(owner_id, collection)
        return self._json.delete_collection(owner_id, collection)

    def ping(self) -> bool:
        try:
            return self._pg.ping() if self._pg else self._json.ping()
        except Exception:
            return False


_store: Optional[Store] = None
_store_lock = threading.Lock()


def get_store() -> Store:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = Store()
    return _store


def reset_store_for_tests(store: Optional[Store] = None) -> None:
    """Permite que las pruebas usen un directorio temporal aislado."""
    global _store
    with _store_lock:
        _store = store


def huella_job(job: Dict[str, Any]) -> str:
    """Huella estable de una oferta.

    Prioriza el identificador del portal; si no existe, usa la URL
    normalizada; como último recurso, empresa + cargo + ubicación.
    """
    import hashlib

    portal = (job.get('portal') or '').strip().lower()
    external_id = str(job.get('external_id') or '').strip()
    if external_id:
        clave = f'{portal}|id|{external_id}'
    else:
        url = _normalizar_url(job.get('url') or job.get('link') or '')
        if url:
            clave = f'{portal}|url|{url.lower()}'
        else:
            empresa = re.sub(r'\s+', ' ', (job.get('empresa') or '')).strip().lower()
            titulo = re.sub(r'\s+', ' ', (job.get('titulo') or '')).strip().lower()
            ubicacion = re.sub(r'\s+', ' ', (job.get('ubicacion') or '')).strip().lower()
            clave = f'{portal}|empresa_cargo|{empresa}|{titulo}|{ubicacion}'
    return hashlib.sha256(clave.encode('utf-8')).hexdigest()


def huella_empresa_cargo(job: Dict[str, Any]) -> str:
    """Segunda huella para detectar la misma vacante publicada en dos portales."""
    import hashlib

    empresa = re.sub(r'[^a-z0-9]+', ' ', (job.get('empresa') or '').lower()).strip()
    titulo = re.sub(r'[^a-z0-9]+', ' ', (job.get('titulo') or '').lower()).strip()
    ubicacion = re.sub(r'[^a-z0-9]+', ' ', (job.get('ubicacion') or '').lower()).strip()
    if not empresa or not titulo or empresa in ('no especificada', 'computrabajo'):
        return ''
    clave = f'{empresa}|{titulo}|{ubicacion}'
    return hashlib.sha256(clave.encode('utf-8')).hexdigest()
