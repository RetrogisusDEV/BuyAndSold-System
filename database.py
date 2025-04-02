import sqlite3
from typing import List, Tuple, Optional
from constants import DB_NAME, IVA_PERCENT

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
                           producto_id INTEGER NOT NULL,
                           cantidad INTEGER NOT NULL,
                           precio_unitario REAL NOT NULL,
                           subtotal REAL NOT NULL,
                           FOREIGN KEY(producto_id) REFERENCES productos(id))''')
    
    def _get_connection(self) -> sqlite3.Connection:
        """Obtiene una conexión a la base de datos"""
        return sqlite3.connect(self.db_name)
    
    def add_or_update_product(self, nombre: str, cantidad: int, precio: float, costo: float) -> int:
        """Agrega o actualiza un producto en el inventario"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cantidad, costo FROM productos WHERE nombre = ?", (nombre,))
            if producto := cursor.fetchone():
                product_id, old_cantidad, old_costo = producto
                nueva_cantidad = old_cantidad + cantidad
                nuevo_costo = (old_cantidad * old_costo + cantidad * costo) / nueva_cantidad
                cursor.execute("UPDATE productos SET cantidad = ?, precio = ?, costo = ? WHERE id = ?", 
                             (nueva_cantidad, precio, nuevo_costo, product_id))
            else:
                cursor.execute("INSERT INTO productos (nombre, cantidad, precio, costo) VALUES (?, ?, ?, ?)", 
                             (nombre, cantidad, precio, costo))
                product_id = cursor.lastrowid
            
            total_gastado = cantidad * costo
            cursor.execute("UPDATE totales SET total_gastado = total_gastado + ?", (total_gastado,))
            return product_id
    
    def get_product_id(self, nombre: str) -> int:
        """Obtiene el ID de un producto por su nombre"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM productos WHERE nombre = ?", (nombre,))
            result = cursor.fetchone()
            if not result:
                raise ValueError("Producto no encontrado")
            return result[0]
    
    def add_to_current_sales(self, product_id: int, cantidad: int = 1) -> None:
        """Agrega un producto a las ventas actuales"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT precio FROM productos WHERE id = ?", (product_id,))
            precio = cursor.fetchone()[0]
            subtotal = precio * cantidad
            
            cursor.execute("SELECT cantidad FROM ventas_actuales WHERE producto_id = ?", (product_id,))
            if existing := cursor.fetchone():
                nueva_cantidad = existing[0] + cantidad
                nuevo_subtotal = nueva_cantidad * precio
                cursor.execute("UPDATE ventas_actuales SET cantidad = ?, subtotal = ? WHERE producto_id = ?",
                             (nueva_cantidad, nuevo_subtotal, product_id))
            else:
                cursor.execute("INSERT INTO ventas_actuales (producto_id, cantidad, precio_unitario, subtotal) VALUES (?, ?, ?, ?)",
                             (product_id, cantidad, precio, subtotal))
    
    def process_sale(self) -> float:
        """Procesa todas las ventas actuales y devuelve el total"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT producto_id, cantidad FROM ventas_actuales")
            current_sales = cursor.fetchall()
            total_venta = 0.0
            
            for producto_id, cantidad in current_sales:
                cursor.execute("SELECT cantidad FROM productos WHERE id = ?", (producto_id,))
                stock = cursor.fetchone()[0]
                if stock < cantidad:
                    raise ValueError(f"Stock insuficiente para producto ID {producto_id}")
                
                cursor.execute("UPDATE productos SET cantidad = cantidad - ? WHERE id = ?", (cantidad, producto_id))
                cursor.execute("SELECT subtotal FROM ventas_actuales WHERE producto_id = ?", (producto_id,))
                subtotal = cursor.fetchone()[0]
                total_venta += subtotal
            
            cursor.execute("UPDATE totales SET total_ventas = total_ventas + ?", (total_venta,))
            cursor.execute("DELETE FROM ventas_actuales")
            return total_venta
    
    def get_totals(self) -> Tuple[float, float]:
        """Obtiene los totales de ventas y gastos"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT total_ventas, total_gastado FROM totales")
            return cursor.fetchone()
    
    def get_all_products(self) -> List[Tuple[int, str, int, float, float]]:
        """Obtiene todos los productos del inventario"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nombre, cantidad, precio, costo FROM productos")
            return cursor.fetchall()
    
    def get_current_sales(self) -> List[Tuple[str, int, float, float]]:
        """Obtiene los productos en venta actuales con nombres"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""SELECT p.nombre, v.cantidad, v.precio_unitario, v.subtotal
                           FROM ventas_actuales v
                           JOIN productos p ON v.producto_id = p.id""")
            return cursor.fetchall()
    
    def clear_current_sales(self) -> None:
        """Limpia las ventas actuales"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ventas_actuales")