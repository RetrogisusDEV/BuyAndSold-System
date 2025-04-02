import sqlite3
import tkinter as tk
from tkinter import messagebox
from typing import List, Dict, Tuple, Optional, NamedTuple
import ttkbootstrap as tb
from ttkbootstrap.dialogs import Dialog

# Constantes y tipos
DB_NAME = "inventario.db"
IVA_PERCENT = 0.19


class Product(NamedTuple):
    nombre: str
    cantidad: int
    precio: float
    costo: float


class SaleItem(NamedTuple):
    producto: str
    cantidad: int
    precio_unitario: float
    subtotal: float


class Totals(NamedTuple):
    ventas: float
    gastos: float


class DatabaseManager:
    """Manejador centralizado de operaciones de base de datos"""

    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Inicializa la estructura de la base de datos"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS productos
                           (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           nombre TEXT NOT NULL UNIQUE,
                           cantidad INTEGER NOT NULL,
                           precio REAL NOT NULL,
                           costo REAL NOT NULL)"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS totales
                           (id INTEGER PRIMARY KEY,
                           total_ventas REAL DEFAULT 0,
                           total_gastado REAL DEFAULT 0)"""
            )
            cursor.execute("INSERT OR IGNORE INTO totales (id) VALUES (1)")
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS ventas_actuales
                           (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           producto TEXT NOT NULL,
                           cantidad INTEGER NOT NULL,
                           precio_unitario REAL NOT NULL,
                           subtotal REAL NOT NULL)"""
            )
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Obtiene una conexión a la base de datos"""
        return sqlite3.connect(self.db_name)

    def execute_query(
        self, query: str, params: Tuple = (), commit: bool = False
    ) -> Optional[List[Tuple]]:
        """Ejecuta una consulta genérica con manejo de errores"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                if commit:
                    conn.commit()
                if query.strip().upper().startswith("SELECT"):
                    return cursor.fetchall()
                return None
            except sqlite3.Error as e:
                conn.rollback()
                raise DatabaseError(f"Error en base de datos: {str(e)}")


class ProductRepository:
    """Repositorio para operaciones específicas de productos"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_all(self) -> List[Product]:
        """Obtiene todos los productos"""
        results = self.db.execute_query(
            "SELECT nombre, cantidad, precio, costo FROM productos"
        )
        return [Product(*row) for row in results] if results else []

    def get_by_name(self, nombre: str) -> Optional[Product]:
        """Obtiene un producto por nombre"""
        result = self.db.execute_query(
            "SELECT nombre, cantidad, precio, costo FROM productos WHERE nombre = ?",
            (nombre,),
        )
        return Product(*result[0]) if result else None

    def add_or_update(self, product: Product) -> None:
        """Agrega o actualiza un producto"""
        existing = self.get_by_name(product.nombre)
        if existing:
            new_quantity = existing.cantidad + product.cantidad
            self.db.execute_query(
                "UPDATE productos SET cantidad = ?, precio = ?, costo = ? WHERE nombre = ?",
                (new_quantity, product.precio, product.costo, product.nombre),
                commit=True,
            )
        else:
            self.db.execute_query(
                "INSERT INTO productos (nombre, cantidad, precio, costo) VALUES (?, ?, ?, ?)",
                (product.nombre, product.cantidad, product.precio, product.costo),
                commit=True,
            )

        # Actualizar total de gastos
        total_gastado = product.cantidad * product.costo
        self.db.execute_query(
            "UPDATE totales SET total_gastado = total_gastado + ?",
            (total_gastado,),
            commit=True,
        )

    def remove(self, nombre: str) -> None:
        """Elimina un producto"""
        self.db.execute_query(
            "DELETE FROM productos WHERE nombre = ?", (nombre,), commit=True
        )


class SalesRepository:
    """Repositorio para operaciones de ventas"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_current_sales(self) -> List[SaleItem]:
        """Obtiene las ventas actuales"""
        results = self.db.execute_query(
            "SELECT producto, cantidad, precio_unitario, subtotal FROM ventas_actuales"
        )
        return [SaleItem(*row) for row in results] if results else []

    def add_to_current_sales(self, nombre: str, cantidad: int = 1) -> None:
        """Agrega un producto a las ventas actuales"""
        product = ProductRepository(self.db).get_by_name(nombre)
        if not product:
            raise ValueError("Producto no encontrado")

        if product.cantidad < cantidad:
            raise ValueError(f"Stock insuficiente. Disponible: {product.cantidad}")

        # Verificar si el producto ya está en ventas actuales
        existing = next(
            (item for item in self.get_current_sales() if item.producto == nombre), None
        )

        if existing:
            new_quantity = existing.cantidad + cantidad
            new_subtotal = new_quantity * existing.precio_unitario
            self.db.execute_query(
                "UPDATE ventas_actuales SET cantidad = ?, subtotal = ? WHERE producto = ?",
                (new_quantity, new_subtotal, nombre),
                commit=True,
            )
        else:
            subtotal = cantidad * product.precio
            self.db.execute_query(
                "INSERT INTO ventas_actuales (producto, cantidad, precio_unitario, subtotal) VALUES (?, ?, ?, ?)",
                (nombre, cantidad, product.precio, subtotal),
                commit=True,
            )

    def process_sale(self) -> float:
        """Procesa la venta actual y devuelve el total"""
        current_sales = self.get_current_sales()
        if not current_sales:
            raise ValueError("No hay productos en la venta actual")

        total = 0.0
        product_repo = ProductRepository(self.db)

        for item in current_sales:
            # Verificar stock nuevamente antes de procesar
            product = product_repo.get_by_name(item.producto)
            if not product or product.cantidad < item.cantidad:
                raise ValueError(f"Stock insuficiente para {item.producto}")

            # Actualizar inventario
            new_quantity = product.cantidad - item.cantidad
            self.db.execute_query(
                "UPDATE productos SET cantidad = ? WHERE nombre = ?",
                (new_quantity, item.producto),
                commit=True,
            )

            # Sumar al total
            total += item.subtotal

        # Actualizar total de ventas
        self.db.execute_query(
            "UPDATE totales SET total_ventas = total_ventas + ?", (total,), commit=True
        )

        # Limpiar ventas actuales
        self.db.execute_query("DELETE FROM ventas_actuales", commit=True)

        return total * (1 + IVA_PERCENT)

    def clear_current_sales(self) -> None:
        """Limpia las ventas actuales"""
        self.db.execute_query("DELETE FROM ventas_actuales", commit=True)


