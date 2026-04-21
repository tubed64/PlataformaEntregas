from django.db import models
from django.contrib.auth.models import User


class PerfilUsuario(models.Model):
    ROL = [
        ('admin',      'Administrador'),
        ('repartidor', 'Repartidor'),
        ('cliente',    'Cliente'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol  = models.CharField(max_length=20, choices=ROL, default='cliente')

    class Meta:
        verbose_name = 'Perfil de usuario'

    def __str__(self):
        return f'{self.user.username} ({self.get_rol_display()})'


class Cliente(models.Model):
    TIPO_DOC = [('INE','INE'),('Pasaporte','Pasaporte'),
                ('CURP','CURP'),('RFC','RFC')]

    cliente_id       = models.AutoField(primary_key=True)
    user             = models.OneToOneField(User, on_delete=models.SET_NULL,
                                            null=True, blank=True)
    nombre_completo  = models.CharField(max_length=100)
    email            = models.CharField(max_length=100, unique=True)
    telefono         = models.CharField(max_length=20, blank=True)
    direccion        = models.CharField(max_length=150, blank=True)
    tipo_documento   = models.CharField(max_length=20, choices=TIPO_DOC, default='INE')
    numero_documento = models.BinaryField(null=True, blank=True)
    fecha_registro   = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'Clientes'
        managed  = False

    def __str__(self):
        return self.nombre_completo


class Vehiculo(models.Model):
    ESTADO = [('Disponible','Disponible'),
              ('En tránsito','En tránsito'),
              ('Mantenimiento','Mantenimiento')]

    vehiculo_id = models.AutoField(primary_key=True)
    tipo        = models.CharField(max_length=50)
    placa       = models.CharField(max_length=20, unique=True)
    capacidad   = models.DecimalField(max_digits=10, decimal_places=2)
    estado      = models.CharField(max_length=20, choices=ESTADO, default='Disponible')

    class Meta:
        db_table = 'Vehiculos'
        managed  = False

    def __str__(self):
        return f'{self.tipo} – {self.placa}'


class Repartidor(models.Model):
    ESTADO = [('Activo','Activo'),('Inactivo','Inactivo')]

    repartidor_id     = models.AutoField(primary_key=True)
    user              = models.OneToOneField(User, on_delete=models.SET_NULL,
                                             null=True, blank=True)
    nombre_completo   = models.CharField(max_length=100)
    licencia_conducir = models.BinaryField(null=True, blank=True)
    telefono          = models.CharField(max_length=20, blank=True)
    usuario           = models.CharField(max_length=50, unique=True)
    contrasena        = models.BinaryField(null=True, blank=True)
    estado            = models.CharField(max_length=20, choices=ESTADO, default='Activo')

    class Meta:
        db_table = 'Repartidores'
        managed  = False

    def __str__(self):
        return self.nombre_completo


class Pedido(models.Model):
    ESTADO = [
        ('Pendiente',   'Pendiente'),
        ('En tránsito', 'En tránsito'),
        ('Entregado',   'Entregado'),
        ('Cancelado',   'Cancelado'),
    ]

    pedido_id         = models.AutoField(primary_key=True)
    cliente           = models.ForeignKey(Cliente, on_delete=models.PROTECT,
                                          db_column='cliente_id',
                                          related_name='pedidos')
    fecha_pedido      = models.DateTimeField(auto_now_add=True)
    direccion_entrega = models.CharField(max_length=150)
    estado            = models.CharField(max_length=20, choices=ESTADO,
                                         default='Pendiente')
    total             = models.DecimalField(max_digits=10, decimal_places=2,
                                            default=0)

    class Meta:
        db_table = 'Pedidos'
        managed  = False
        ordering = ['-fecha_pedido']

    def __str__(self):
        return f'Pedido #{self.pedido_id}'


class DetallePedido(models.Model):
    detalle_id      = models.AutoField(primary_key=True)
    pedido          = models.ForeignKey(Pedido, on_delete=models.CASCADE,
                                        db_column='pedido_id',
                                        related_name='detalles')
    producto        = models.CharField(max_length=100)
    cantidad        = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal        = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=0)

    class Meta:
        db_table = 'Detalle_Pedidos'
        managed  = False

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.producto} x{self.cantidad}'


class Entrega(models.Model):
    ESTADO = [
        ('En tránsito', 'En tránsito'),
        ('Entregado',   'Entregado'),
        ('Fallido',     'Fallido'),
    ]

    entrega_id        = models.AutoField(primary_key=True)
    pedido            = models.OneToOneField(Pedido, on_delete=models.PROTECT,
                                             db_column='pedido_id',
                                             related_name='entrega')
    repartidor        = models.ForeignKey(Repartidor, on_delete=models.PROTECT,
                                          db_column='repartidor_id',
                                          related_name='entregas')
    vehiculo          = models.ForeignKey(Vehiculo, on_delete=models.PROTECT,
                                          db_column='vehiculo_id',
                                          related_name='entregas')
    fecha_salida      = models.DateTimeField(null=True, blank=True)
    fecha_entrega     = models.DateTimeField(null=True, blank=True)
    estado            = models.CharField(max_length=20, choices=ESTADO,
                                         default='En tránsito')
    evidencia_entrega = models.BinaryField(null=True, blank=True)

    class Meta:
        db_table = 'Entregas'
        managed  = False

    def __str__(self):
        return f'Entrega #{self.entrega_id}'


