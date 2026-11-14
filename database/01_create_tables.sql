-- ЛР №4. БД інтернет-магазину "ТехноМарт" (PostgreSQL 17)
-- 01: створення структури (DDL)

DROP TABLE IF EXISTS activity_log CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS product_price_history CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS suppliers CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS regions CASCADE;

CREATE TABLE regions (
    region_id   SERIAL PRIMARY KEY,
    region_name VARCHAR(50) NOT NULL UNIQUE,
    region_code VARCHAR(2)  NOT NULL UNIQUE
);

CREATE TABLE suppliers (
    supplier_id   SERIAL PRIMARY KEY,
    company_name  VARCHAR(100) NOT NULL,
    contact_name  VARCHAR(50),
    contact_title VARCHAR(50),
    address       VARCHAR(100),
    city          VARCHAR(30),
    region_id     INTEGER REFERENCES regions(region_id) ON DELETE RESTRICT,
    postal_code   VARCHAR(10),
    phone         VARCHAR(20),
    email         VARCHAR(100) CHECK (email IS NULL OR email LIKE '%_@_%.__%'),
    website       VARCHAR(100)
);

CREATE TABLE categories (
    category_id   SERIAL PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL UNIQUE,
    description   TEXT,
    picture_url   VARCHAR(200)
);

CREATE TABLE products (
    product_id        SERIAL PRIMARY KEY,
    product_name      VARCHAR(100) NOT NULL,
    supplier_id       INTEGER REFERENCES suppliers(supplier_id) ON DELETE RESTRICT,
    category_id       INTEGER REFERENCES categories(category_id) ON DELETE RESTRICT,
    quantity_per_unit VARCHAR(50),
    unit_price        DECIMAL(10,2) NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    units_in_stock    INTEGER NOT NULL DEFAULT 0 CHECK (units_in_stock >= 0),
    units_on_order    INTEGER NOT NULL DEFAULT 0 CHECK (units_on_order >= 0),
    reorder_level     INTEGER NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
    discontinued      BOOLEAN NOT NULL DEFAULT false,
    description       TEXT,
    picture_url       VARCHAR(200)
);

CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    last_name   VARCHAR(50) NOT NULL,
    first_name  VARCHAR(50) NOT NULL,
    middle_name VARCHAR(50),
    title       VARCHAR(50),
    birth_date  DATE,
    hire_date   DATE,
    address     VARCHAR(100),
    city        VARCHAR(30),
    region_id   INTEGER REFERENCES regions(region_id) ON DELETE RESTRICT,
    postal_code VARCHAR(10),
    phone       VARCHAR(20),
    email       VARCHAR(100) UNIQUE,
    salary      DECIMAL(10,2) CHECK (salary IS NULL OR salary >= 0),
    reports_to  INTEGER REFERENCES employees(employee_id) ON DELETE SET NULL,
    CHECK (hire_date IS NULL OR birth_date IS NULL OR hire_date > birth_date)
);

CREATE TABLE customers (
    customer_id       SERIAL PRIMARY KEY,
    company_name      VARCHAR(100),
    contact_name      VARCHAR(50) NOT NULL,
    contact_title     VARCHAR(50),
    address           VARCHAR(100),
    city              VARCHAR(30),
    region_id         INTEGER REFERENCES regions(region_id) ON DELETE RESTRICT,
    postal_code       VARCHAR(10),
    phone             VARCHAR(20),
    email             VARCHAR(100) UNIQUE,
    registration_date DATE NOT NULL DEFAULT CURRENT_DATE,
    customer_type     VARCHAR(20) NOT NULL DEFAULT 'individual'
        CHECK (customer_type IN ('individual', 'company')),
    CHECK (customer_type = 'individual' OR company_name IS NOT NULL)
);

CREATE TABLE orders (
    order_id         SERIAL PRIMARY KEY,
    customer_id      INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
    employee_id      INTEGER REFERENCES employees(employee_id) ON DELETE SET NULL,
    order_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    required_date    DATE,
    shipped_date     DATE,
    ship_via         VARCHAR(50),
    freight          DECIMAL(8,2) NOT NULL DEFAULT 0 CHECK (freight >= 0),
    -- адреса доставки зберігається як "знімок" на момент замовлення
    ship_name        VARCHAR(100),
    ship_address     VARCHAR(100),
    ship_city        VARCHAR(30),
    ship_region_id   INTEGER REFERENCES regions(region_id) ON DELETE RESTRICT,
    ship_postal_code VARCHAR(10),
    order_status     VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (order_status IN ('pending','processing','shipped','delivered','cancelled')),
    CHECK (required_date IS NULL OR required_date >= order_date),
    CHECK (shipped_date  IS NULL OR shipped_date  >= order_date)
);

CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id)     ON DELETE RESTRICT,
    product_id    INTEGER NOT NULL REFERENCES products(product_id) ON DELETE RESTRICT,
    unit_price    DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),  -- ціна на момент продажу
    quantity      INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    discount      DECIMAL(4,2) NOT NULL DEFAULT 0 CHECK (discount >= 0 AND discount <= 1),
    UNIQUE (order_id, product_id)
);

-- Історія зміни цін (заповнюється тригером)
CREATE TABLE product_price_history (
    history_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    old_price  DECIMAL(10,2) NOT NULL,
    new_price  DECIMAL(10,2) NOT NULL,
    changed_by VARCHAR(50) NOT NULL DEFAULT current_user,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE regions     IS 'Регіони України';
COMMENT ON TABLE suppliers   IS 'Постачальники товарів';
COMMENT ON TABLE categories  IS 'Категорії товарів';
COMMENT ON TABLE products    IS 'Каталог товарів';
COMMENT ON TABLE employees   IS 'Співробітники компанії';
COMMENT ON TABLE customers   IS 'Клієнти (фізичні та юридичні особи)';
COMMENT ON TABLE orders      IS 'Замовлення клієнтів';
COMMENT ON TABLE order_items IS 'Позиції замовлень';
COMMENT ON TABLE product_price_history IS 'Аудит зміни цін товарів';
