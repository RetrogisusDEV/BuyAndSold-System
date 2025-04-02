import sqlite3
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb
from ttkbootstrap.dialogs import Dialog
from typing import Dict, Tuple, Optional, List

# Constantes
DB_NAME = "inventario.db"
IVA_PERCENT = 0.19

class DatabaseManager:
    """Manejador de operaciones de base de datos"""
    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name
        self._initialize_db()
    
    def _initialize_db(self) -> None:
        """Inicializa las tablas de la base de datos"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS productos
                           (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           nombre TEXT NOT NULL UNIQUE,
                           cantidad INTEGER NOT NULL,
                           precio REAL NOT NULL,
                           costo REAL NOT NULL)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS totales
                           (id INTEGER PRIMARY KEY,
                           total_ventas REAL DEFAULT 0,
                           total_gastado REAL DEFAULT 0)''')
            cursor.execute("INSERT OR IGNORE INTO totales (id) VALUES (1)")
            cursor.execute('''CREATE TABLE IF NOT EXISTS ventas_actuales
                           (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           producto TEXT NOT NULL,
                           cantidad INTEGER NOT NULL,
                           precio_unitario REAL NOT NULL,
                           subtotal REAL NOT NULL)''')
    
    def _get_connection(self) -> sqlite3.Connection:
        """Obtiene una conexión a la base de datos"""
        return sqlite3.connect(self.db_name)
    
    def add_or_update_product(self, nombre: str, cantidad: int, precio: float, costo: float) -> None:
        """Agrega o actualiza un producto en el inventario"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cantidad FROM productos WHERE nombre = ?", (nombre,))
            if producto := cursor.fetchone():
                nueva_cantidad = producto[0] + cantidad
                cursor.execute("UPDATE productos SET cantidad = ?, precio = ?, costo = ? WHERE nombre = ?", 
                              (nueva_cantidad, precio, costo, nombre))
            else:
                cursor.execute("INSERT INTO productos (nombre, cantidad, precio, costo) VALUES (?, ?, ?, ?)", 
                             (nombre, cantidad, precio, costo))
            
            total_gastado = cantidad * costo
            cursor.execute("UPDATE totales SET total_gastado = total_gastado + ?", (total_gastado,))
    
    def sell_product(self, nombre: str, cantidad: int) -> float:
        """Realiza una venta de producto y devuelve el precio unitario"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cantidad, precio FROM productos WHERE nombre = ?", (nombre,))
            if not (producto := cursor.fetchone()):
                raise ValueError("Producto no encontrado")
            
            stock, precio = producto
            if stock < cantidad:
                raise ValueError(f"No hay suficiente stock. Disponible: {stock}")
            
            nueva_cantidad = stock - cantidad
            cursor.execute("UPDATE productos SET cantidad = ? WHERE nombre = ?", (nueva_cantidad, nombre))
            
            subtotal = cantidad * precio
            cursor.execute("UPDATE totales SET total_ventas = total_ventas + ?", (subtotal,))
            
            # Agregar a ventas actuales
            cursor.execute("INSERT INTO ventas_actuales (producto, cantidad, precio_unitario, subtotal) VALUES (?, ?, ?, ?)",
                          (nombre, cantidad, precio, subtotal))
            
            return precio
    
    def get_totals(self) -> Tuple[float, float]:
        """Obtiene los totales de ventas y gastos"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT total_ventas, total_gastado FROM totales")
            return cursor.fetchone()
    
    def get_all_products(self) -> List[Tuple[str, int, float, float]]:
        """Obtiene todos los productos del inventario"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nombre, cantidad, precio, costo FROM productos")
            return cursor.fetchall()
    
    def get_current_sales(self) -> List[Tuple[str, int, float]]:
        """Obtiene los productos en venta actuales"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT producto, cantidad, precio_unitario FROM ventas_actuales")
            return cursor.fetchall()
    
    def clear_current_sales(self) -> None:
        """Limpia las ventas actuales"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ventas_actuales")

class SaleDetailsPanel(tb.Frame):
    """Panel para mostrar los detalles de la venta"""
    def __init__(self, master):
        super().__init__(master, padding=10)
        
        tb.Label(self, text="Detalles de Venta", font=('Helvetica', 12, 'bold')).pack(pady=5)
        
        self.entries = {}
        fields = [
            ("Producto:", "producto"),
            ("Precio Unitario:", "precio"),
            ("Cantidad:", "cantidad"),
            ("Subtotal:", "subtotal"),
            (f"IVA ({IVA_PERCENT*100:.0f}%):", "iva"),
            ("Total:", "total")
        ]
        
        for label, key in fields:
            frame = tb.Frame(self)
            frame.pack(fill=tk.X, pady=2)
            
            tb.Label(frame, text=label, width=15, anchor="w").pack(side=tk.LEFT, padx=5)
            entry = tb.Entry(frame, state='readonly')
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entries[key] = entry
        
        tb.Button(
            self, text="Ver Totales", bootstyle="info",
            command=self.master._show_totals, width=15
        ).pack(pady=10)
    
    def update_details(self, producto: str, precio: float, cantidad: int) -> None:
        """Actualiza los detalles de la venta"""
        subtotal = precio * cantidad
        iva = subtotal * IVA_PERCENT
        total = subtotal + iva
        
        for entry in self.entries.values():
            entry.config(state='normal')
            entry.delete(0, tk.END)
        
        self.entries['producto'].insert(0, producto)
        self.entries['precio'].insert(0, f"${precio:.2f}")
        self.entries['cantidad'].insert(0, str(cantidad))
        self.entries['subtotal'].insert(0, f"${subtotal:.2f}")
        self.entries['iva'].insert(0, f"${iva:.2f}")
        self.entries['total'].insert(0, f"${total:.2f}")
        
        for entry in self.entries.values():
            entry.config(state='readonly')
    
    def clear(self) -> None:
        """Limpia todos los campos"""
        for entry in self.entries.values():
            entry.config(state='normal')
            entry.delete(0, tk.END)
            entry.config(state='readonly')

class InventoryApp(tb.Window):
    """Aplicación principal de gestión de inventario"""
    def __init__(self):
        super().__init__(themename="cosmo")
        self.title("Sistema de Gestión de Inventario")
        self.geometry("1200x650")
        
        self.db = DatabaseManager()
        self.current_edit_product = None
        self._setup_ui()
        self._load_products()
        self._load_sales()
    
    def _setup_ui(self) -> None:
        """Configura la interfaz de usuario"""
        # Panel izquierdo
        self.sale_panel = SaleDetailsPanel(self)
        self.sale_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # Panel central
        main_frame = tb.Frame(self)
        main_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # Controles de búsqueda/venta
        search_frame = tb.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=10)
        
        tb.Label(search_frame, text="Producto:").pack(side=tk.LEFT, padx=5)
        self.product_entry = tb.Entry(search_frame)
        self.product_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        tb.Label(search_frame, text="Cantidad:").pack(side=tk.LEFT, padx=5)
        self.quantity_entry = tb.Entry(search_frame, width=10)
        self.quantity_entry.pack(side=tk.LEFT, padx=5)
        
        # Lista de productos
        self.tree = tb.Treeview(
            main_frame,
            columns=("nombre", "cantidad", "precio", "costo"),
            show='headings',
            height=15,
            bootstyle="primary"
        )
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Configurar columnas
        for col, text in zip(
            ["nombre", "cantidad", "precio", "costo"],
            ["Nombre", "Cantidad", "Precio", "Costo"]
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, anchor="center", width=100)
        
        # Barra de herramientas
        toolbar = tb.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=10)
        
        buttons = [
            ("Agregar Producto", "success", self.show_add_product_view),
            ("Actualizar Valores", "primary", self._update_sale_details),
            ("Vender", "danger", self._sell_product),
            ("Editar Producto", "warning", self._edit_product),
            ("Eliminar Producto", "light", self._delete_product)
        ]
        
        for text, style, command in buttons:
            tb.Button(
                toolbar, text=text, bootstyle=style,
                command=command
            ).pack(side=tk.LEFT, padx=5)
        
        # Panel derecho
        self.right_panel = tb.Frame(self, width=350)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)
        
        self._setup_right_panel()
    
    def _setup_right_panel(self):
        # Frame para agregar productos
        self.add_product_frame = tb.Frame(self.right_panel)
        self._build_add_product_form()
        
        # Frame para mostrar productos en venta
        self.sales_frame = tb.Frame(self.right_panel)
        tb.Label(self.sales_frame, text="Productos en Venta", font=('Helvetica', 12, 'bold')).pack(pady=5)
        self.sales_tree = tb.Treeview(
            self.sales_frame,
            columns=("producto", "cantidad", "precio"),
            show='headings',
            height=15,
            bootstyle="primary"
        )
        self.sales_tree.pack(fill=tk.BOTH, expand=True)
        self.sales_tree.heading("producto", text="Producto")
        self.sales_tree.heading("cantidad", text="Cantidad")
        self.sales_tree.heading("precio", text="Precio Unit.")
        
        self.show_sales_view()
    
    def _build_add_product_form(self):
        form_frame = tb.Frame(self.add_product_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
    
        # Título usando pack (es el único elemento que usará pack en este frame)
        tb.Label(form_frame, text="Agregar/Editar Producto", font=('Helvetica', 12, 'bold')).pack(pady=5)
    
        # Frame interno para los campos del formulario (usará grid)
        fields_frame = tb.Frame(form_frame)
        fields_frame.pack(fill=tk.X, pady=10)
    
        self.entries = {}
        fields = [
            ("Nombre del Producto:", "nombre"),
            ("Cantidad:", "cantidad"),
            ("Precio de Venta:", "precio"),
            ("Costo:", "costo")
        ]
    
        for row, (label, key) in enumerate(fields):
            tb.Label(fields_frame, text=label).grid(row=row, column=0, padx=5, pady=5, sticky="w")
            entry = tb.Entry(fields_frame)
            entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
            self.entries[key] = entry
    
        button_frame = tb.Frame(form_frame)
        button_frame.pack(fill=tk.X, pady=10)
    
        tb.Button(
            button_frame, text="Guardar", bootstyle="success",
            command=self._save_product
        ).pack(side=tk.LEFT, padx=5)
    
        tb.Button(
            button_frame, text="Cancelar", bootstyle="secondary",
            command=self.show_sales_view
        ).pack(side=tk.LEFT, padx=5)
    
        fields_frame.columnconfigure(1, weight=1)
    
    def show_add_product_view(self):
        """Muestra el formulario para agregar/editar productos"""
        self.sales_frame.pack_forget()
        self.add_product_frame.pack(fill=tk.BOTH, expand=True)
        self._clear_entries()
        self.current_edit_product = None
    
    def show_sales_view(self):
        """Muestra la lista de productos en venta"""
        self.add_product_frame.pack_forget()
        self.sales_frame.pack(fill=tk.BOTH, expand=True)
        self._load_sales()
    
    def _load_products(self) -> None:
        """Carga los productos en el Treeview principal"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for producto in self.db.get_all_products():
            self.tree.insert("", tk.END, values=producto)
    
    def _load_sales(self):
        """Carga los productos en venta en el Treeview derecho"""
        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)
        
        for producto in self.db.get_current_sales():
            self.sales_tree.insert("", tk.END, values=producto)
    
    def _save_product(self) -> None:
        """Guarda un producto nuevo o editado"""
        try:
            data = {
                'nombre': self.entries['nombre'].get().strip(),
                'cantidad': int(self.entries['cantidad'].get()),
                'precio': float(self.entries['precio'].get()),
                'costo': float(self.entries['costo'].get())
            }
            
            if not all(data.values()):
                raise ValueError("Todos los campos son obligatorios")
            
            if data['cantidad'] <= 0 or data['precio'] <= 0 or data['costo'] <= 0:
                raise ValueError("Los valores deben ser positivos")
            
            if self.current_edit_product:
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM productos WHERE nombre = ?", (self.current_edit_product,))
                    conn.commit()
                self.current_edit_product = None
            
            self.db.add_or_update_product(**data)
            self._load_products()
            messagebox.showinfo("Éxito", "Producto guardado correctamente")
            self.show_sales_view()
            self._clear_entries()
        
        except ValueError as e:
            messagebox.showerror("Error", f"Dato inválido: {e}")
    
    def _clear_entries(self):
        """Limpia los campos del formulario"""
        for entry in self.entries.values():
            entry.delete(0, tk.END)
    
    def _edit_product(self) -> None:
        """Prepara el formulario para editar un producto"""
        if not (selected := self.tree.selection()):
            messagebox.showwarning("Advertencia", "Seleccione un producto")
            return
        
        item = self.tree.item(selected[0])
        product_data = {
            'nombre': item['values'][0],
            'cantidad': item['values'][1],
            'precio': item['values'][2],
            'costo': item['values'][3]
        }
        
        self.current_edit_product = product_data['nombre']
        self._clear_entries()
        self.entries['nombre'].insert(0, product_data['nombre'])
        self.entries['cantidad'].insert(0, str(product_data['cantidad']))
        self.entries['precio'].insert(0, str(product_data['precio']))
        self.entries['costo'].insert(0, str(product_data['costo']))
        self.show_add_product_view()
    
    def _delete_product(self) -> None:
        """Elimina el producto seleccionado"""
        if not (selected := self.tree.selection()):
            messagebox.showwarning("Advertencia", "Seleccione un producto")
            return
        
        product_name = self.tree.item(selected[0])['values'][0]
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar el producto {product_name}?"):
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM productos WHERE nombre = ?", (product_name,))
                conn.commit()
            
            self._load_products()
            messagebox.showinfo("Éxito", "Producto eliminado")
    
    def _update_sale_details(self) -> None:
        """Actualiza el panel de detalles de venta"""
        product = self.product_entry.get().strip()
        quantity = self.quantity_entry.get().strip()
        
        try:
            if not product or not quantity:
                raise ValueError("Complete todos los campos")
            
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError("La cantidad debe ser positiva")
            
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT cantidad, precio FROM productos WHERE nombre = ?", (product,))
                if not (result := cursor.fetchone()):
                    raise ValueError("Producto no encontrado")
                
                stock, price = result
                if stock < quantity:
                    raise ValueError(f"Stock insuficiente. Disponible: {stock}")
                
                self.sale_panel.update_details(product, price, quantity)
        
        except ValueError as e:
            messagebox.showerror("Error", str(e))
    
    def _sell_product(self) -> None:
        """Realiza la venta del producto"""
        try:
            product = self.sale_panel.entries['producto'].get()
            quantity = int(self.sale_panel.entries['cantidad'].get())
            
            if not product or quantity <= 0:
                raise ValueError("No hay datos de venta válidos")
            
            price = self.db.sell_product(product, quantity)
            self._load_products()
            
            messagebox.showinfo(
                "Venta realizada",
                f"{product} x {quantity}\n"
                f"Precio unitario: ${price:.2f}\n"
                f"Total: ${price * quantity:.2f}"
            )
            
            # Limpiar campos
            self.product_entry.delete(0, tk.END)
            self.quantity_entry.delete(0, tk.END)
            self.sale_panel.clear()
            self._load_sales()
        
        except ValueError as e:
            messagebox.showerror("Error en venta", str(e))
    
    def _show_totals(self) -> None:
        """Muestra los totales del sistema"""
        ventas, gastos = self.db.get_totals()
        ganancias = ventas - gastos
        
        messagebox.showinfo(
            "Totales del Sistema",
            f"Ventas Totales: ${ventas:.2f}\n"
            f"Gastos Totales: ${gastos:.2f}\n"
            f"Ganancias: ${ganancias:.2f}\n\n"
            f"Margen de ganancia: {(ganancias/ventas*100 if ventas else 0):.1f}%"
        )

if __name__ == "__main__":
    app = InventoryApp()
    app.mainloop()