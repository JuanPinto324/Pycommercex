from django.contrib import admin

from .models import Cliente, DetalleVenta, Devolucion, Producto, Usuario, Venta


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('identificacion', 'nombre', 'rol', 'activo')
    search_fields = ('identificacion', 'nombre')
    list_filter = ('rol', 'activo')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'precio_venta', 'cantidad_stock', 'stock_minimo', 'activo')
    search_fields = ('codigo', 'nombre')
    list_filter = ('activo',)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('identificacion', 'nombre', 'telefono', 'correo', 'fecha_registro')
    search_fields = ('identificacion', 'nombre', 'telefono', 'correo')


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('id_venta', 'fecha_hora', 'cliente', 'cajero_responsable', 'total')
    date_hierarchy = 'fecha_hora'
    inlines = (DetalleVentaInline,)
    list_select_related = ('cliente', 'cajero_responsable')


@admin.register(DetalleVenta)
class DetalleVentaAdmin(admin.ModelAdmin):
    list_display = ('id_detalle', 'venta', 'producto', 'cantidad', 'subtotal')
    list_select_related = ('venta', 'producto')


@admin.register(Devolucion)
class DevolucionAdmin(admin.ModelAdmin):
    list_display = ('id_devolucion', 'venta', 'producto', 'cantidad', 'usuario_responsable', 'fecha_hora')
    list_select_related = ('venta', 'producto', 'usuario_responsable')
    search_fields = ('motivo', 'producto__nombre', 'venta__id_venta')