class TotalsRepository:
    """Repositorio para operaciones con totales"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_totals(self) -> Totals:
        """Obtiene los totales acumulados"""
        result = self.db.execute_query(
            "SELECT total_ventas, total_gastado FROM totales"
        )
        return Totals(*result[0]) if result else Totals(0.0, 0.0)


class DatabaseError(Exception):
    """Excepción personalizada para errores de base de datos"""

    pass


class SaleDetailsPanel(tb.Frame):
    """Panel para mostrar los detalles de la venta actual"""

    def __init__(self, master):
        super().__init__(master, padding=10)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configura los componentes de la interfaz"""
        tb.Label(self, text="Detalles de Venta", font=("Helvetica", 12, "bold")).pack(
            pady=5
        )

        self.entries = {}
        fields = [
            ("Producto:", "producto"),
            ("Precio Unitario:", "precio"),
            ("Cantidad:", "cantidad"),
            ("Subtotal:", "subtotal"),
            (f"IVA ({IVA_PERCENT*100:.0f}%):", "iva"),
            ("Total:", "total"),
        ]

        for label, key in fields:
            frame = tb.Frame(self)
            frame.pack(fill=tk.X, pady=2)

            tb.Label(frame, text=label, width=15, anchor="w").pack(side=tk.LEFT, padx=5)
            entry = tb.Entry(frame, state="readonly")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entries[key] = entry

        tb.Button(
            self,
            text="Ver Totales",
            bootstyle="info",
            command=self.master.show_totals,
            width=15,
        ).pack(pady=10)

    def update_details(self, sale_item: SaleItem) -> None:
        """Actualiza los detalles con la información de un ítem de venta"""
        iva = sale_item.subtotal * IVA_PERCENT
        total = sale_item.subtotal + iva

        for entry in self.entries.values():
            entry.config(state="normal")
            entry.delete(0, tk.END)

        self.entries["producto"].insert(0, sale_item.producto)
        self.entries["precio"].insert(0, f"${sale_item.precio_unitario:.2f}")
        self.entries["cantidad"].insert(0, str(sale_item.cantidad))
        self.entries["subtotal"].insert(0, f"${sale_item.subtotal:.2f}")
        self.entries["iva"].insert(0, f"${iva:.2f}")
        self.entries["total"].insert(0, f"${total:.2f}")

        for entry in self.entries.values():
            entry.config(state="readonly")

    def clear(self) -> None:
        """Limpia todos los campos"""
        for entry in self.entries.values():
            entry.config(state="normal")
            entry.delete(0, tk.END)
            entry.config(state="readonly")


