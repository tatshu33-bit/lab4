# Логічна схема БД «ТехноМарт» (3НФ)

## Відношення (PK — первинний ключ, FK — зовнішній, UQ — унікальне)

| Таблиця | Атрибути |
|---|---|
| **regions** | **region_id** PK, region_name UQ, region_code UQ |
| **suppliers** | **supplier_id** PK, company_name, contact_name, contact_title, address, city, region_id FK→regions, postal_code, phone, email, website |
| **categories** | **category_id** PK, category_name UQ, description, picture_url |
| **products** | **product_id** PK, product_name, supplier_id FK→suppliers, category_id FK→categories, quantity_per_unit, unit_price, units_in_stock, units_on_order, reorder_level, discontinued, description, picture_url |
| **employees** | **employee_id** PK, last_name, first_name, middle_name, title, birth_date, hire_date, address, city, region_id FK→regions, postal_code, phone, email UQ, salary, reports_to FK→employees |
| **customers** | **customer_id** PK, company_name, contact_name, contact_title, address, city, region_id FK→regions, postal_code, phone, email UQ, registration_date, customer_type |
| **orders** | **order_id** PK, customer_id FK→customers, employee_id FK→employees, order_date, required_date, shipped_date, ship_via, freight, ship_name, ship_address, ship_city, ship_region_id FK→regions, ship_postal_code, order_status |
| **order_items** | **order_item_id** PK, order_id FK→orders, product_id FK→products, unit_price, quantity, discount, UQ(order_id, product_id) |
| product_price_history | **history_id** PK, product_id FK→products, old_price, new_price, changed_by, changed_at |
| users *(рівень 3)* | **user_id** PK, username UQ, password_hash, email UQ, role, is_active, created_at |
| activity_log *(рівень 3)* | **log_id** PK, user_id FK→users, username, action, table_name, record_id, details JSONB, created_at |

## Зв'язки
- categories 1:N products; suppliers 1:N products
- customers 1:N orders; employees 1:N orders
- orders 1:N order_items; products 1:N order_items → зв'язок **orders M:N products** розв'язано таблицею `order_items`
- employees 1:N employees (ієрархія `reports_to`)
- regions 1:N customers / suppliers / employees / orders (адреса доставки)

## Перевірка нормальних форм
- **1НФ.** Усі атрибути атомарні, повторюваних груп немає (позиції замовлення — окрема таблиця, а не «товар1, товар2…»).
- **2НФ.** Складених первинних ключів немає (сурогатні `SERIAL`); у `order_items` неключові атрибути залежать від пари (order_id, product_id), а пара додатково захищена `UNIQUE`.
- **3НФ.** Транзитивних залежностей між неключовими атрибутами немає: назви регіонів, категорій і постачальників винесено в окремі таблиці; суми замовлень **не зберігаються** (обчислюються у представленні `order_totals`), тож немає надлишковості, що може розсинхронізуватися.

### Свідомі рішення (чому це не порушення)
| Місце | Пояснення |
|---|---|
| `order_items.unit_price` | Ціна **на момент продажу** — історичний факт позиції; якщо брати її з `products`, зміна прайсу зламала б старі замовлення. |
| `orders.ship_*` | «Знімок» адреси доставки: клієнт може змінити адресу пізніше, а в замовленні має лишитись та, що була вказана. |
| `city` поряд з `region_id` | Назви міст не унікальні в межах країни, тому окрема таблиця міст не дає однозначної залежності city→region без додаткової моделі адрес (КОАТУУ/КАТОТТГ). Для навчальної БД це прийнятне спрощення. |

## Обмеження цілісності (основні)
`CHECK`: ціна ≥ 0, залишок ≥ 0, кількість > 0, знижка 0..1, статус замовлення ∈ {pending, processing, shipped, delivered, cancelled}, тип клієнта ∈ {individual, company}, юрособа має `company_name`, `required_date ≥ order_date`, `shipped_date ≥ order_date`, дата прийому > дати народження.
`UNIQUE`: email клієнтів/співробітників, назви регіонів/категорій, пара (order_id, product_id).
`FOREIGN KEY`: `ON DELETE RESTRICT` для довідників і замовлень (не можна видалити клієнта з замовленнями), `SET NULL` для необов'язкових посилань (employee_id, reports_to).
