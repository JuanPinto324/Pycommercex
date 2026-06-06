CREATE DATABASE IF NOT EXISTS pycommerce;
USE pycommerce;

CREATE TABLE IF NOT EXISTS USUARIOS (
    id_usuario INT AUTO_INCREMENT PRIMARY KEY,
    identificacion VARCHAR(20) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    password VARCHAR(128) NOT NULL,
    rol ENUM('ADMIN', 'CAJERO') DEFAULT 'CAJERO' NOT NULL,
    activo BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE IF NOT EXISTS PRODUCTOS (
    id_producto INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    precio_costo DECIMAL(10,2) NOT NULL,
    precio_venta DECIMAL(10,2) NOT NULL,
    cantidad_stock INT DEFAULT 0 NOT NULL,
    stock_minimo INT DEFAULT 5 NOT NULL,
    activo BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE IF NOT EXISTS CLIENTES (
    id_cliente INT AUTO_INCREMENT PRIMARY KEY,
    identificacion VARCHAR(20) UNIQUE NOT NULL,
    nombre VARCHAR(120) NOT NULL,
    telefono VARCHAR(30) NULL,
    correo VARCHAR(120) NULL,
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS VENTAS (
    id_venta INT AUTO_INCREMENT PRIMARY KEY,
    fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    total DECIMAL(12,2) DEFAULT 0.00 NOT NULL,
    cliente_id INT NULL,
    cajero_responsable_id INT NOT NULL,
    CONSTRAINT fk_ventas_cliente
        FOREIGN KEY (cliente_id) REFERENCES CLIENTES(id_cliente)
        ON DELETE RESTRICT,
    CONSTRAINT fk_ventas_cajero
        FOREIGN KEY (cajero_responsable_id) REFERENCES USUARIOS(id_usuario)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS DETALLE_VENTA (
    id_detalle INT AUTO_INCREMENT PRIMARY KEY,
    id_venta INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad INT NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_detalle_venta
        FOREIGN KEY (id_venta) REFERENCES VENTAS(id_venta)
        ON DELETE CASCADE,
    CONSTRAINT fk_detalle_producto
        FOREIGN KEY (id_producto) REFERENCES PRODUCTOS(id_producto)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS DEVOLUCIONES (
    id_devolucion INT AUTO_INCREMENT PRIMARY KEY,
    id_venta INT NOT NULL,
    id_detalle INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad INT NOT NULL,
    motivo VARCHAR(250) NOT NULL,
    usuario_responsable_id INT NOT NULL,
    fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT fk_devoluciones_venta
        FOREIGN KEY (id_venta) REFERENCES VENTAS(id_venta)
        ON DELETE CASCADE,
    CONSTRAINT fk_devoluciones_detalle
        FOREIGN KEY (id_detalle) REFERENCES DETALLE_VENTA(id_detalle)
        ON DELETE RESTRICT,
    CONSTRAINT fk_devoluciones_producto
        FOREIGN KEY (id_producto) REFERENCES PRODUCTOS(id_producto)
        ON DELETE RESTRICT,
    CONSTRAINT fk_devoluciones_usuario
        FOREIGN KEY (usuario_responsable_id) REFERENCES USUARIOS(id_usuario)
        ON DELETE RESTRICT
);
