from django.urls import path
from . import views

urlpatterns = [
    # Pública
    path('',            views.home,                 name='home'),
    path('login/',      views.login_view,           name='login'),
    path('logout/',     views.logout_view,          name='logout'),
    path('registro/',   views.registro_cliente,     name='registro'),
    path('dashboard/',  views.dashboard,            name='dashboard'),

    # Admin
    path('admin-panel/',                               views.admin_dashboard,      name='admin_dashboard'),
    path('admin-panel/pedidos/',                       views.admin_pedidos,        name='admin_pedidos'),
    path('admin-panel/pedidos/<int:pedido_id>/',       views.admin_pedido_detalle, name='admin_pedido_detalle'),

    # Repartidor
    path('repartidor/', views.repartidor_dashboard, name='repartidor_dashboard'),

    # Cliente
    path('cliente/',                    views.cliente_dashboard,    name='cliente_dashboard'),
    path('cliente/nuevo-pedido/',       views.cliente_nuevo_pedido, name='cliente_nuevo_pedido'),

    path('admin-panel/repartidores/',                        views.admin_repartidores,     name='admin_repartidores'),
    path('admin-panel/pedidos/<int:pedido_id>/asignar/',     views.admin_asignar_entrega,  name='admin_asignar_entrega'),
    path('admin-panel/entregas/<int:entrega_id>/actualizar/',views.admin_actualizar_entrega,name='admin_actualizar_entrega'),
    path('admin-panel/ranking/',                             views.admin_ranking,           name='admin_ranking'),
    path('admin-panel/pagos/', views.admin_pagos, name='admin_pagos'),
    path('admin-panel/reportes/', views.admin_reportes, name='admin_reportes'),
]