class ProductForm(tb.Frame):
    """Formulario para agregar/editar productos"""

    def __init__(self, master, main_app):  # Añadir main_app como parámetro
        super().__init__(master)
        self.main_app = main_app  # Guardar referencia a la app principal
        self._setup_form()
        self.current_product: Optional[str] = None

    def _setup_form(self) -> None:
        """Configura los componentes del formulario"""
        tb.Label(
            self, text="Agregar/Editar Producto", font=("Helvetica", 12, "bold")
        ).pack(pady=5)

        self.entries = {}
        fields = [
            ("Nombre del Producto:", "nombre"),
            ("Cantidad:", "cantidad"),
            ("Precio de Venta:", "precio"),
            ("Costo:", "costo"),
        ]

        for label, key in fields:
            frame = tb.Frame(self)
            frame.pack(fill=tk.X, pady=5)

            tb.Label(frame, text=label, width=20, anchor="w").pack(side=tk.LEFT, padx=5)
            entry = tb.Entry(frame)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entries[key] = entry

        button_frame = tb.Frame(self)
        button_frame.pack(fill=tk.X, pady=10)

        tb.Button(
            button_frame, text="Guardar", bootstyle="success", command=self._on_save
        ).pack(side=tk.LEFT, padx=5)

        tb.Button(
            button_frame,
            text="Cancelar",
            bootstyle="secondary",
            command=self.main_app.show_sales_view,  # Usar main_app en lugar de master
        ).pack(side=tk.LEFT, padx=5)

    def load_product(self, product: Product) -> None:
        """Carga los datos de un producto en el formulario"""
        self.current_product = product.nombre
        self._clear_entries()
        self.entries["nombre"].insert(0, product.nombre)
        self.entries["cantidad"].insert(0, str(product.cantidad))
        self.entries["precio"].insert(0, str(product.precio))
        self.entries["costo"].insert(0, str(product.costo))

    def _on_save(self) -> None:
        """Manejador del evento de guardar"""
        try:
            product = self._validate_and_get_product()
            ProductRepository(self.master.db).add_or_update(product)
            self.master.load_products()
            messagebox.showinfo("Éxito", "Producto guardado correctamente")
            self.master.show_sales_view()
            self._clear_entries()
            self.current_product = None
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _validate_and_get_product(self) -> Product:
        """Valida los datos del formulario y retorna un objeto Product"""
        nombre = self.entries["nombre"].get().strip()
        cantidad = self.entries["cantidad"].get().strip()
        precio = self.entries["precio"].get().strip()
        costo = self.entries["costo"].get().strip()

        if not all([nombre, cantidad, precio, costo]):
            raise ValueError("Todos los campos son obligatorios")

        try:
            cantidad_int = int(cantidad)
            precio_float = float(precio)
            costo_float = float(costo)

            if cantidad_int <= 0 or precio_float <= 0 or costo_float <= 0:
                raise ValueError("Los valores deben ser positivos")

            return Product(nombre, cantidad_int, precio_float, costo_float)

        except ValueError:
            raise ValueError("Valores numéricos inválidos")

    def _clear_entries(self) -> None:
        """Limpia todos los campos del formulario"""
        for entry in self.entries.values():
            entry.delete(0, tk.END)


