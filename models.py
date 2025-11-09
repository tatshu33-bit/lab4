import sqlite3
from datetime import datetime

def init_db():
    """Ініціалізація бази даних та створення таблиць"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Таблиця відгуків (Feedback)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # Таблиця товарів (Products)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            description TEXT,
            price DECIMAL(10, 2) NOT NULL,
            category TEXT NOT NULL,
            image_url TEXT,
            stock_quantity INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблиця клієнтів (Customers)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблиця замовлень (Orders)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            customer_phone TEXT,
            customer_address TEXT,
            total_amount DECIMAL(10, 2) NOT NULL,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id)
        )
    ''')
    
    # Таблиця елементів замовлення (Order Items)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_title TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Додаємо тестові дані
    add_sample_data(cursor)
    
    conn.commit()
    conn.close()
    print("✅ База даних успішно ініціалізована!")

def add_sample_data(cursor):
    """Додавання тестових даних"""
    
    # Тестові товари
    sample_products = [
        ('Хіба ревуть воли...', 'Панас Мирний', 'Класика української літератури', 250.00, 'Художня література', '📚'),
        ('Тигролови', 'Іван Багряний', 'Пригодницький роман', 280.00, 'Художня література', '📚'),
        ('Майстер і Маргарита', 'Михайло Булгаков', 'Філософський роман', 320.00, 'Художня література', '📚'),
        ('1984', 'Джордж Орвелл', 'Антиутопія', 290.00, 'Художня література', '📚'),
        ('Python для початківців', 'Марк Лутц', 'Навчальний посібник', 450.00, 'Наукова література', '📚'),
        ('Історія України', 'Петро Толочко', 'Наукове видання', 380.00, 'Наукова література', '📚')
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO products (title, author, description, price, category, image_url, stock_quantity)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [(p[0], p[1], p[2], p[3], p[4], p[5], 10) for p in sample_products])
    
    # Тестові відгуки
    sample_feedback = [
        ('Олена Петренко', 'olena@example.com', 'Чудовий магазин! Швидка доставка.', 5),
        ('Іван Коваленко', 'ivan@example.com', 'Якісні книги, але дороговато.', 4),
        ('Марія Шевченко', 'maria@example.com', 'Дуже задоволена обслуговуванням!', 5)
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO feedback (name, email, message, rating)
        VALUES (?, ?, ?, ?)
    ''', sample_feedback)

def get_db_connection():
    """Отримання з'єднання з базою даних"""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Функції для роботи з відгуками (CRUD)
def add_feedback(name, email, message, rating):
    """Додавання нового відгуку"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO feedback (name, email, message, rating) VALUES (?, ?, ?, ?)',
        (name, email, message, rating)
    )
    conn.commit()
    conn.close()

def get_all_feedback():
    """Отримання всіх відгуків"""
    conn = get_db_connection()
    feedback = conn.execute('SELECT * FROM feedback ORDER BY created_at DESC').fetchall()
    conn.close()
    return feedback

def delete_feedback(feedback_id):
    """Видалення відгуку"""
    conn = get_db_connection()
    conn.execute('DELETE FROM feedback WHERE id = ?', (feedback_id,))
    conn.commit()
    conn.close()

# Функції для роботи з товарами
def get_all_products():
    """Отримання всіх товарів"""
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    conn.close()
    return products

def get_product_by_id(product_id):
    """Отримання товару за ID"""
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    return product

def add_product(title, author, description, price, category, image_url, stock_quantity):
    """Додавання нового товару"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO products (title, author, description, price, category, image_url, stock_quantity) 
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (title, author, description, price, category, image_url, stock_quantity)
    )
    conn.commit()
    conn.close()

# Функції для роботи з клієнтами
def add_customer(name, email, phone, address):
    """Додавання нового клієнта"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO customers (name, email, phone, address) VALUES (?, ?, ?, ?)',
        (name, email, phone, address)
    )
    conn.commit()
    conn.close()

def get_all_customers():
    """Отримання всіх клієнтів"""
    conn = get_db_connection()
    customers = conn.execute('SELECT * FROM customers ORDER BY created_at DESC').fetchall()
    conn.close()
    return customers

# Функції для роботи з замовленнями
def create_order(customer_data, cart_items, total_amount):
    """Створення нового замовлення"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Створюємо замовлення
    cursor.execute(
        '''INSERT INTO orders (customer_name, customer_email, customer_phone, customer_address, total_amount)
        VALUES (?, ?, ?, ?, ?)''',
        (customer_data['name'], customer_data['email'], customer_data['phone'], 
         customer_data['address'], total_amount)
    )
    
    order_id = cursor.lastrowid
    
    # Додаємо товари до замовлення
    for item in cart_items:
        cursor.execute(
            '''INSERT INTO order_items (order_id, product_id, product_title, quantity, price)
            VALUES (?, ?, ?, ?, ?)''',
            (order_id, item['id'], item['title'], item['quantity'], item['price'])
        )
    
    conn.commit()
    conn.close()
    return order_id

def get_all_orders():
    """Отримання всіх замовлень"""
    conn = get_db_connection()
    orders = conn.execute('''
        SELECT o.*, COUNT(oi.id) as items_count 
        FROM orders o 
        LEFT JOIN order_items oi ON o.id = oi.order_id 
        GROUP BY o.id 
        ORDER BY o.created_at DESC
    ''').fetchall()
    conn.close()
    return orders

def update_order_status(order_id, status):
    """Оновлення статусу замовлення"""
    conn = get_db_connection()
    conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

def get_order_details(order_id):
    """Отримання деталей замовлення"""
    conn = get_db_connection()
    order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (order_id,)).fetchall()
    conn.close()
    return order, items
