import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
import ttkbootstrap as tb
from ttkbootstrap.dialogs import Dialog

# Funciones de base de datos
def crear_tablas():
    conexion = sqlite3.connect("inventario.db")
    cursor = conexion.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    cantidad INTEGER NOT NULL,
                    precio REAL NOT NULL,
                    costo REAL NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS totales
                    (id INTEGER PRIMARY KEY,
                    total_ventas REAL DEFAULT 0,
                    total_gastado REAL DEFAULT 0)''')
    cursor.execute("INSERT OR IGNORE INTO totales (id) VALUES (1)")
    conexion.commit()
    conexion.close()

def agregar_producto(nombre, cantidad, precio, costo):
    conexion = sqlite3.connect("inventario.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM productos WHERE nombre = ?", (nombre,))
    producto = cursor.fetchone()
    
    if producto:
        nueva_cantidad = producto[2] + cantidad
        cursor.execute("UPDATE productos SET cantidad = ? WHERE nombre = ?", (nueva_cantidad, nombre))
    else:
        cursor.execute("INSERT INTO productos (nombre, cantidad, precio, costo) VALUES (?, ?, ?, ?)", 
                       (nombre, cantidad, precio, costo))
    
    total_gastado = cantidad * costo
    cursor.execute("UPDATE totales SET total_gastado = total_gastado + ?", (total_gastado,))
    conexion.commit()
    conexion.close()

def vender_producto(nombre, cantidad_vendida):
    conexion = sqlite3.connect("inventario.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM productos WHERE nombre = ?", (nombre,))
    producto = cursor.fetchone()
    
    if producto:
        if producto[2] >= cantidad_vendida:
            nueva_cantidad = producto[2] - cantidad_vendida
            cursor.execute("UPDATE productos SET cantidad = ? WHERE nombre = ?", (nueva_cantidad, nombre))
            total_ventas = cantidad_vendida * producto[3]
            cursor.execute("UPDATE totales SET total_ventas = total_ventas + ?", (total_ventas,))
            conexion.commit()
            return producto[3]  # Retorna el precio unitario
        else:
            raise ValueError("No hay suficiente cantidad disponible")
    else:
        raise ValueError("Producto no encontrado")
    conexion.close()

def mostrar_totales():
    conexion = sqlite3.connect("inventario.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM totales")
    totales = cursor.fetchone()
    conexion.close()
    return totales

def mostrar_productos(tree):
    for row in tree.get_children():
        tree.delete(row)
    conexion = sqlite3.connect("inventario.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT nombre, cantidad, precio, costo FROM productos")
    productos = cursor.fetchall()
    for producto in productos:
        tree.insert("", tk.END, values=(producto[0], producto[1], producto[2], producto[3]))
    conexion.close()

# Diálogo para agregar productos
class AgregarProductoDialog(Dialog):
    def __init__(self, parent, title, callback):
        self.callback = callback
        super().__init__(parent, title)
    
    def create_body(self, master):
        frame = tb.Frame(master, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Campos del formulario
        self.entries = {}
        campos = [
            ("Nombre del Producto:", "nombre"),
            ("Cantidad:", "cantidad"),
            ("Precio de Venta:", "precio"),
            ("Costo:", "costo")
        ]
        
        for i, (texto, key) in enumerate(campos):
            lbl = tb.Label(frame, text=texto)
            lbl.grid(row=i, column=0, padx=5, pady=5, sticky="w")
            entry = tb.Entry(frame)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky="ew")
            self.entries[key] = entry
        
        frame.columnconfigure(1, weight=1)
        return frame
    
    def create_buttons(self, master):
        frame = tb.Frame(master, padding=10)
        frame.pack(fill=tk.X)
        
        btn_guardar = tb.Button(
            frame, 
            text="Guardar", 
            bootstyle="success",
            command=self.on_guardar
        )
        btn_guardar.pack(side=tk.RIGHT, padx=5)
        
        btn_cancelar = tb.Button(
            frame,
            text="Cancelar",
            bootstyle="secondary",
            command=self.on_cancelar
        )
        btn_cancelar.pack(side=tk.RIGHT, padx=5)
        
        return frame
    
    def on_guardar(self):
        try:
            datos = {
                'nombre': self.entries['nombre'].get(),
                'cantidad': int(self.entries['cantidad'].get()),
                'precio': float(self.entries['precio'].get()),
                'costo': float(self.entries['costo'].get())
            }
            
            if not all(datos.values()):
                raise ValueError("Todos los campos son obligatorios")
            
            self.callback(datos)
            self._result = True
            self.close()
            
        except ValueError as e:
            messagebox.showerror("Error", f"Datos inválidos: {str(e)}")
    
    def on_cancelar(self):
        self._result = False
        self.close()

# Interfaz principal
class Aplicacion(tb.Window):
    def __init__(self):
        super().__init__(themename="cosmo")
        self.title("Sistema de Compra y Venta")
        self.geometry("900x600")
        
        # Panel izquierdo para detalles de venta
        self.crear_panel_izquierdo()
        
        # Marco principal
        self.crear_marco_principal()
        
        # Inicializar la base de datos
        crear_tablas()
        mostrar_productos(self.tree)
    
    def crear_panel_izquierdo(self):
        left_frame = tb.Frame(self)
        left_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)
        
        lbl_titulo = tb.Label(left_frame, text="Detalles de Venta", font=('Helvetica', 12, 'bold'))
        lbl_titulo.pack(pady=5)
        
        # Campos de detalles
        self.detalle_entries = {}
        detalles = [
            ("Nombre del Producto:", "nombre"),
            ("Valor unitario:", "valor"),
            ("Cantidad vendida:", "cantidad"),
            ("Total Venta:", "total"),
            ("IVA (19%):", "iva"),
            ("Total + IVA:", "total_iva")
        ]
        
        for texto, key in detalles:
            frame = tb.Frame(left_frame)
            frame.pack(fill=tk.X, pady=2)
            
            lbl = tb.Label(frame, text=texto, width=15, anchor="w")
            lbl.pack(side=tk.LEFT, padx=5)
            
            entry = tb.Entry(frame, state='readonly')
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.detalle_entries[key] = entry
        
        # Botón para mostrar totales
        btn_totales = tb.Button(
            left_frame,
            text="Ver Totales",
            command=self.mostrar_totales,
            bootstyle="info",
            width=15
        )
        btn_totales.pack(pady=10)
    
    def crear_marco_principal(self):
        main_frame = tb.Frame(self)
        main_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # Frame para búsqueda/venta
        frame_venta = tb.Frame(main_frame)
        frame_venta.pack(fill=tk.X, pady=10)
        
        lbl_nombre = tb.Label(frame_venta, text="Producto:")
        lbl_nombre.pack(side=tk.LEFT, padx=5)
        
        self.entrada_nombre = tb.Entry(frame_venta)
        self.entrada_nombre.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        lbl_cantidad = tb.Label(frame_venta, text="Cantidad:")
        lbl_cantidad.pack(side=tk.LEFT, padx=5)
        
        self.entrada_cantidad = tb.Entry(frame_venta, width=10)
        self.entrada_cantidad.pack(side=tk.LEFT, padx=5)
        
        # Treeview para productos
        self.tree = ttk.Treeview(
            main_frame,
            columns=("Nombre", "Cantidad", "Precio", "Costo"),
            show='headings',
            height=15
        )
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Configurar columnas
        for col in ("Nombre", "Cantidad", "Precio", "Costo"):
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=100)
        
        # Frame para botones
        frame_botones = tb.Frame(main_frame)
        frame_botones.pack(fill=tk.X, pady=10)
        
        # Botones principales
        btn_agregar = tb.Button(
            frame_botones,
            text="Agregar Producto",
            command=self.abrir_dialogo_agregar,
            bootstyle="success"
        )
        btn_agregar.pack(side=tk.LEFT, padx=5)
        
        btn_actualizar = tb.Button(
            frame_botones,
            text="Actualizar Valores",
            command=self.actualizar_panel,
            bootstyle="primary"
        )
        btn_actualizar.pack(side=tk.LEFT, padx=5)
        
        btn_vender = tb.Button(
            frame_botones,
            text="Vender",
            command=self.realizar_venta,
            bootstyle="danger"
        )
        btn_vender.pack(side=tk.LEFT, padx=5)
    
    def abrir_dialogo_agregar(self):
        def callback(datos):
            agregar_producto(
                datos['nombre'],
                datos['cantidad'],
                datos['precio'],
                datos['costo']
            )
            mostrar_productos(self.tree)
            messagebox.showinfo("Éxito", "Producto agregado correctamente")
        
        AgregarProductoDialog(self, "Agregar Producto", callback)
    
    def actualizar_panel(self):
        nombre = self.entrada_nombre.get()
        cantidad = self.entrada_cantidad.get()
        
        try:
            if not nombre or not cantidad:
                raise ValueError("Complete nombre y cantidad")
            
            cantidad = int(cantidad)
            if cantidad <= 0:
                raise ValueError("La cantidad debe ser positiva")
            
            conexion = sqlite3.connect("inventario.db")
            cursor = conexion.cursor()
            cursor.execute("SELECT precio, cantidad FROM productos WHERE nombre = ?", (nombre,))
            producto = cursor.fetchone()
            conexion.close()
            
            if not producto:
                raise ValueError("Producto no encontrado")
            
            precio_unitario, stock = producto
            if stock < cantidad:
                raise ValueError(f"Stock insuficiente. Disponible: {stock}")
            
            total = precio_unitario * cantidad
            iva = total * 0.19
            total_con_iva = total + iva
            
            # Actualizar campos
            for entry in self.detalle_entries.values():
                entry.config(state='normal')
                entry.delete(0, tk.END)
            
            self.detalle_entries['nombre'].insert(0, nombre)
            self.detalle_entries['valor'].insert(0, f"${precio_unitario:.2f}")
            self.detalle_entries['cantidad'].insert(0, str(cantidad))
            self.detalle_entries['total'].insert(0, f"${total:.2f}")
            self.detalle_entries['iva'].insert(0, f"${iva:.2f}")
            self.detalle_entries['total_iva'].insert(0, f"${total_con_iva:.2f}")
            
            for entry in self.detalle_entries.values():
                entry.config(state='readonly')
            
        except ValueError as e:
            messagebox.showerror("Error", str(e))
    
    def realizar_venta(self):
        try:
            nombre = self.detalle_entries['nombre'].get()
            cantidad = int(self.detalle_entries['cantidad'].get())
            
            if not nombre or cantidad <= 0:
                raise ValueError("Datos de venta inválidos")
            
            precio_unitario = vender_producto(nombre, cantidad)
            mostrar_productos(self.tree)
            
            messagebox.showinfo("Éxito", f"Venta realizada:\n{nombre} x {cantidad}\nTotal: ${precio_unitario * cantidad:.2f}")
            
            # Limpiar campos
            self.entrada_nombre.delete(0, tk.END)
            self.entrada_cantidad.delete(0, tk.END)
            for entry in self.detalle_entries.values():
                entry.config(state='normal')
                entry.delete(0, tk.END)
                entry.config(state='readonly')
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def mostrar_totales(self):
        totales = mostrar_totales()
        messagebox.showinfo(
            "Totales del Sistema",
            f"Total en Ventas: ${totales[1]:.2f}\n"
            f"Total Gastado: ${totales[2]:.2f}\n"
            f"Ganancias: ${totales[1] - totales[2]:.2f}"
        )

# Ejecutar la aplicación
if __name__ == "__main__":
    app = Aplicacion()
    app.mainloop()