class SalesPanel(tb.Frame):
    """Panel para mostrar los productos en venta actual"""

    def __init__(self, master):
        super().__init__(master)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configura los componentes de la interfaz"""
        tb.Label(self, text="Productos en Venta", font=("Helvetica", 12, "bold")).pack(
            pady=5
        )

        # Treeview para productos en venta
        self.tree = tb.Treeview(
            self,
            columns=("producto", "cantidad", "precio", "subtotal"),
            show="headings",
            height=15,
            bootstyle="primary",
        )
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Configurar columnas
        columns = [
            ("producto", "Producto", 150),
            ("cantidad", "Cantidad", 80),
            ("precio", "Precio Unit.", 100),
            ("subtotal", "Subtotal", 100),
        ]

        for col, text, width in columns:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center")

        # Panel de totales
        total_frame = tb.Frame(self)
        total_frame.pack(fill=tk.X, pady=5)

        tb.Label(total_frame, text="Total Venta:", font=("Helvetica", 10, "bold")).pack(
            side=tk.LEFT, padx=5
        )
        self.total_label = tb.Label(
            total_frame, text="$0.00", font=("Helvetica", 10, "bold")
        )
        self.total_label.pack(side=tk.LEFT)

    def update_sales(self, sales: List[SaleItem]) -> None:
        """Actualiza la lista de productos en venta"""
        self.tree.delete(*self.tree.get_children())

        total = 0.0
        for item in sales:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    item.producto,
                    item.cantidad,
                    f"${item.precio_unitario:.2f}",
                    f"${item.subtotal:.2f}",
                ),
            )
            total += item.subtotal

        total_con_iva = total * (1 + IVA_PERCENT)
        self.total_label.config(text=f"${total_con_iva:.2f}")


class ProductTable(tb.Frame):
    """Tabla de productos con funcionalidad de selección"""

    def __init__(self, master):
        super().__init__(master)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Configura los componentes de la interfaz"""
        # Controles de búsqueda
        search_frame = tb.Frame(self)
        search_frame.pack(fill=tk.X, pady=10)

        tb.Label(search_frame, text="Producto:").pack(side=tk.LEFT, padx=5)
        self.product_entry = tb.Entry(search_frame)
        self.product_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        tb.Label(search_frame, text="Cantidad:").pack(side=tk.LEFT, padx=5)
        self.quantity_entry = tb.Entry(search_frame, width=10)
        self.quantity_entry.pack(side=tk.LEFT, padx=5)

        # Tabla de productos
        self.tree = tb.Treeview(
            self,
            columns=("nombre", "cantidad", "precio", "costo"),
            show="headings",
            height=15,
            bootstyle="primary",
        )
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)

        # Configurar columnas
        columns = [
            ("nombre", "Nombre", 200),
            ("cantidad", "Cantidad", 80),
            ("precio", "Precio", 100),
            ("costo", "Costo", 100),
        ]

        for col, text, width in columns:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center")

        # Evento de selección
        self.tree.bind("<ButtonRelease-1>", self._on_product_selected)

        # Barra de herramientas
        toolbar = tb.Frame(self)
        toolbar.pack(fill=tk.X, pady=10)

        buttons = [
            ("Agregar Producto", "success", self.master.show_add_product_view),
            ("Actualizar Valores", "primary", self._update_sale_details),
            ("Vender", "danger", self.master.process_sale),
            ("Editar Producto", "warning", self._edit_product),
            ("Eliminar Producto", "light", self._delete_product),
        ]

        for text, style, command in buttons:
            tb.Button(toolbar, text=text, bootstyle=style, command=command).pack(
                side=tk.LEFT, padx=5
            )

    def load_products(self, products: List[Product]) -> None:
        """Carga los productos en la tabla"""
        self.tree.delete(*self.tree.get_children())
        for product in products:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    product.nombre,
                    product.cantidad,
                    f"${product.precio:.2f}",
                    f"${product.costo:.2f}",
                ),
            )

    def _on_product_selected(self, event) -> None:
        """Manejador del evento de selección de producto"""
        selected = self.tree.selection()
        if not selected:
            return

        product_name = self.tree.item(selected[0])["values"][0]
        self.product_entry.delete(0, tk.END)
        self.product_entry.insert(0, product_name)
        self.quantity_entry.delete(0, tk.END)
        self.quantity_entry.insert(0, "1")

        try:
            SalesRepository(self.master.db).add_to_current_sales(product_name)
            self.master.load_sales()

            # Mostrar detalles del producto agregado
            current_sales = SalesRepository(self.master.db).get_current_sales()
            added_item = next(
                item for item in current_sales if item.producto == product_name
            )
            self.master.sale_panel.update_details(added_item)
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _update_sale_details(self) -> None:
        """Actualiza los detalles de venta con la cantidad especificada"""
        product_name = self.product_entry.get().strip()
        quantity_str = self.quantity_entry.get().strip()

        if not product_name or not quantity_str:
            messagebox.showerror("Error", "Complete todos los campos")
            return

        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                raise ValueError("La cantidad debe ser positiva")

            SalesRepository(self.master.db).add_to_current_sales(product_name, quantity)
            self.master.load_sales()

            current_sales = SalesRepository(self.master.db).get_current_sales()
            added_item = next(
                item for item in current_sales if item.producto == product_name
            )
            self.master.sale_panel.update_details(added_item)
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _edit_product(self) -> None:
        """Prepara la edición de un producto seleccionado"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un producto")
            return

        product_name = self.tree.item(selected[0])["values"][0]
        product = ProductRepository(self.master.db).get_by_name(product_name)

        if product:
            self.master.product_form.load_product(product)
            self.master.show_add_product_view()

    def _delete_product(self) -> None:
        """Elimina el producto seleccionado"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Advertencia", "Seleccione un producto")
            return

        product_name = self.tree.item(selected[0])["values"][0]

        if messagebox.askyesno("Confirmar", f"¿Eliminar el producto {product_name}?"):
            ProductRepository(self.master.db).remove(product_name)
            self.master.load_products()
            messagebox.showinfo("Éxito", "Producto eliminado")


