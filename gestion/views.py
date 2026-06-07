from datetime import date
from datetime import datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
import json
import random

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import F, Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Cliente, DetalleVenta, Devolucion, Producto, Usuario, Venta


ROLES_ADMIN = {'ADMIN'}
ROLES_OPERATIVOS = {'ADMIN', 'CAJERO'}


def login_requerido(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('usuario_id'):
            return redirect('login')
        return view_func(request, *args, **kwargs)

    return wrapper


def rol_requerido(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.session.get('usuario_id'):
                return redirect('login')
            if request.session.get('usuario_rol') not in roles:
                messages.warning(request, 'No tienes permisos para acceder a ese modulo.')
                return redirect('pos')
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def _decimal_positivo(valor, campo):
    try:
        texto = str(valor or '').strip().replace(',', '.')
        numero = Decimal(texto)
    except (InvalidOperation, TypeError):
        raise ValueError(f'{campo} debe ser un numero valido.')
    if numero < 0:
        raise ValueError(f'{campo} no puede ser negativo.')
    return numero.quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def _entero_no_negativo(valor, campo):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f'{campo} debe ser un numero entero.')
    if numero < 0:
        raise ValueError(f'{campo} no puede ser negativo.')
    return numero


def _usuario_actual(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None
    return Usuario.objects.filter(id_usuario=usuario_id).first()


def _normalizar_rol(rol):
    return (rol or '').strip().upper()


def _texto_obligatorio(valor, campo, minimo=2, maximo=120):
    texto = (valor or '').strip()
    if len(texto) < minimo:
        raise ValueError(f'{campo} es obligatorio.')
    if len(texto) > maximo:
        raise ValueError(f'{campo} no puede superar {maximo} caracteres.')
    return texto


def _generar_captcha(request):
    numero_a = random.randint(2, 9)
    numero_b = random.randint(1, 9)
    request.session['captcha_login'] = str(numero_a + numero_b)
    return f'{numero_a} + {numero_b}'


def _render_login(request, error=None):
    return render(request, 'gestion/login.html', {
        'error': error,
        'captcha_pregunta': _generar_captcha(request),
    })


def _rango_dia(fecha):
    inicio = timezone.make_aware(datetime.combine(fecha, time.min), timezone.get_current_timezone())
    fin = timezone.make_aware(datetime.combine(fecha, time.max), timezone.get_current_timezone())
    return inicio, fin


@rol_requerido(*ROLES_ADMIN)
def dashboard(request):
    hoy = timezone.localdate()
    inicio_hoy, fin_hoy = _rango_dia(hoy)
    ventas_hoy_qs = Venta.objects.filter(fecha_hora__range=(inicio_hoy, fin_hoy))
    ventas_hoy = ventas_hoy_qs.aggregate(total_dia=Sum('total'))['total_dia'] or Decimal('0.00')
    facturas_hoy = ventas_hoy_qs.count()
    productos_activos = Producto.objects.filter(activo=True)
    total_productos = productos_activos.count()
    unidades_stock = productos_activos.aggregate(total=Sum('cantidad_stock'))['total'] or 0
    productos_criticos = productos_activos.filter(cantidad_stock__lte=F('stock_minimo')).order_by('cantidad_stock', 'nombre')
    total_alertas = productos_criticos.count()
    productos_agotados = productos_criticos.filter(cantidad_stock=0).count()

    contexto = {
        'ventas_hoy': ventas_hoy,
        'facturas_hoy': facturas_hoy,
        'total_productos': total_productos,
        'unidades_stock': unidades_stock,
        'total_alertas': total_alertas,
        'productos_agotados': productos_agotados,
        'productos_criticos': productos_criticos,
    }
    return render(request, 'gestion/dashboard.html', contexto)


@login_requerido
def punto_de_venta(request):
    productos = Producto.objects.filter(activo=True, cantidad_stock__gt=0).order_by('nombre')
    return render(request, 'gestion/pos.html', {'productos': productos})


@login_requerido
def guardar_venta(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo no permitido.'}, status=405)

    try:
        datos = json.loads(request.body)
        carrito = datos.get('carrito', [])
        cliente_datos = datos.get('cliente', {})

        if not carrito:
            return JsonResponse({'error': 'El carrito esta vacio.'}, status=400)

        usuario = _usuario_actual(request)
        if not usuario or _normalizar_rol(usuario.rol) not in ROLES_OPERATIVOS:
            return JsonResponse({'error': 'Sesion invalida o sin permisos para vender.'}, status=403)

        cliente_identificacion = _texto_obligatorio(
            cliente_datos.get('identificacion'),
            'La identificacion del cliente',
            minimo=4,
            maximo=20,
        )
        cliente_nombre = _texto_obligatorio(cliente_datos.get('nombre'), 'El nombre del cliente')
        cliente_telefono = (cliente_datos.get('telefono') or '').strip()[:30] or None
        cliente_correo = (cliente_datos.get('correo') or '').strip()[:120] or None

        cantidades_por_producto = {}
        for item in carrito:
            producto_id = int(item.get('id'))
            cantidad = _entero_no_negativo(item.get('cantidad'), 'La cantidad')
            if cantidad <= 0:
                raise ValueError('La cantidad debe ser mayor a cero.')
            cantidades_por_producto[producto_id] = cantidades_por_producto.get(producto_id, 0) + cantidad

        ids = list(cantidades_por_producto.keys())

        with transaction.atomic():
            cliente, creado = Cliente.objects.get_or_create(
                identificacion=cliente_identificacion,
                defaults={
                    'nombre': cliente_nombre,
                    'telefono': cliente_telefono,
                    'correo': cliente_correo,
                },
            )
            if not creado:
                cliente.nombre = cliente_nombre
                cliente.telefono = cliente_telefono
                cliente.correo = cliente_correo
                cliente.save(update_fields=['nombre', 'telefono', 'correo'])

            productos = {
                producto.id_producto: producto
                for producto in Producto.objects.select_for_update().filter(id_producto__in=ids, activo=True)
            }

            if len(productos) != len(ids):
                return JsonResponse({'error': 'Uno o mas productos ya no existen.'}, status=400)

            total = Decimal('0')
            detalles = []

            for producto_id, cantidad in cantidades_por_producto.items():
                producto = productos[producto_id]
                if producto.cantidad_stock < cantidad:
                    raise ValueError(f'Stock insuficiente para {producto.nombre}. Disponible: {producto.cantidad_stock}.')

                subtotal = producto.precio_venta * cantidad
                total += subtotal
                producto.cantidad_stock -= cantidad
                producto.save(update_fields=['cantidad_stock'])
                detalles.append((producto, cantidad, subtotal))

            nueva_venta = Venta.objects.create(total=total, cliente=cliente, cajero_responsable=usuario)
            DetalleVenta.objects.bulk_create([
                DetalleVenta(
                    venta=nueva_venta,
                    producto=producto,
                    cantidad=cantidad,
                    subtotal=subtotal,
                )
                for producto, cantidad, subtotal in detalles
            ])

        return JsonResponse({
            'mensaje': 'Venta registrada con exito.',
            'id_venta': nueva_venta.id_venta,
            'total': str(total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
        })

    except (TypeError, ValueError, json.JSONDecodeError) as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception:
        return JsonResponse({'error': 'No fue posible registrar la venta. Revisa los datos e intenta de nuevo.'}, status=400)


@rol_requerido(*ROLES_ADMIN)
def gestionar_productos(request):
    if request.method == 'POST':
        try:
            accion = request.POST.get('accion', 'crear')
            if accion == 'eliminar':
                producto = get_object_or_404(Producto, id_producto=request.POST.get('id_producto'))
                producto.activo = False
                producto.save(update_fields=['activo'])
                messages.success(request, 'Producto retirado del catalogo activo.')
                return redirect('productos')

            codigo = (request.POST.get('codigo') or '').strip().upper()
            nombre = (request.POST.get('nombre') or '').strip()
            precio_costo = _decimal_positivo(request.POST.get('precio_costo'), 'El precio de costo')
            precio_venta = _decimal_positivo(request.POST.get('precio_venta'), 'El precio de venta')
            cantidad_stock = _entero_no_negativo(request.POST.get('cantidad_stock'), 'El stock')
            stock_minimo = _entero_no_negativo(request.POST.get('stock_minimo'), 'El stock minimo')

            if not codigo or not nombre:
                raise ValueError('Codigo y nombre son obligatorios.')
            if precio_venta < precio_costo:
                raise ValueError('El precio de venta no puede ser menor al costo.')

            if accion == 'editar':
                producto = get_object_or_404(Producto, id_producto=request.POST.get('id_producto'))
                duplicado = Producto.objects.filter(codigo=codigo).exclude(id_producto=producto.id_producto).exists()
                if duplicado:
                    raise ValueError('Ya existe otro producto con ese codigo.')
                producto.codigo = codigo
                producto.nombre = nombre
                producto.precio_costo = precio_costo
                producto.precio_venta = precio_venta
                producto.cantidad_stock = cantidad_stock
                producto.stock_minimo = stock_minimo
                producto.activo = True
                producto.save()
                messages.success(request, 'Producto actualizado correctamente.')
            else:
                producto_inactivo = Producto.objects.filter(codigo=codigo, activo=False).first()
                if producto_inactivo:
                    producto_inactivo.nombre = nombre
                    producto_inactivo.precio_costo = precio_costo
                    producto_inactivo.precio_venta = precio_venta
                    producto_inactivo.cantidad_stock = cantidad_stock
                    producto_inactivo.stock_minimo = stock_minimo
                    producto_inactivo.activo = True
                    producto_inactivo.save()
                    messages.success(request, 'Producto reactivado correctamente.')
                elif Producto.objects.filter(codigo=codigo).exists():
                    raise ValueError('Ya existe un producto con ese codigo.')
                else:
                    Producto.objects.create(
                        codigo=codigo,
                        nombre=nombre,
                        precio_costo=precio_costo,
                        precio_venta=precio_venta,
                        cantidad_stock=cantidad_stock,
                        stock_minimo=stock_minimo,
                        activo=True,
                    )
                    messages.success(request, 'Producto creado correctamente.')
        except Exception as e:
            messages.error(request, str(e))

        return redirect('productos')

    productos = Producto.objects.filter(activo=True).order_by('nombre')
    resumen = productos.aggregate(
        unidades=Sum('cantidad_stock'),
        valor_costo=Sum(F('cantidad_stock') * F('precio_costo')),
        valor_venta=Sum(F('cantidad_stock') * F('precio_venta')),
    )
    return render(request, 'gestion/productos.html', {
        'productos': productos,
        'resumen': resumen,
        'alertas': productos.filter(cantidad_stock__lte=F('stock_minimo')).count(),
    })


@rol_requerido(*ROLES_ADMIN)
def gestionar_usuarios(request):
    if request.method == 'POST':
        try:
            accion = request.POST.get('accion', 'crear')
            if accion == 'eliminar':
                usuario = get_object_or_404(Usuario, id_usuario=request.POST.get('id_usuario'), rol='CAJERO')
                if usuario.id_usuario == request.session.get('usuario_id'):
                    raise ValueError('No puedes eliminar tu propio usuario activo.')
                usuario.activo = False
                usuario.save(update_fields=['activo'])
                messages.success(request, 'Cajero retirado correctamente.')
                return redirect('usuarios')

            nombre = (request.POST.get('nombre') or '').strip()
            identificacion = (request.POST.get('identificacion') or '').strip()
            password = request.POST.get('password') or ''
            rol = _normalizar_rol(request.POST.get('rol'))

            if not nombre or not identificacion:
                raise ValueError('Nombre e identificacion son obligatorios.')
            if rol not in ROLES_OPERATIVOS:
                raise ValueError('Rol invalido.')
            if len(password) < 8:
                raise ValueError('La contrasena debe tener al menos 8 caracteres.')
            usuario_inactivo = Usuario.objects.filter(identificacion=identificacion, activo=False).first()
            if usuario_inactivo:
                usuario_inactivo.nombre = nombre
                usuario_inactivo.password = make_password(password)
                usuario_inactivo.rol = rol
                usuario_inactivo.activo = True
                usuario_inactivo.save(update_fields=['nombre', 'password', 'rol', 'activo'])
                messages.success(request, 'Usuario reactivado correctamente.')
            elif Usuario.objects.filter(identificacion=identificacion).exists():
                raise ValueError('Ya existe un usuario activo con esa identificacion.')
            else:
                Usuario.objects.create(
                    nombre=nombre,
                    identificacion=identificacion,
                    password=make_password(password),
                    rol=rol,
                    activo=True,
                )
                messages.success(request, 'Usuario registrado correctamente.')
        except Exception as e:
            messages.error(request, str(e))
        return redirect('usuarios')

    usuarios = Usuario.objects.filter(activo=True).order_by('nombre')
    return render(request, 'gestion/usuarios.html', {'usuarios': usuarios})


def login_view(request):
    if request.session.get('usuario_id'):
        if request.session.get('usuario_rol') == 'ADMIN':
            return redirect('dashboard')
        return redirect('pos')

    if request.method == 'POST':
        identificacion = (request.POST.get('identificacion') or '').strip()
        password = request.POST.get('password') or ''
        captcha_respuesta = (request.POST.get('captcha') or '').strip()

        try:
            if captcha_respuesta != request.session.get('captcha_login'):
                return _render_login(request, 'Verificacion incorrecta. Resuelve nuevamente el CAPTCHA.')

            usuario = Usuario.objects.get(identificacion=identificacion)
            if not usuario.activo:
                return _render_login(request, 'Usuario inactivo. Contacta al administrador.')

            password_ok = check_password(password, usuario.password)
            es_password_legacy = usuario.password == password

            if not password_ok and not es_password_legacy:
                raise Usuario.DoesNotExist

            if es_password_legacy:
                usuario.password = make_password(password)
                usuario.save(update_fields=['password'])

            request.session.cycle_key()
            request.session['usuario_id'] = usuario.id_usuario
            request.session['usuario_nombre'] = usuario.nombre
            request.session['usuario_rol'] = _normalizar_rol(usuario.rol)

            if _normalizar_rol(usuario.rol) == 'ADMIN':
                return redirect('dashboard')
            return redirect('pos')

        except Usuario.DoesNotExist:
            return _render_login(request, 'No existe el usuario con id {identificacion}')

    return _render_login(request)


def logout_view(request):
    request.session.flush()
    return redirect('login')


@rol_requerido(*ROLES_ADMIN)
def registrar_devolucion(request):
    if request.method != 'POST':
        return redirect('historial')

    try:
        detalle = get_object_or_404(
            DetalleVenta.objects.select_related('venta', 'producto'),
            id_detalle=request.POST.get('id_detalle'),
        )
        cantidad = _entero_no_negativo(request.POST.get('cantidad'), 'La cantidad devuelta')
        motivo = _texto_obligatorio(request.POST.get('motivo'), 'El motivo de la devolucion', minimo=5, maximo=250)
        usuario = _usuario_actual(request)

        if not usuario:
            raise ValueError('Sesion invalida.')
        if cantidad <= 0:
            raise ValueError('La cantidad devuelta debe ser mayor a cero.')

        with transaction.atomic():
            devuelto = Devolucion.objects.filter(detalle=detalle).aggregate(total=Sum('cantidad'))['total'] or 0
            disponible = detalle.cantidad - devuelto
            if cantidad > disponible:
                raise ValueError(f'Solo quedan {disponible} unidades disponibles para devolver en este detalle.')

            producto = Producto.objects.select_for_update().get(id_producto=detalle.producto_id)
            producto.cantidad_stock += cantidad
            producto.save(update_fields=['cantidad_stock'])

            Devolucion.objects.create(
                venta=detalle.venta,
                detalle=detalle,
                producto=producto,
                cantidad=cantidad,
                motivo=motivo,
                usuario_responsable=usuario,
            )

        messages.success(request, 'Devolucion registrada y stock repuesto correctamente.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('historial')


@rol_requerido(*ROLES_ADMIN)
def historial_ventas(request):
    fecha_filtro = request.GET.get('fecha', str(timezone.localdate()))
    busqueda = request.GET.get('buscar', '')

    ventas = Venta.objects.select_related('cajero_responsable', 'cliente').prefetch_related(
        Prefetch('detalleventa_set', queryset=DetalleVenta.objects.select_related('producto')),
        Prefetch('devolucion_set', queryset=Devolucion.objects.select_related('producto', 'usuario_responsable').order_by('-fecha_hora')),
    ).order_by('-id_venta')

    if fecha_filtro:
        try:
            fecha = date.fromisoformat(fecha_filtro)
            inicio, fin = _rango_dia(fecha)
            ventas = ventas.filter(fecha_hora__range=(inicio, fin))
        except ValueError:
            ventas = ventas.none()
    if busqueda:
        if busqueda.isdigit():
            ventas = ventas.filter(Q(id_venta=busqueda) | Q(cliente__identificacion__icontains=busqueda))
        else:
            ventas = ventas.filter(
                Q(cliente__nombre__icontains=busqueda) |
                Q(cliente__identificacion__icontains=busqueda)
            )

    total_recaudado = ventas.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    total_facturas = ventas.count()
    total_articulos = DetalleVenta.objects.filter(venta__in=ventas).aggregate(total=Sum('cantidad'))['total'] or 0
    total_devoluciones = Devolucion.objects.filter(venta__in=ventas).aggregate(total=Sum('cantidad'))['total'] or 0

    ventas = list(ventas)
    detalle_ids = [
        detalle.id_detalle
        for venta in ventas
        for detalle in venta.detalleventa_set.all()
    ]
    devueltos_por_detalle = {
        fila['detalle_id']: fila['total'] or 0
        for fila in Devolucion.objects.filter(detalle_id__in=detalle_ids)
        .values('detalle_id')
        .annotate(total=Sum('cantidad'))
    }
    for venta in ventas:
        for detalle in venta.detalleventa_set.all():
            detalle.cantidad_devuelta = devueltos_por_detalle.get(detalle.id_detalle, 0)
            detalle.cantidad_disponible_devolucion = detalle.cantidad - detalle.cantidad_devuelta

    return render(request, 'gestion/historial.html', {
        'ventas': ventas,
        'total_recaudado': total_recaudado,
        'total_facturas': total_facturas,
        'total_articulos': total_articulos,
        'total_devoluciones': total_devoluciones,
        'fecha_filtro': fecha_filtro,
        'busqueda': busqueda,
    })
