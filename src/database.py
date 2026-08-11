import sqlite3
from typing import List, Dict, Any, Optional
from src.config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            price REAL DEFAULT 0.0,
            quantity INTEGER DEFAULT 0,
            interactions INTEGER DEFAULT 0,
            description TEXT,
            image_path TEXT,
            obs_scene TEXT,
            obs_source TEXT
        )
    ''')
    
    # Đảm bảo cột interactions tồn tại trong trường hợp bảng products đã được tạo từ trước
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN interactions INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    
    # Create orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            platform TEXT NOT NULL,
            product_code TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'Chờ xác nhận',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create stream_sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stream_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            responsible_person_name TEXT NOT NULL,
            id_verification_ref TEXT,
            voice_mode TEXT NOT NULL,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ended_at DATETIME
        )
    ''')
    
    # Insert some mock products if table is empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        mock_products = [
            ("SP001", "Áo Thun Cotton Basic", 150000.0, 50, "Áo thun 100% cotton co giãn 4 chiều, thoáng mát.", "", "Product_A_Scene", "Product_A_Image"),
            ("SP002", "Quần Jean Slimfit", 350000.0, 25, "Quần jean nam kiểu dáng slimfit, chất bò dày dặn co giãn nhẹ.", "", "Product_B_Scene", "Product_B_Image"),
            ("SP003", "Mũ Lưỡi Trai Sport", 80000.0, 100, "Mũ lưỡi trai phong cách thể thao năng động, chống nắng tốt.", "", "Product_C_Scene", "Product_C_Image"),
        ]
        cursor.executemany('''
            INSERT INTO products (code, name, price, quantity, description, image_path, obs_scene, obs_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', mock_products)
        conn.commit()
        
    conn.close()

def get_all_products() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    products = [dict(row) for row in rows]
    conn.close()
    return products

def find_product_by_query(query: str) -> Optional[Dict[str, Any]]:
    """Tìm kiếm sản phẩm theo mã sản phẩm hoặc tên sản phẩm."""
    if not query:
        return None
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Search by code exact match or name fuzzy match
    cursor.execute(
        "SELECT * FROM products WHERE code = ? OR name LIKE ?", 
        (query.strip(), f"%{query.strip()}%")
    )
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None

def add_product(code: str, name: str, price: float, quantity: int, description: str, 
                image_path: str = "", obs_scene: str = "", obs_source: str = "") -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (code, name, price, quantity, description, image_path, obs_scene, obs_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (code, name, price, quantity, description, image_path, obs_scene, obs_source))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def update_product(product_id: int, code: str, name: str, price: float, quantity: int, 
                   description: str, image_path: str = "", obs_scene: str = "", obs_source: str = "") -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products
            SET code = ?, name = ?, price = ?, quantity = ?, description = ?, 
                image_path = ?, obs_scene = ?, obs_source = ?
            WHERE id = ?
        ''', (code, name, price, quantity, description, image_path, obs_scene, obs_source, product_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_product(product_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def create_order(customer_name: str, platform: str, product_code: str, price: float, quantity: int = 1, status: str = 'Chờ xác nhận') -> bool:
    """Tạo đơn hàng mới và tự động trừ số lượng sản phẩm tương ứng trong tồn kho (Atomic Transaction)."""
    conn = None
    try:
        conn = get_db_connection()
        conn.isolation_level = None
        cursor = conn.cursor()
        
        # Bắt đầu transaction ghi khóa tức thì
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        
        # 1. Kiểm tra tồn kho hiện tại
        cursor.execute("SELECT quantity FROM products WHERE code = ?", (product_code,))
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            return False
            
        current_qty = row['quantity']
        if current_qty < quantity:
            conn.rollback()
            return False
            
        # 2. Tạo đơn hàng mới
        cursor.execute('''
            INSERT INTO orders (customer_name, platform, product_code, price, quantity, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (customer_name, platform, product_code, price, quantity, status))
        
        # 3. Trừ tồn kho sản phẩm
        cursor.execute('''
            UPDATE products
            SET quantity = quantity - ?
            WHERE code = ?
        ''', (quantity, product_code))
        
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        import logging
        logging.getLogger("Database").error(f"Lỗi khi tạo đơn hàng: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_all_orders() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các đơn hàng."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    rows = cursor.fetchall()
    orders = [dict(row) for row in rows]
    conn.close()
    return orders

def update_order_status(order_id: int, status: str) -> bool:
    """Cập nhật trạng thái đơn hàng."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE orders
            SET status = ?
            WHERE id = ?
        ''', (status, order_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        import logging
        logging.getLogger("Database").error(f"Lỗi khi cập nhật trạng thái đơn hàng {order_id}: {e}")
        return False

def delete_order(order_id: int) -> bool:
    """Xóa đơn hàng và hoàn trả lại số lượng sản phẩm vào tồn kho."""
    conn = None
    try:
        conn = get_db_connection()
        conn.isolation_level = None
        cursor = conn.cursor()
        
        # Bắt đầu transaction ghi khóa tức thì
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        
        # 1. Lấy thông tin đơn hàng trước khi xóa
        cursor.execute("SELECT product_code, quantity FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            return False
            
        product_code = row['product_code']
        quantity = row['quantity']
        
        # 2. Xóa đơn hàng
        cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        
        # 3. Hoàn trả tồn kho
        cursor.execute('''
            UPDATE products
            SET quantity = quantity + ?
            WHERE code = ?
        ''', (quantity, product_code))
        
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        import logging
        logging.getLogger("Database").error(f"Lỗi khi xóa đơn hàng {order_id}: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_orders_by_customer(customer_name: str) -> List[Dict[str, Any]]:
    """Lấy danh sách các đơn hàng đã chốt của một khách hàng."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE customer_name = ? ORDER BY id DESC", (customer_name.strip(),))
    rows = cursor.fetchall()
    orders = [dict(row) for row in rows]
    conn.close()
    return orders

def increment_product_interactions(code: str) -> bool:
    """Tăng số lượt tương tác/hỏi han về sản phẩm đó lên 1."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET interactions = interactions + 1 WHERE code = ?", (code.strip(),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        import logging
        logging.getLogger("Database").error(f"Lỗi khi tăng interactions cho sản phẩm {code}: {e}")
        return False

def start_stream_session(platform: str, responsible_person_name: str, id_verification_ref: str, voice_mode: str) -> int:
    """Bắt đầu một phiên livestream mới và ghi nhận danh tính người chịu trách nhiệm."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO stream_sessions (platform, responsible_person_name, id_verification_ref, voice_mode)
        VALUES (?, ?, ?, ?)
    ''', (platform, responsible_person_name, id_verification_ref, voice_mode))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def end_stream_session(session_id: int):
    """Kết thúc phiên livestream."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE stream_sessions
        SET ended_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (session_id,))
    conn.commit()
    conn.close()

