from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),      # <-- Ruta de inicio de sesión
    path('logout/', views.logout_view, name='logout'),   # <-- Ruta para cerrar sesión
    path('', views.dashboard, name='dashboard'),
    path('pos/', views.punto_de_venta, name='pos'),
    path('guardar_venta/', views.guardar_venta, name='guardar_venta'),
    path('productos/', views.gestionar_productos, name='productos'),
    path('usuarios/', views.gestionar_usuarios, name='usuarios'),
    path('historial/', views.historial_ventas, name='historial'),
    path('devoluciones/registrar/', views.registrar_devolucion, name='registrar_devolucion'),
]
