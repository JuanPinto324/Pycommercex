from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.utils import timezone

class Usuario(models.Model):
    ADMIN = 'ADMIN'
    CAJERO = 'CAJERO'
    ROLES = (
        (ADMIN, 'Administrador'),
        (CAJERO, 'Cajero'),
    )

    id_usuario = models.AutoField(primary_key=True)
    identificacion = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    password = models.CharField(max_length=128)
    rol = models.CharField(max_length=20, choices=ROLES, default=CAJERO)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'USUARIOS'
        managed = False  # Le indica a Django que la tabla ya existe en MySQL

    def __str__(self):
        return f"{self.nombre} - {self.rol}"

class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_stock = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=5)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'PRODUCTOS'
        managed = False

    def __str__(self):
        return f"[{self.codigo}] {self.nombre}"

    @property
    def necesita_reposicion(self):
        return self.cantidad_stock <= self.stock_minimo

    @property
    def esta_agotado(self):
        return self.cantidad_stock == 0

    @property
    def margen_unitario(self):
        return self.precio_venta - self.precio_costo

    @property
    def precio_venta_entero(self):
        return int(self.precio_venta.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    identificacion = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=120)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    correo = models.EmailField(max_length=120, blank=True, null=True)
    fecha_registro = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'CLIENTES'
        managed = False

    def __str__(self):
        return f"{self.identificacion} - {self.nombre}"

class Venta(models.Model):
    id_venta = models.AutoField(primary_key=True)
    fecha_hora = models.DateTimeField(default=timezone.now)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cliente = models.ForeignKey(Cliente, on_delete=models.RESTRICT, db_column='cliente_id', blank=True, null=True)
    cajero_responsable = models.ForeignKey(Usuario, on_delete=models.RESTRICT, db_column='cajero_responsable_id')

    class Meta:
        db_table = 'VENTAS'
        managed = False

    def __str__(self):
        return f"Venta {self.id_venta}"

class DetalleVenta(models.Model):
    id_detalle = models.AutoField(primary_key=True)
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, db_column='id_venta')
    producto = models.ForeignKey(Producto, on_delete=models.RESTRICT, db_column='id_producto')
    cantidad = models.IntegerField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'DETALLE_VENTA'
        managed = False


class Devolucion(models.Model):
    id_devolucion = models.AutoField(primary_key=True)
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, db_column='id_venta')
    detalle = models.ForeignKey(DetalleVenta, on_delete=models.RESTRICT, db_column='id_detalle')
    producto = models.ForeignKey(Producto, on_delete=models.RESTRICT, db_column='id_producto')
    cantidad = models.IntegerField()
    motivo = models.CharField(max_length=250)
    usuario_responsable = models.ForeignKey(Usuario, on_delete=models.RESTRICT, db_column='usuario_responsable_id')
    fecha_hora = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'DEVOLUCIONES'
        managed = False
