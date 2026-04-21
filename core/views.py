from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import PerfilUsuario


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/home.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if not user:
            from django.contrib.auth.models import User
            try:
                u = User.objects.get(email=username)
                user = authenticate(request, username=u.username, password=password)
            except User.DoesNotExist:
                pass
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Usuario o contraseña incorrectos.')
    return render(request, 'core/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


def registro_cliente(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username       = request.POST.get('email')
        email          = request.POST.get('email')
        password       = request.POST.get('password')
        password2      = request.POST.get('password2')
        nombre         = request.POST.get('nombre')
        telefono       = request.POST.get('telefono', '')
        direccion      = request.POST.get('direccion', '')
        tipo_documento = request.POST.get('tipo_documento', 'INE')
        num_documento  = request.POST.get('numero_documento', '000')

        if password != password2:
            messages.error(request, 'Las contraseñas no coinciden.')
            return redirect('home')

        from django.contrib.auth.models import User
        from .models import Cliente
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Ese email ya está registrado.')
            return redirect('home')

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=nombre,
            )
            PerfilUsuario.objects.create(user=user, rol='cliente')
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute(
                    "EXEC registrar_cliente %s, %s, %s, %s, %s, %s",
                    [nombre, email, telefono, direccion, tipo_documento, num_documento]
                )
            Cliente.objects.filter(email=email).update(user=user)
            messages.success(request, '¡Cuenta creada! Inicia sesión.')
            return redirect('home')
        except Exception as e:
            messages.error(request, f'Error: {e}')
            return redirect('home')

    return render(request, 'core/registro.html')


@login_required
def dashboard(request):
    try:
        rol = request.user.perfil.rol
    except PerfilUsuario.DoesNotExist:
        return redirect('login')
    if rol == 'admin':
        return redirect('admin_dashboard')
    elif rol == 'repartidor':
        return redirect('repartidor_dashboard')
    else:
        return redirect('cliente_dashboard')


@login_required
def admin_dashboard(request):
    from .models import Pedido, Cliente, Repartidor, Pago, Entrega
    from django.db import connection

    ingresos = sum(p.monto for p in Pago.objects.all()) if Pago.objects.exists() else 0
    total_pedidos = Pedido.objects.count()

    # Repartidores con conteo de entregas via SQL directo
    reps_data = []
    with connection.cursor() as cur:
        cur.execute("""
            SELECT r.repartidor_id, r.nombre_completo, r.usuario, r.estado,
                   SUM(CASE WHEN e.estado = 'Entregado' THEN 1 ELSE 0 END) AS total
            FROM Repartidores r
            LEFT JOIN Entregas e ON r.repartidor_id = e.repartidor_id
            GROUP BY r.repartidor_id, r.nombre_completo, r.usuario, r.estado
            ORDER BY total DESC
        """)
        for row in cur.fetchall():
            reps_data.append({
                'nombre_completo': row[1],
                'usuario':         row[2],
                'estado':          row[3],
                'total':           row[4] or 0,
            })

    max_e = max((r['total'] for r in reps_data), default=1) or 1
    for r in reps_data:
        r['pct'] = round(r['total'] / max_e * 100)

    resumen = [
        ('Total pedidos',        total_pedidos,                                         '#e6edf3'),
        ('Pendientes',           Pedido.objects.filter(estado='Pendiente').count(),      '#94a3b8'),
        ('En tránsito',          Pedido.objects.filter(estado='En tránsito').count(),    '#fbbf24'),
        ('Entregados',           Pedido.objects.filter(estado='Entregado').count(),      '#10b981'),
        ('Repartidores activos', Repartidor.objects.filter(estado='Activo').count(),     '#38bdf8'),
        ('Ingresos totales',     f'${ingresos:,.2f}',                                   '#f59e0b'),
    ]

    ctx = {
        'total_pedidos':        total_pedidos,
        'pedidos_pendientes':   Pedido.objects.filter(estado='Pendiente').count(),
        'en_transito':          Pedido.objects.filter(estado='En tránsito').count(),
        'entregados':           Pedido.objects.filter(estado='Entregado').count(),
        'total_clientes':       Cliente.objects.count(),
        'repartidores_activos': Repartidor.objects.filter(estado='Activo').count(),
        'ingresos':             ingresos,
        'pedidos_recientes':    Pedido.objects.select_related('cliente').order_by('-fecha_pedido')[:6],
        'repartidores_lista':   reps_data,
        'resumen':              resumen,
    }
    return render(request, 'core/admin/dashboard.html', ctx)


@login_required
def admin_pedidos(request):
    from .models import Pedido, Pago
    estado = request.GET.get('estado', '')
    search = request.GET.get('q', '')
    qs = Pedido.objects.select_related('cliente').order_by('-fecha_pedido')
    if estado:
        qs = qs.filter(estado=estado)
    if search:
        qs = qs.filter(cliente__nombre_completo__icontains=search)

    # IDs de pedidos que tienen al menos un pago
    pedidos_con_pago = set(
        Pago.objects.values_list('pedido_id', flat=True)
    )

    return render(request, 'core/admin/pedidos.html', {
        'pedidos':          qs,
        'estados':          Pedido.ESTADO,
        'filtro_estado':    estado,
        'search':           search,
        'pedidos_con_pago': pedidos_con_pago,
    })


@login_required
def admin_pedido_detalle(request, pedido_id):
    from .models import Pedido
    pedido   = Pedido.objects.select_related('cliente').get(pk=pedido_id)
    detalles = pedido.detalles.all()
    entrega  = getattr(pedido, 'entrega', None)
    pago     = getattr(pedido, 'pago', None)
    log_in, log_up = [], []
    try:
        from .models import PedidosLogIN, PedidosLogUP
        log_in = PedidosLogIN.objects.filter(pedido_id=pedido_id).order_by('-fecha_registro')
        log_up = PedidosLogUP.objects.filter(pedido_id=pedido_id).order_by('-fecha_registro')
    except Exception:
        pass
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado:
            pedido.estado = nuevo_estado
            pedido.save()
            messages.success(request, f'Estado actualizado a "{nuevo_estado}".')
    return render(request, 'core/admin/pedido_detalle.html', {
        'pedido': pedido, 'detalles': detalles,
        'entrega': entrega, 'pago': pago,
        'log_in': log_in, 'log_up': log_up,
    })


@login_required
def admin_repartidores(request):
    from .models import Repartidor, Vehiculo
    repartidores = Repartidor.objects.all().order_by('nombre_completo')
    vehiculos    = Vehiculo.objects.filter(estado='Disponible')

    if request.method == 'POST':
        nombre     = request.POST.get('nombre')
        telefono   = request.POST.get('telefono')
        usuario    = request.POST.get('usuario')
        contrasena = request.POST.get('contrasena')
        licencia   = request.POST.get('licencia')

        try:
            from django.contrib.auth.models import User
            from django.db import connection

            if User.objects.filter(username=usuario).exists():
                messages.error(request, 'Ese usuario ya existe.')
                return redirect('admin_repartidores')

            user = User.objects.create_user(
                username=usuario,
                password=contrasena,
            )
            PerfilUsuario.objects.create(user=user, rol='repartidor')

            with connection.cursor() as cur:
                cur.execute(
                    "EXEC registrar_repartidor %s, %s, %s, %s, %s",
                    [nombre, telefono, usuario, contrasena, licencia]
                )

            Repartidor.objects.filter(usuario=usuario).update(user=user)
            messages.success(request, f'Repartidor {nombre} registrado correctamente.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('admin_repartidores')

    return render(request, 'core/admin/repartidores.html', {
        'repartidores': repartidores,
        'vehiculos':    vehiculos,
    })


@login_required
def admin_asignar_entrega(request, pedido_id):
    from .models import Pedido, Repartidor, Vehiculo
    from django.db import connection

    pedido       = Pedido.objects.select_related('cliente').get(pk=pedido_id)
    repartidores = Repartidor.objects.filter(estado='Activo')
    vehiculos    = Vehiculo.objects.filter(estado='Disponible')

    if request.method == 'POST':
        repartidor_id = request.POST.get('repartidor_id')
        vehiculo_id   = request.POST.get('vehiculo_id')
        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO Entregas
                        (pedido_id, repartidor_id, vehiculo_id, fecha_salida, estado)
                    VALUES (%s, %s, %s, GETDATE(), 'En tránsito')
                """, [pedido_id, repartidor_id, vehiculo_id])
            messages.success(request, 'Entrega asignada correctamente.')
            return redirect('admin_pedido_detalle', pedido_id=pedido_id)
        except Exception as e:
            messages.error(request, f'Error al asignar: {e}')

    return render(request, 'core/admin/asignar_entrega.html', {
        'pedido':       pedido,
        'repartidores': repartidores,
        'vehiculos':    vehiculos,
    })


@login_required
def admin_actualizar_entrega(request, entrega_id):
    from .models import Entrega
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        try:
            entrega = Entrega.objects.select_related('pedido').get(pk=entrega_id)
            entrega.estado = nuevo_estado
            if nuevo_estado == 'Entregado':
                from django.utils import timezone
                entrega.fecha_entrega = timezone.now()
                entrega.pedido.estado = 'Entregado'
                entrega.pedido.save()
            entrega.save()
            messages.success(request, f'Estado actualizado a "{nuevo_estado}".')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_pedido_detalle', pedido_id=request.POST.get('pedido_id'))


@login_required
def admin_pagos(request):
    from .models import Pago, Pedido
    from django.db import connection

    pagos = Pago.objects.select_related('pedido__cliente').order_by('-fecha_pago')

    if request.method == 'POST':
        pedido_id   = request.POST.get('pedido_id')
        metodo_pago = request.POST.get('metodo_pago')
        referencia  = request.POST.get('referencia')
        monto       = request.POST.get('monto')
        try:
            with connection.cursor() as cur:
                cur.execute(
                    "EXEC registrar_pago %s, %s, %s, %s",
                    [pedido_id, metodo_pago, referencia, monto]
                )
            messages.success(request, 'Pago registrado correctamente.')
            return redirect('admin_pagos')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    pedidos_sin_pago = Pedido.objects.select_related('cliente').filter(
        estado__in=['Pendiente', 'Confirmado', 'En tránsito']
    ).exclude(
        pedido_id__in=Pago.objects.values_list('pedido_id', flat=True)
    ).order_by('-fecha_pedido')

    return render(request, 'core/admin/pagos.html', {
        'pagos':            pagos,
        'pedidos_sin_pago': pedidos_sin_pago,
    })


@login_required
def admin_ranking(request):
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute("""
            SELECT
                r.repartidor_id,
                r.nombre_completo,
                r.usuario,
                r.estado,
                COUNT(e.entrega_id) AS total_entregas,
                SUM(CASE WHEN e.estado = 'Entregado' THEN 1 ELSE 0 END) AS entregados,
                SUM(CASE WHEN e.estado = 'En tránsito' THEN 1 ELSE 0 END) AS en_transito,
                RANK() OVER (
                    ORDER BY SUM(CASE WHEN e.estado = 'Entregado' THEN 1 ELSE 0 END) DESC
                ) AS ranking
            FROM Repartidores r
            LEFT JOIN Entregas e ON r.repartidor_id = e.repartidor_id
            GROUP BY r.repartidor_id, r.nombre_completo, r.usuario, r.estado
            ORDER BY ranking
        """)
        cols = [c[0] for c in cur.description]
        ranking = [dict(zip(cols, row)) for row in cur.fetchall()]

    max_e = max((r['entregados'] or 0 for r in ranking), default=1) or 1
    for r in ranking:
        r['pct'] = round((r['entregados'] or 0) / max_e * 100)

    return render(request, 'core/admin/ranking.html', {'ranking': ranking})


@login_required
def repartidor_dashboard(request):
    from .models import Repartidor, Entrega
    try:
        rep      = Repartidor.objects.get(user=request.user)
        entregas = Entrega.objects.filter(
            repartidor=rep
        ).select_related('pedido__cliente').order_by('-entrega_id')
    except Repartidor.DoesNotExist:
        rep      = None
        entregas = []

    if request.method == 'POST':
        entrega_id   = request.POST.get('entrega_id')
        nuevo_estado = request.POST.get('estado')
        if entrega_id and nuevo_estado:
            try:
                entrega = Entrega.objects.get(entrega_id=entrega_id, repartidor=rep)
                entrega.estado = nuevo_estado
                if nuevo_estado == 'Entregado':
                    from django.utils import timezone
                    entrega.fecha_entrega = timezone.now()
                entrega.save()
                messages.success(request, 'Estado actualizado.')
            except Exception as e:
                messages.error(request, f'Error: {e}')
        return redirect('repartidor_dashboard')

    en_transito = sum(1 for e in entregas if e.estado == 'En tránsito') if entregas else 0
    entregados  = sum(1 for e in entregas if e.estado == 'Entregado')   if entregas else 0

    return render(request, 'core/repartidor/dashboard.html', {
        'rep':         rep,
        'entregas':    entregas,
        'en_transito': en_transito,
        'entregados':  entregados,
    })


@login_required
def cliente_dashboard(request):
    from .models import Cliente, Pedido
    try:
        cliente = Cliente.objects.get(user=request.user)
        pedidos = Pedido.objects.filter(cliente=cliente).order_by('-fecha_pedido')
    except Cliente.DoesNotExist:
        cliente = None
        pedidos = []
    return render(request, 'core/cliente/dashboard.html', {
        'cliente':     cliente,
        'pedidos':     pedidos,
        'pendientes':  pedidos.filter(estado='Pendiente').count() if pedidos else 0,
        'en_transito': pedidos.filter(estado='En tránsito').count() if pedidos else 0,
        'entregados':  pedidos.filter(estado='Entregado').count() if pedidos else 0,
    })


@login_required
def cliente_nuevo_pedido(request):
    from .models import Cliente, Pedido, DetallePedido
    try:
        cliente = Cliente.objects.get(user=request.user)
    except Cliente.DoesNotExist:
        messages.error(request, 'No tienes un perfil de cliente.')
        return redirect('cliente_dashboard')

    if request.method == 'POST':
        direccion  = request.POST.get('direccion_entrega')
        productos  = request.POST.getlist('producto[]')
        cantidades = request.POST.getlist('cantidad[]')
        precios    = request.POST.getlist('precio_unitario[]')

        if not direccion or not any(p.strip() for p in productos):
            messages.error(request, 'Completa la dirección y agrega al menos un producto.')
            return render(request, 'core/cliente/nuevo_pedido.html', {'cliente': cliente})

        try:
            from decimal import Decimal
            total = sum(
                Decimal(p) * int(c)
                for p, c in zip(precios, cantidades) if p and c
            )
            from django.db import connection
            with connection.cursor() as cur:
                cur.execute(
                    "EXEC generar_pedido %s, %s, %s",
                    [cliente.cliente_id, direccion, total]
                )
            pedido = Pedido.objects.filter(
                cliente=cliente
            ).order_by('-pedido_id').first()

            if pedido:
                for prod, cant, precio in zip(productos, cantidades, precios):
                    if prod.strip():
                        DetallePedido.objects.create(
                            pedido=pedido,
                            producto=prod.strip(),
                            cantidad=int(cant),
                            precio_unitario=Decimal(precio),
                        )
            messages.success(request, '¡Pedido creado exitosamente!')
            return redirect('cliente_dashboard')
        except Exception as e:
            messages.error(request, f'Error al crear el pedido: {e}')

    return render(request, 'core/cliente/nuevo_pedido.html', {'cliente': cliente})

@login_required
def admin_reportes(request):
    from django.db import connection
    from .models import PedidosLogIN, PedidosLogUP, PedidosLogDEL, EntregasLogIN, EntregasLogUP, PagosLogIN

    # CASE: Clasificación de clientes
    with connection.cursor() as cur:
        cur.execute("""
            SELECT c.nombre_completo, COUNT(p.pedido_id) AS total_pedidos,
                CASE WHEN COUNT(p.pedido_id) > 5 THEN 'Frecuente' ELSE 'Normal' END AS tipo
            FROM Clientes c
            LEFT JOIN Pedidos p ON c.cliente_id = p.cliente_id
            GROUP BY c.cliente_id, c.nombre_completo
            ORDER BY total_pedidos DESC
        """)
        cols = [c[0] for c in cur.description]
        clasificacion = [dict(zip(cols, row)) for row in cur.fetchall()]

    # PIVOT: Entregas por mes
    with connection.cursor() as cur:
        cur.execute("""
            SELECT * FROM (
                SELECT MONTH(fecha_entrega) mes FROM Entregas
                WHERE fecha_entrega IS NOT NULL
            ) AS tabla
            PIVOT (
                COUNT(mes)
                FOR mes IN ([1],[2],[3],[4],[5],[6],[7],[8],[9],[10],[11],[12])
            ) AS pivote
        """)
        meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
        pivot = []
        if cur.description:
            rows = cur.fetchall()
            if rows:
                row = rows[0]
                for i in range(12):
                    pivot.append({'mes': meses[i], 'total': row[i] or 0})

    return render(request, 'core/admin/reportes.html', {
        'clasificacion':    clasificacion,
        'pivot':            pivot,
        'log_pedidos_in':   PedidosLogIN.objects.order_by('-fecha_registro')[:30],
        'log_pedidos_up':   PedidosLogUP.objects.order_by('-fecha_registro')[:30],
        'log_pedidos_del':  PedidosLogDEL.objects.order_by('-fecha_registro')[:20],
        'log_entregas_in':  EntregasLogIN.objects.order_by('-fecha_registro')[:20],
        'log_entregas_up':  EntregasLogUP.objects.order_by('-fecha_registro')[:20],
        'log_pagos_in':     PagosLogIN.objects.order_by('-fecha_registro')[:20],
    })