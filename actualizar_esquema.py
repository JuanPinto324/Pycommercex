import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
from django.db import connection

django.setup()


def columna_existe(tabla, columna):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = %s
            """,
            [tabla, columna],
        )
        return cursor.fetchone()[0] > 0


def tabla_existe(tabla):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            """,
            [tabla],
        )
        return cursor.fetchone()[0] > 0


def constraint_existe(nombre):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
            WHERE TABLE_SCHEMA = DATABASE()
              AND CONSTRAINT_NAME = %s
            """,
            [nombre],
        )
        return cursor.fetchone()[0] > 0


def foreign_key_existe(tabla, columna, tabla_referenciada):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = %s
              AND REFERENCED_TABLE_NAME = %s
            """,
            [tabla, columna, tabla_referenciada],
        )
        return cursor.fetchone()[0] > 0


def agregar_columna_si_falta(tabla, columna, definicion):
    if not columna_existe(tabla, columna):
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")


def agregar_foreign_key_si_falta(nombre, tabla, columna, tabla_referenciada, sql):
    if not constraint_existe(nombre) and not foreign_key_existe(tabla, columna, tabla_referenciada):
        with connection.cursor() as cursor:
            cursor.execute(sql)


with connection.cursor() as cursor:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS USUARIOS (
            id_usuario INT AUTO_INCREMENT PRIMARY KEY,
            identificacion VARCHAR(20) UNIQUE NOT NULL,
            nombre VARCHAR(100) NOT NULL,
            password VARCHAR(128) NOT NULL,
            rol ENUM('ADMIN', 'CAJERO') DEFAULT 'CAJERO' NOT NULL,
            activo BOOLEAN DEFAULT TRUE NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS PRODUCTOS (
            id_producto INT AUTO_INCREMENT PRIMARY KEY,
            codigo VARCHAR(50) UNIQUE NOT NULL,
            nombre VARCHAR(150) NOT NULL,
            precio_costo DECIMAL(10,2) NOT NULL,
            precio_venta DECIMAL(10,2) NOT NULL,
            cantidad_stock INT DEFAULT 0 NOT NULL,
            stock_minimo INT DEFAULT 5 NOT NULL,
            activo BOOLEAN DEFAULT TRUE NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS CLIENTES (
            id_cliente INT AUTO_INCREMENT PRIMARY KEY,
            identificacion VARCHAR(20) UNIQUE NOT NULL,
            nombre VARCHAR(120) NOT NULL,
            telefono VARCHAR(30) NULL,
            correo VARCHAR(120) NULL,
            fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS VENTAS (
            id_venta INT AUTO_INCREMENT PRIMARY KEY,
            fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            total DECIMAL(12,2) DEFAULT 0.00 NOT NULL,
            cliente_id INT NULL,
            cajero_responsable_id INT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS DETALLE_VENTA (
            id_detalle INT AUTO_INCREMENT PRIMARY KEY,
            id_venta INT NOT NULL,
            id_producto INT NOT NULL,
            cantidad INT NOT NULL,
            subtotal DECIMAL(10,2) NOT NULL
        )
        """
    )

agregar_columna_si_falta("USUARIOS", "activo", "BOOLEAN DEFAULT TRUE NOT NULL")
agregar_columna_si_falta("PRODUCTOS", "activo", "BOOLEAN DEFAULT TRUE NOT NULL")
agregar_columna_si_falta("VENTAS", "cliente_id", "INT NULL AFTER total")

agregar_foreign_key_si_falta(
    "fk_ventas_cajero",
    "VENTAS",
    "cajero_responsable_id",
    "USUARIOS",
    """
    ALTER TABLE VENTAS
    ADD CONSTRAINT fk_ventas_cajero
    FOREIGN KEY (cajero_responsable_id) REFERENCES USUARIOS(id_usuario)
    ON DELETE RESTRICT
    """,
)
agregar_foreign_key_si_falta(
    "fk_ventas_cliente",
    "VENTAS",
    "cliente_id",
    "CLIENTES",
    """
    ALTER TABLE VENTAS
    ADD CONSTRAINT fk_ventas_cliente
    FOREIGN KEY (cliente_id) REFERENCES CLIENTES(id_cliente)
    ON DELETE RESTRICT
    """,
)
agregar_foreign_key_si_falta(
    "fk_detalle_venta",
    "DETALLE_VENTA",
    "id_venta",
    "VENTAS",
    """
    ALTER TABLE DETALLE_VENTA
    ADD CONSTRAINT fk_detalle_venta
    FOREIGN KEY (id_venta) REFERENCES VENTAS(id_venta)
    ON DELETE CASCADE
    """,
)
agregar_foreign_key_si_falta(
    "fk_detalle_producto",
    "DETALLE_VENTA",
    "id_producto",
    "PRODUCTOS",
    """
    ALTER TABLE DETALLE_VENTA
    ADD CONSTRAINT fk_detalle_producto
    FOREIGN KEY (id_producto) REFERENCES PRODUCTOS(id_producto)
    ON DELETE RESTRICT
    """,
)

with connection.cursor() as cursor:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS DEVOLUCIONES (
            id_devolucion INT AUTO_INCREMENT PRIMARY KEY,
            id_venta INT NOT NULL,
            id_detalle INT NOT NULL,
            id_producto INT NOT NULL,
            cantidad INT NOT NULL,
            motivo VARCHAR(250) NOT NULL,
            usuario_responsable_id INT NOT NULL,
            fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """
    )

agregar_foreign_key_si_falta(
    "fk_devoluciones_venta",
    "DEVOLUCIONES",
    "id_venta",
    "VENTAS",
    """
    ALTER TABLE DEVOLUCIONES
    ADD CONSTRAINT fk_devoluciones_venta
    FOREIGN KEY (id_venta) REFERENCES VENTAS(id_venta)
    ON DELETE CASCADE
    """,
)
agregar_foreign_key_si_falta(
    "fk_devoluciones_detalle",
    "DEVOLUCIONES",
    "id_detalle",
    "DETALLE_VENTA",
    """
    ALTER TABLE DEVOLUCIONES
    ADD CONSTRAINT fk_devoluciones_detalle
    FOREIGN KEY (id_detalle) REFERENCES DETALLE_VENTA(id_detalle)
    ON DELETE RESTRICT
    """,
)
agregar_foreign_key_si_falta(
    "fk_devoluciones_producto",
    "DEVOLUCIONES",
    "id_producto",
    "PRODUCTOS",
    """
    ALTER TABLE DEVOLUCIONES
    ADD CONSTRAINT fk_devoluciones_producto
    FOREIGN KEY (id_producto) REFERENCES PRODUCTOS(id_producto)
    ON DELETE RESTRICT
    """,
)
agregar_foreign_key_si_falta(
    "fk_devoluciones_usuario",
    "DEVOLUCIONES",
    "usuario_responsable_id",
    "USUARIOS",
    """
    ALTER TABLE DEVOLUCIONES
    ADD CONSTRAINT fk_devoluciones_usuario
    FOREIGN KEY (usuario_responsable_id) REFERENCES USUARIOS(id_usuario)
    ON DELETE RESTRICT
    """,
)

print("Estructura de PyCommerce lista.")
