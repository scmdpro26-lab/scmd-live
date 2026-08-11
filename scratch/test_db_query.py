import sys
import os

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db

db.init_db()
p = db.find_product_by_query("SP002")
print("FOUND:", p)
