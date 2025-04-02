import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as tb
from typing import Optional
from database import DatabaseManager
from sale_details_panel import SaleDetailsPanel
from constants import IVA_PERCENT

class InventoryApp(tb.Window):
    """Aplicación principal de gestión de inventario"""
    def __init__(self):
        super().__init__(themename="cosmo")
        self.title("Sistema de Gestión de Inventario")
        self.geometry("1200x650")
        self.db = DatabaseManager()
        self.current_edit_id: Optional[int] = None
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
            columns=("id", "nombre", "cantidad", "precio", "costo"),
            show='headings',
            height=15,
            bootstyle="primary"
        )
        columns = [
            ("id", "ID"),
            ("nombre", "Nombre"),
            ("cantidad", "Cantidad"),
            ("precio", "Precio"),
            ("costo", "Costo")
        ]
        for col, text in columns:
            self.tree.heading(col, text=text)
            self.tree.column(col, anchor="center", width=100 if col != "id" else 0, stretch=tk.NO if col == "id" else tk.YES)
        self.tree.column("id")
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        self.tree.bind("<ButtonRelease-1>", self._on_product_selected)
        
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
            tb.Button(toolbar, text=text, bootstyle=style, command=command).pack(side=tk.LEFT, padx=5)
        
        # Panel derecho
        self.right_panel = tb.Frame(self, width=350)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)
        self._setup_right_panel()
    
    def _setup_right_panel(self):
        self.add_product_frame = tb.Frame(self.right_panel)
        self._build_add_product_form()
        
        self.sales_frame = tb.Frame(self.right_panel)
        tb.Label(self.sales_frame, text="Productos en Venta", font=('Helvetica', 12, 'bold')).pack(pady=5)
        self.sales_tree = tb.Treeview(
            self.sales_frame,
            columns=("producto", "cantidad", "precio", "subtotal"),
            show='headings',
            height=15,
            bootstyle="primary"
        )
        for col, text in [("producto", "Producto"), ("cantidad", "Cantidad"), 
                        ("precio", "Precio Unit."), ("subtotal", "Subtotal")]:
            self.sales_tree.heading(col, text=text)
            self.sales_tree.column(col, anchor="center", width=80)
        self.sales_tree.pack(fill=tk.BOTH, expand=True)
        
        self.total_frame = tb.Frame(self.sales_frame)
        self.total_frame.pack(fill=tk.X, pady=5)
        tb.Label(self.total_frame, text="Total Venta:", font=('Helvetica', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        self.total_venta_label = tb.Label(self.total_frame, text="$0.00", font=('Helvetica', 10, 'bold'))
        self.total_venta_label.pack(side=tk.LEFT)
        self.show_sales_view()
    
    def _build_add_product_form(self):
        form_frame = tb.Frame(self.add_product_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        tb.Label(form_frame, text="Agregar/Editar Producto", font=('Helvetica', 12, 'bold')).pack(pady=5)
        
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
        tb.Button(button_frame, text="Guardar", bootstyle="success", command=self._save_product).pack(side=tk.LEFT, padx=5)
        tb.Button(button_frame, text="Cancelar", bootstyle="secondary", command=self.show_sales_view).pack(side=tk.LEFT, padx=5)
        fields_frame.columnconfigure(1, weight=1)
    
    def _on_product_selected(self, event):
        """Manejador de evento cuando se selecciona un producto"""
        selected = self.tree.selection()
        if not selected:
            return
        
        item = self.tree.item(selected[0])
        product_id = item['values'][0]
        product_name = item['values'][1]
        product_price = item['values'][3]
        
        try:
            self.db.add_to_current_sales(product_id)
            self._load_sales()
            self.sale_panel.update_details(product_name, product_price, 1)
            self.product_entry.delete(0, tk.END)
            self.product_entry.insert(0, product_name)
            self.quantity_entry.delete(0, tk.END)
            self.quantity_entry.insert(0, "1")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
    
    def _load_products(self) -> None:
        """Carga los productos en el Treeview principal"""
        self.tree.delete(*self.tree.get_children())
        for producto in self.db.get_all_products():
            self.tree.insert("", tk.END, values=producto)
    
    def _load_sales(self):
        """Carga los productos en venta"""
        self.sales_tree.delete(*self.sales_tree.get_children())
        total_venta = 0
        for producto in self.db.get_current_sales():
            self.sales_tree.insert("", tk.END, values=producto)
            total_venta += producto[3]
        self.total_venta_label.config(text=f"${total_venta * (1 + IVA_PERCENT):.2f}")
    
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
            
            if self.current_edit_id:
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM productos WHERE id = ?", (self.current_edit_id,))
                    conn.commit()
                self.current_edit_id = None
            
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
            'id': item['values'][0],
            'nombre': item['values'][1],
            'cantidad': item['values'][2],
            'precio': item['values'][3],
            'costo': item['values'][4]
        }
        
        self.current_edit_id = product_data['id']
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
        
        product_id = self.tree.item(selected[0])['values'][0]
        product_name = self.tree.item(selected[0])['values'][1]
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar el producto {product_name}?"):
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM productos WHERE id = ?", (product_id,))
                conn.commit()
            
            self._load_products()
            messagebox.showinfo("Éxito", "Producto eliminado")
    
    def _update_sale_details(self) -> None:
        """Actualiza el panel de detalles de venta"""
        product_name = self.product_entry.get().strip()
        quantity = self.quantity_entry.get().strip()
        
        try:
            if not product_name or not quantity:
                raise ValueError("Complete todos los campos")
            
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError("La cantidad debe ser positiva")
            
            product_id = self.db.get_product_id(product_name)
            self.db.add_to_current_sales(product_id, quantity)
            
            # Obtener precio actualizado
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT precio FROM productos WHERE id = ?", (product_id,))
                price = cursor.fetchone()[0]
            
            self._load_sales()
            self.sale_panel.update_details(product_name, price, quantity)
        
        except ValueError as e:
            messagebox.showerror("Error", str(e))
    
    def _sell_product(self) -> None:
        """Realiza la venta del producto"""
        try:
            total_venta = self.db.process_sale()
            current_sales = self.db.get_current_sales()  # Esto debería estar vacío ahora
            
            messagebox.showinfo(
                "Venta realizada",
                f"Total de productos: {len(current_sales)}\n"
                f"Subtotal: ${total_venta:.2f}\n"
                f"IVA ({IVA_PERCENT*100:.0f}%): ${total_venta * IVA_PERCENT:.2f}\n"
                f"Total: ${total_venta * (1 + IVA_PERCENT):.2f}"
            )
            
            # Limpiar campos y actualizar vistas
            self.product_entry.delete(0, tk.END)
            self.quantity_entry.delete(0, tk.END)
            self.sale_panel.clear()
            self._load_products()
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
    
    def show_add_product_view(self):
        """Muestra el formulario para agregar/editar productos"""
        self.sales_frame.pack_forget()
        self.add_product_frame.pack(fill=tk.BOTH, expand=True)
        self._clear_entries()
        self.current_edit_id = None
    
    def show_sales_view(self):
        """Muestra la lista de productos en venta"""
        self.add_product_frame.pack_forget()
        self.sales_frame.pack(fill=tk.BOTH, expand=True)
        self._load_sales()