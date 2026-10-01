from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import PlatoMenu, Proveedor, Pedido, ItemPedido
from usuarios.models import Usuario, EmpresaConvenio
from usuarios.decorators import rol_requerido

# ==================== VISTAS DEL CLIENTE ====================
@login_required
def menu_semanal_cliente(request):
    dias_semana = ['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES']
    menus_por_dia = {dia: PlatoMenu.objects.filter(dia_semana=dia, activo=True) for dia in dias_semana}
    direcciones = request.user.direcciones.all()

    if request.method == 'POST':
        dir_id = request.POST.get('direccion')
        horario = request.POST.get('horario_entrega')

        if not dir_id or not horario:
            messages.error(request, "Debes seleccionar una dirección y un horario de entrega.")
            return redirect('menu_semanal')

        direccion_obj = get_object_or_404(direcciones, id=dir_id)

        with transaction.atomic():
            pedido = Pedido.objects.create(
                cliente=request.user,
                direccion=direccion_obj,
                horario_entrega=horario,
                estado='SOLICITADO'
            )

            seleccion_realizada = False
            for dia in dias_semana:
                plato_id = request.POST.get(f'plato_{dia}')
                if plato_id:
                    plato = PlatoMenu.objects.get(id=plato_id)
                    ItemPedido.objects.create(
                        pedido=pedido,
                        plato=plato,
                        cantidad=1,
                        precio_unitario=plato.precio
                    )
                    seleccion_realizada = True

            if not seleccion_realizada:
                transaction.set_rollback(True)
                messages.error(request, "Debes seleccionar al menos un plato de la semana.")
                return redirect('menu_semanal')

            pedido.recalcular_total()
            messages.success(request, f"¡Pedido #{pedido.id} realizado con éxito!")
            return redirect('mis_pedidos')

    return render(request, 'pedidos/menu_semanal.html', {
        'menus_por_dia': menus_por_dia,
        'direcciones': direcciones,
        'horarios': Pedido.HORARIOS_ENTREGA,
    })

@login_required
def mis_pedidos(request):
    pedidos = request.user.pedidos.all().order_by('-fecha_pedido')
    return render(request, 'pedidos/mis_pedidos.html', {'pedidos': pedidos})


# ==================== VISTA ATENCIÓN AL CLIENTE ====================
@rol_requerido(['ATENCION', 'GERENTE'])
def atencion_dashboard(request):
    pedidos = Pedido.objects.all().select_related('cliente', 'direccion').order_by('-fecha_pedido')
    platos = PlatoMenu.objects.filter(activo=True)

    if request.method == 'POST':
        pedido_id = request.POST.get('pedido_id')
        nuevo_estado = request.POST.get('estado')
        pedido = get_object_or_404(Pedido, id=pedido_id)
        if nuevo_estado in dict(Pedido.ESTADOS):
            pedido.estado = nuevo_estado
            pedido.save()
            messages.success(request, f"Pedido #{pedido.id} modificado a {nuevo_estado}.")
            return redirect('atencion_dashboard')

    return render(request, 'pedidos/atencion_dashboard.html', {
        'pedidos': pedidos,
        'platos': platos,
        'estados': Pedido.ESTADOS
    })


# ==================== VISTA REPARTIDOR ====================
@rol_requerido(['REPARTIDOR', 'GERENTE'])
def repartidor_dashboard(request):
    # Visualiza direcciones de pedidos listos para despacho
    pedidos_ruta = Pedido.objects.filter(estado__in=['SOLICITADO', 'EN_PREPARACION', 'EN_RUTA']).select_related('direccion', 'cliente')
    
    if request.method == 'POST':
        pedido_id = request.POST.get('pedido_id')
        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.estado = 'ENTREGADO'
        pedido.repartidor = request.user
        pedido.save()
        messages.success(request, f"Pedido #{pedido.id} marcado como ENTREGADO.")
        return redirect('repartidor_dashboard')

    return render(request, 'pedidos/repartidor_dashboard.html', {'pedidos': pedidos_ruta})


# ==================== VISTA GERENTE ====================
@rol_requerido(['GERENTE'])
def gerente_dashboard(request):
    menus = PlatoMenu.objects.all().order_by('dia_semana')
    proveedores = Proveedor.objects.all()
    empleados = Usuario.objects.filter(rol__in=['GERENTE', 'ATENCION', 'REPARTIDOR'])
    convenios = EmpresaConvenio.objects.all()

    if request.method == 'POST':
        accion = request.POST.get('accion')

        # 1. Agregar Plato Menú
        if accion == 'crear_menu':
            PlatoMenu.objects.create(
                nombre=request.POST.get('nombre'),
                descripcion=request.POST.get('descripcion'),
                dia_semana=request.POST.get('dia_semana'),
                precio=request.POST.get('precio')
            )
            messages.success(request, "Plato incorporado al menú semanal.")

        # 2. Agregar Proveedor
        elif accion == 'crear_proveedor':
            Proveedor.objects.create(
                nombre=request.POST.get('nombre'),
                contacto=request.POST.get('contacto'),
                telefono=request.POST.get('telefono')
            )
            messages.success(request, "Proveedor ingresado.")

        # 3. Registrar Empleado
        elif accion == 'crear_empleado':
            nuevo_emp = Usuario.objects.create_user(
                email=request.POST.get('email'),
                nombre=request.POST.get('nombre'),
                apellido=request.POST.get('apellido'),
                rut=request.POST.get('rut'),
                telefono=request.POST.get('telefono'),
                direccion=request.POST.get('direccion'),
                cargo=request.POST.get('cargo'),
                rol=request.POST.get('rol'),
                password=request.POST.get('password')
            )
            messages.success(request, f"Empleado {nuevo_emp.nombre} registrado con éxito.")

        # 4. Registrar Empresa Convenio
        elif accion == 'crear_convenio':
            EmpresaConvenio.objects.create(
                nombre=request.POST.get('nombre'),
                rut=request.POST.get('rut'),
                direccion=request.POST.get('direccion'),
                telefono=request.POST.get('telefono')
            )
            messages.success(request, "Empresa en convenio agregada.")

        return redirect('gerente_dashboard')

    return render(request, 'pedidos/gerente_dashboard.html', {
        'menus': menus,
        'proveedores': proveedores,
        'empleados': empleados,
        'convenios': convenios,
        'dias': PlatoMenu.DIAS
    })

@rol_requerido(['GERENTE'])
def eliminar_elemento(request, tipo, item_id):
    if tipo == 'menu':
        get_object_or_404(PlatoMenu, id=item_id).delete()
    elif tipo == 'proveedor':
        get_object_or_404(Proveedor, id=item_id).delete()
    elif tipo == 'empleado':
        get_object_or_404(Usuario, id=item_id).delete()
    elif tipo == 'convenio':
        get_object_or_404(EmpresaConvenio, id=item_id).delete()
    messages.success(request, f"Elemento eliminado exitosamente.")
    return redirect('gerente_dashboard')