class InventoryApp(tb.Window):
    """Aplicación principal de gestión de inventario"""
    def __init__(self):
        super().__init__(themename="cosmo")
        self.title("Sistema de Gestión de Inventario")
        self.geometry("1200x650")
        
        # Inicializar componentes
        self.db = DatabaseManager()
        self._setup_ui()
        self.load_products()
        self.load_sales()
    
    def _setup_ui(self) -> None:
        """Configura la interfaz de usuario principal"""
        # Panel izquierdo - Detalles de venta
        self.sale_panel = SaleDetailsPanel(self)
        self.sale_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # Panel central - Tabla de productos
        self.product_table = ProductTable(self)
        self.product_table.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=10, pady=10)
        
        # Panel derecho - Contenedor de vistas alternas
        self.right_panel = tb.Frame(self, width=350)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)
        
        # Vistas del panel derecho
        self.product_form = ProductForm(self.right_panel, self)  # Pasar self como main_app
        self.sales_panel = SalesPanel(self.right_panel)
        
        # Mostrar vista inicial
        self.show_sales_view()

    def load_products(self) -> None:
        """Carga los productos desde la base de datos"""
        products = ProductRepository(self.db).get_all()
        self.product_table.load_products(products)

    def load_sales(self) -> None:
        """Carga las ventas actuales desde la base de datos"""
        sales = SalesRepository(self.db).get_current_sales()
        self.sales_panel.update_sales(sales)

    def show_add_product_view(self) -> None:
        """Muestra el formulario para agregar/editar productos"""
        self.sales_panel.pack_forget()
        self.product_form.pack(fill=tk.BOTH, expand=True)

    def show_sales_view(self) -> None:
        """Muestra la lista de productos en venta"""
        self.product_form.pack_forget()
        self.sales_panel.pack(fill=tk.BOTH, expand=True)
        self.load_sales()

    def process_sale(self) -> None:
        """Procesa la venta actual"""
        try:
            total = SalesRepository(self.db).process_sale()

            messagebox.showinfo(
                "Venta realizada",
                f"Venta completada con éxito\n" f"Total: ${total:.2f}",
            )

            # Actualizar interfaces
            self.load_products()
            self.load_sales()
            self.sale_panel.clear()
            self.product_table.product_entry.delete(0, tk.END)
            self.product_table.quantity_entry.delete(0, tk.END)

        except ValueError as e:
            messagebox.showerror("Error en venta", str(e))

    def show_totals(self) -> None:
        """Muestra los totales acumulados del sistema"""
        totals = TotalsRepository(self.db).get_totals()
        ganancias = totals.ventas - totals.gastos

        messagebox.showinfo(
            "Totales del Sistema",
            f"Ventas Totales: ${totals.ventas:.2f}\n"
            f"Gastos Totales: ${totals.gastos:.2f}\n"
            f"Ganancias: ${ganancias:.2f}\n\n"
            f"Margen de ganancia: {(ganancias/totals.ventas*100 if totals.ventas else 0):.1f}%",
        )


if __name__ == "__main__":
    app = InventoryApp()
    app.mainloop()
