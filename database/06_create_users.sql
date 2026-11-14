-- 06: користувачі застосунку та ролі (рівень 3)
-- Паролі зберігаються як bcrypt-хеші (pgcrypto), а не відкритим текстом.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE CHECK (length(username) >= 3),
    password_hash VARCHAR(255) NOT NULL,
    email         VARCHAR(100) NOT NULL UNIQUE,
    role          VARCHAR(20)  NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin', 'manager', 'viewer')),
    is_active     BOOLEAN      NOT NULL DEFAULT true,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE users IS 'Користувачі вебзастосунку (admin - все, manager - CRUD, viewer - перегляд)';

CREATE OR REPLACE FUNCTION register_user(p_username VARCHAR, p_password VARCHAR, p_email VARCHAR,
                                         p_role VARCHAR DEFAULT 'viewer') RETURNS INT AS $$
DECLARE v_id INT;
BEGIN
    IF length(p_password) < 6 THEN
        RAISE EXCEPTION 'Пароль має містити щонайменше 6 символів';
    END IF;
    INSERT INTO users (username, password_hash, email, role)
    VALUES (p_username, crypt(p_password, gen_salt('bf')), p_email, p_role)
    RETURNING user_id INTO v_id;
    RETURN v_id;
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'Користувач з таким іменем або email вже існує';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION authenticate_user(p_username VARCHAR, p_password VARCHAR)
RETURNS TABLE(user_id INT, username VARCHAR, role VARCHAR) AS $$
    SELECT u.user_id, u.username, u.role FROM users u
    WHERE u.username = p_username AND u.is_active AND u.password_hash = crypt(p_password, u.password_hash);
$$ LANGUAGE sql STABLE;

-- Демо-акаунти (ЗМІНІТЬ паролі перед реальним використанням!)
SELECT register_user('admin',   'admin123',   'admin@technomart.ua',   'admin');
SELECT register_user('manager', 'manager123', 'manager@technomart.ua', 'manager');
SELECT register_user('viewer',  'viewer123',  'viewer@technomart.ua',  'viewer');