class Pago(models.Model):
    METODO = [
        ('Efectivo',      'Efectivo'),
        ('Tarjeta',       'Tarjeta'),
        ('Transferencia', 'Transferencia'),
        ('OXXO',          'OXXO'),
    ]

    pago_id         = models.AutoField(primary_key=True)
    pedido          = models.OneToOneField(Pedido, on_delete=models.PROTECT,
                                           db_column='pedido_id',
                                           related_name='pago')
    fecha_pago      = models.DateField(auto_now_add=True)
    metodo_pago     = models.CharField(max_length=30, choices=METODO)
    referencia_pago = models.BinaryField(null=True, blank=True)
    monto           = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'Pagos'
        managed  = False

    def __str__(self):
        return f'Pago #{self.pago_id} – ${self.monto}'


class ErrorLog(models.Model):
    id      = models.AutoField(primary_key=True)
    mensaje = models.CharField(max_length=255)
    fecha   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'Errores'
        managed  = False

    def __str__(self):
        return f'[{self.fecha}] {self.mensaje}'

class PedidosLogIN(models.Model):
    ID_log            = models.AutoField(primary_key=True)
    pedido_id         = models.IntegerField(null=True)
    cliente_id        = models.IntegerField(null=True)
    fecha_pedido      = models.DateTimeField(null=True)
    direccion_entrega = models.CharField(max_length=150, null=True)
    estado            = models.CharField(max_length=20, null=True)
    total             = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    fecha_registro    = models.DateTimeField(null=True)
    class Meta:
        db_table = 'Pedidos_log_IN'
        managed  = False


class PedidosLogUP(models.Model):
    ID_log            = models.AutoField(primary_key=True)
    pedido_id         = models.IntegerField(null=True)
    cliente_id        = models.IntegerField(null=True)
    fecha_pedido      = models.DateTimeField(null=True)
    direccion_entrega = models.CharField(max_length=150, null=True)
    estado            = models.CharField(max_length=20, null=True)
    total             = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    fecha_registro    = models.DateTimeField(null=True)
    class Meta:
        db_table = 'Pedidos_log_UP'
        managed  = False


class PedidosLogDEL(models.Model):
    ID_log            = models.AutoField(primary_key=True)
    pedido_id         = models.IntegerField(null=True)
    cliente_id        = models.IntegerField(null=True)
    fecha_pedido      = models.DateTimeField(null=True)
    direccion_entrega = models.CharField(max_length=150, null=True)
    estado            = models.CharField(max_length=20, null=True)
    total             = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    fecha_registro    = models.DateTimeField(null=True)
    class Meta:
        db_table = 'Pedidos_log_DEL'
        managed  = False


class EntregasLogIN(models.Model):
    ID_log         = models.AutoField(primary_key=True)
    entrega_id     = models.IntegerField(null=True)
    pedido_id      = models.IntegerField(null=True)
    repartidor_id  = models.IntegerField(null=True)
    vehiculo_id    = models.IntegerField(null=True)
    fecha_salida   = models.DateTimeField(null=True)
    fecha_entrega  = models.DateTimeField(null=True)
    estado         = models.CharField(max_length=20, null=True)
    fecha_registro = models.DateTimeField(null=True)
    class Meta:
        db_table = 'Entregas_log_IN'
        managed  = False


class EntregasLogUP(models.Model):
    ID_log         = models.AutoField(primary_key=True)
    entrega_id     = models.IntegerField(null=True)
    pedido_id      = models.IntegerField(null=True)
    repartidor_id  = models.IntegerField(null=True)
    vehiculo_id    = models.IntegerField(null=True)
    fecha_salida   = models.DateTimeField(null=True)
    fecha_entrega  = models.DateTimeField(null=True)
    estado         = models.CharField(max_length=20, null=True)
    fecha_registro = models.DateTimeField(null=True)
    class Meta:
        db_table = 'Entregas_log_UP'
        managed  = False


class PagosLogIN(models.Model):
    ID_log         = models.AutoField(primary_key=True)
    pago_id        = models.IntegerField(null=True)
    pedido_id      = models.IntegerField(null=True)
    fecha_pago     = models.DateField(null=True)
    metodo_pago    = models.CharField(max_length=30, null=True)
    monto          = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    fecha_registro = models.DateTimeField(null=True)
    class Meta:
        db_table = 'Pagos_log_IN'
        managed  = False