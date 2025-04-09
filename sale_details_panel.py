import tkinter as tk
import ttkbootstrap as tb
from constants import IVA_PERCENT

class SaleDetailsPanel(tb.Frame):
    """Panel para mostrar los detalles de la venta"""
    def __init__(self, master):
        super().__init__(master, padding=10)
        self._create_ui()
    
    def _create_ui(self):
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
        iva_percent = self.master.db.get_iva_percent()  # Obtener de DB
        subtotal = precio * cantidad
        iva = subtotal * iva_percent
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