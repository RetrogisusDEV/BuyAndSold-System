import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
import ttkbootstrap as tb

# Funcion para crear el db
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

# Funcion para agregar o actualizar un producto
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
    
    # Actualizar total gastado
    total_gastado = cantidad * costo
    cursor.execute("UPDATE totales SET total_gastado = total_gastado + ?", (total_gastado,))
    
    conexion.commit()
    conexion.close()

# Funcion para vender un producto
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
            messagebox.showinfo("Éxito", f"Vendidos {cantidad_vendida} de {nombre}.")
        else:
            messagebox.showerror("Error", "No hay suficiente cantidad disponible.")
    else:
        messagebox.showerror("Error", "Producto no encontrado.")
    
    conexion.close()

# Funcion para mostrar totales
def mostrar_totales():
    conexion = sqlite3.connect("inventario.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM totales")
    totales = cursor.fetchone()
    conexion.close()
    return totales

# Funcion para mostrar productos en el Treeview
def mostrar_productos(tree):
    for row in tree.get_children():
        tree.delete(row)  # Limpiar el Treeview
    conexion = sqlite3.connect("inventario.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT nombre, cantidad, precio, costo FROM productos")
    productos = cursor.fetchall()
    for producto in productos:
        tree.insert("", tk.END, values=(producto[0], producto[1], producto[2], producto[3]))
    conexion.close()

# Interfaz gráfica
def interfaz_grafica():
    ventana = tb.Window(themename="cosmo")  
    ventana.title("Sistema de Compra y Venta")
    
    # Campos de entrada
    frame_entrada = tb.Frame(ventana)
    frame_entrada.pack(pady=10)

    lbl_nombre = tb.Label(frame_entrada, text="Nombre del Producto:")
    lbl_nombre.grid(row=0, column=0, padx=5, pady=5)
    entrada_nombre = tb.Entry(frame_entrada)
    entrada_nombre.grid(row=0, column=1, padx=5, pady=5)
    
    lbl_cantidad = tb.Label(frame_entrada, text="Cantidad:")
    lbl_cantidad.grid(row=1, column=0, padx=5, pady=5)
    entrada_cantidad = tb.Entry(frame_entrada)
    entrada_cantidad.grid(row=1, column=1, padx=5, pady=5)
    
    lbl_precio = tb.Label(frame_entrada, text="Precio:")
    lbl_precio.grid(row=2, column=0, padx=5, pady=5)
    entrada_precio = tb.Entry(frame_entrada)
    entrada_precio.grid(row=2, column=1, padx=5, pady=5)
    
    lbl_costo = tb.Label(frame_entrada, text="Costo:")
    lbl_costo.grid(row=3, column=0, padx=5, pady=5)
    entrada_costo = tb.Entry(frame_entrada)
    entrada_costo.grid(row=3, column=1, padx=5, pady=5)
    
    # Treeview para mostrar productos
    columnas = ("Nombre", "Cantidad", "Precio", "Costo")
    tree = ttk.Treeview(ventana, columns=columnas, show='headings', height=8)
    tree.pack(pady=10)
    
    for col in columnas:
        tree.heading(col, text=col)
        tree.column(col, anchor="center")
    
    # Funciones de los botones
    def agregar():
        nombre = entrada_nombre.get()
        cantidad = int(entrada_cantidad.get())
        precio = float(entrada_precio.get())
        costo = float(entrada_costo.get())
        agregar_producto(nombre, cantidad, precio, costo)
        mostrar_productos(tree)  # Actualizar el Treeview
        entrada_nombre.delete(0, tk.END)
        entrada_cantidad.delete(0, tk.END)
        entrada_precio.delete(0, tk.END)
        entrada_costo.delete(0, tk.END)
    
    def vender():
        nombre = entrada_nombre.get()
        cantidad = int(entrada_cantidad.get())
        vender_producto(nombre, cantidad)
        mostrar_productos(tree)  # Actualizar el Treeview
        entrada_nombre.delete(0, tk.END)
        entrada_cantidad.delete(0, tk.END)

    def mostrar():
        totales = mostrar_totales()
        messagebox.showinfo("Totales", f"Total Ventas: {totales[1]}\nTotal Gastado: {totales[2]}")

    # Botones
    frame_botones = tb.Frame(ventana)
    frame_botones.pack(pady=10)

    btn_agregar = tb.Button(frame_botones, text="Agregar Producto", command=agregar)
    btn_agregar.grid(row=0, column=0, padx=5)

    btn_vender = tb.Button(frame_botones, text="Vender Producto", command=vender)
    btn_vender.grid(row=0, column=1, padx=5)

    btn_mostrar = tb.Button(frame_botones, text="Mostrar Totales", command=mostrar)
    btn_mostrar.grid(row=0, column=2, padx=5)

    # Inicializar el Treeview con productos
    mostrar_productos(tree)

    ventana.mainloop()

# Inicializar la aplicación
if __name__ == "__main__":
    crear_tablas()
    interfaz_grafica()