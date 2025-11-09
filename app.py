from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import models
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Змініть на випадковий ключ

# Ініціалізація бази даних при запуску
@app.before_first_request
def init_database():
    models.init_db()

# Головна сторінка
@app.route('/')
def home():
    products = models.get_all_products()[:4]  # Останні 4 товари
    return render_template('index.html', products=products)

# Сторінка "Про нас"
@app.route('/about')
def about():
    return render_template('about.html')

# Каталог товарів
@app.route('/catalog')
def catalog():
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    
    products = models.get_all_products()
    
    # Фільтрація за категорією
    if category:
        products = [p for p in products if p['category'] == category]
    
    # Пошук
    if search:
        search_lower = search.lower()
        products = [p for p in products if search_lower in p['title'].lower() or search_lower in p['author'].lower()]
    
    # Отримуємо унікальні категорії для фільтра
    categories = list(set([p['category'] for p in models.get_all_products()]))
    
    return render_template('catalog.html', products=products, categories=categories, 
                         selected_category=category, search_query=search)

# Контакти та форма зворотного зв'язку
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        rating = int(request.form['rating'])
        
        models.add_feedback(name, email, message, rating)
        flash('Дякуємо за ваш відгук!', 'success')
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

# Кошик
@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    return render_template('shop/cart.html', cart_items=cart_items, total=total)

# Додавання товару до кошика
@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    product = models.get_product_by_id(product_id)
    if not product:
        flash('Товар не знайдено', 'error')
        return redirect(url_for('catalog'))
    
    cart = session.get('cart', [])
    
    # Перевіряємо, чи товар вже є в кошику
    for item in cart:
        if item['id'] == product_id:
            item['quantity'] += 1
            break
    else:
        cart.append({
            'id': product['id'],
            'title': product['title'],
            'author': product['author'],
            'price': float(product['price']),
            'quantity': 1,
            'image_url': product['image_url']
        })
    
    session['cart'] = cart
    flash('Товар додано до кошика!', 'success')
    return redirect(url_for('catalog'))

# Видалення товару з кошика
@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', [])
    cart = [item for item in cart if item['id'] != product_id]
    session['cart'] = cart
    flash('Товар видалено з кошика', 'success')
    return redirect(url_for('cart'))

# Оформлення замовлення
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_items = session.get('cart', [])
    if not cart_items:
        flash('Кошик порожній', 'error')
        return redirect(url_for('cart'))
    
    if request.method == 'POST':
        customer_data = {
            'name': request.form['name'],
            'email': request.form['email'],
            'phone': request.form['phone'],
            'address': request.form['address']
        }
        
        total_amount = sum(item['price'] * item['quantity'] for item in cart_items)
        
        # Створюємо замовлення
        order_id = models.create_order(customer_data, cart_items, total_amount)
        
        # Очищаємо кошик
        session['cart'] = []
        
        flash(f'Замовлення #{order_id} успішно оформлено!', 'success')
        return redirect(url_for('home'))
    
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    return render_template('shop/order.html', cart_items=cart_items, total=total)

# Адмін-панель
@app.route('/admin')
def admin_dashboard():
    # Проста перевірка доступу (в реальному додатку потрібна автентифікація)
    feedback_count = len(models.get_all_feedback())
    products_count = len(models.get_all_products())
    orders_count = len(models.get_all_orders())
    customers_count = len(models.get_all_customers())
    
    return render_template('admin/dashboard.html', 
                         feedback_count=feedback_count,
                         products_count=products_count,
                         orders_count=orders_count,
                         customers_count=customers_count)

# Управління відгуками (адмін)
@app.route('/admin/feedback')
def admin_feedback():
    feedback_list = models.get_all_feedback()
    return render_template('admin/feedback.html', feedback_list=feedback_list)

# Видалення відгуку (адмін)
@app.route('/admin/feedback/delete/<int:feedback_id>')
def delete_feedback(feedback_id):
    models.delete_feedback(feedback_id)
    flash('Відгук видалено', 'success')
    return redirect(url_for('admin_feedback'))

# Управління товарами (адмін)
@app.route('/admin/products')
def admin_products():
    products = models.get_all_products()
    return render_template('admin/products.html', products=products)

# Додавання товару (адмін)
@app.route('/admin/products/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        image_url = request.form['image_url']
        stock_quantity = int(request.form['stock_quantity'])
        
        models.add_product(title, author, description, price, category, image_url, stock_quantity)
        flash('Товар успішно додано!', 'success')
        return redirect(url_for('admin_products'))
    
    return render_template('admin/product_form.html')

# Управління замовленнями (адмін)
@app.route('/admin/orders')
def admin_orders():
    orders = models.get_all_orders()
    return render_template('admin/orders.html', orders=orders)

# Оновлення статусу замовлення (адмін)
@app.route('/admin/orders/update_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    new_status = request.form['status']
    models.update_order_status(order_id, new_status)
    flash('Статус замовлення оновлено', 'success')
    return redirect(url_for('admin_orders'))

# Управління клієнтами
@app.route('/admin/customers')
def admin_customers():
    customers = models.get_all_customers()
    return render_template('admin/customers.html', customers=customers)

if __name__ == '__main__':
    app.run(debug=True)
