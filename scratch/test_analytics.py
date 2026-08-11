import sys
import os
import asyncio

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.database as db
from src.web.server import get_analytics_summary, get_analytics_products, get_analytics_hourly

async def main():
    print("=== START TEST: ROI ANALYTICS ENGINE ===")
    
    # 1. Setup DB sạch
    db.init_db()
    
    # Xoá sạch dữ liệu cũ để test
    conn = db.get_db_connection()
    conn.execute("DELETE FROM orders")
    conn.execute("DELETE FROM products")
    conn.commit()
    
    # Insert các sản phẩm test kèm lượt tương tác (interactions)
    mock_products = [
        ("SP001", "Áo Thun Cotton Basic", 150000.0, 50, 10, "Áo thun", "", "", ""),
        ("SP002", "Quần Jean Slimfit", 350000.0, 25, 20, "Quần jean", "", "", ""),
        ("SP003", "Mũ Lưỡi Trai Sport", 80000.0, 100, 5, "Mũ thể thao", "", "", ""),
    ]
    conn.executemany('''
        INSERT INTO products (code, name, price, quantity, interactions, description, image_path, obs_scene, obs_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', mock_products)
    conn.commit()
    
    # Insert các đơn hàng test ở các khung giờ khác nhau
    mock_orders = [
        ("Khách A", "TikTok", "SP001", 150000.0, 2, "Chờ xác nhận", "2026-08-08 09:15:00"), # Slot 08h-10h
        ("Khách B", "Facebook", "SP002", 350000.0, 1, "Đã chốt", "2026-08-08 15:45:00"),     # Slot 14h-16h
        ("Khách C", "TikTok", "SP001", 150000.0, 1, "Đã giao", "2026-08-08 09:30:00"),     # Slot 08h-10h
        ("Khách D", "YouTube", "SP003", 80000.0, 3, "Chờ xác nhận", "2026-08-08 21:05:00"),  # Slot 20h-22h
    ]
    conn.executemany('''
        INSERT INTO orders (customer_name, platform, product_code, price, quantity, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', mock_orders)
    conn.commit()
    conn.close()
    
    print("Database đã chuẩn bị dữ liệu test ROI thành công.")

    # 2. KIỂM TRA API SUMMARY
    print("\n--- 2. KIỂM TRA SUMMARY API ---")
    summary = await get_analytics_summary()
    print(f"Summary Response: {summary}")
    
    assert summary["total_orders"] == 4, "Lỗi: Tổng số đơn hàng không khớp!"
    # Tổng doanh thu: (150k*2) + 350k + 150k + (80k*3) = 300k + 350k + 150k + 240k = 1,040,000
    assert summary["total_revenue"] == 1040000.0, "Lỗi: Tổng doanh thu không khớp!"
    assert summary["total_interactions"] == 35, "Lỗi: Tổng lượt tương tác không khớp!"
    # Overall CR = 4 / 35 = 11.43%
    assert summary["overall_cr"] == 11.43, f"Lỗi: CR chung không khớp! Nhận: {summary['overall_cr']}"
    assert summary["best_seller"]["code"] in ["SP001", "SP003"], "Lỗi: Sản phẩm bán chạy nhất không khớp!"
    print("✅ Summary API xác thực thành công 100%!")

    # 3. KIỂM TRA API PRODUCTS ROI
    print("\n--- 3. KIỂM TRA PRODUCTS ROI API ---")
    products_roi = await get_analytics_products()
    print("Products ROI Response:")
    for p in products_roi:
        print(f"- {p['code']} ({p['name']}): Doanh thu {p['revenue']:.0f}đ, Bán {p['sold']} cái, Tương tác {p['interactions']} lượt, CR {p['conversion_rate']}%")
        
        if p["code"] == "SP001":
            assert p["revenue"] == 450000.0, "Lỗi doanh thu SP001!"
            assert p["sold"] == 3, "Lỗi số lượng bán SP001!"
            # CR = (3 * 100.0) / 10 = 30.00%
            assert p["conversion_rate"] == 30.0, f"Lỗi CR SP001! Nhận: {p['conversion_rate']}"
            
        elif p["code"] == "SP002":
            assert p["revenue"] == 350000.0, "Lỗi doanh thu SP002!"
            assert p["sold"] == 1, "Lỗi số lượng bán SP002!"
            # CR = (1 * 100.0) / 20 = 5.00%
            assert p["conversion_rate"] == 5.0, "Lỗi CR SP002!"
            
        elif p["code"] == "SP003":
            assert p["revenue"] == 240000.0, "Lỗi doanh thu SP003!"
            assert p["sold"] == 3, "Lỗi số lượng bán SP003!"
            # CR = (3 * 100.0) / 5 = 60.00%
            assert p["conversion_rate"] == 60.0, "Lỗi CR SP003!"
            
    print("✅ Products ROI API xác thực thành công 100%!")

    # 4. KIỂM TRA API HOURLY
    print("\n--- 4. KIỂM TRA HOURLY API ---")
    hourly = await get_analytics_hourly()
    print("Hourly Response:")
    
    found_slots = 0
    for h in hourly:
        if h["revenue"] > 0:
            print(f"- Khung giờ {h['hour_slot']}: {h['orders']} đơn, Doanh thu {h['revenue']:.0f}đ")
            found_slots += 1
            if h["hour_slot"] == "08h - 10h":
                assert h["orders"] == 2, "Lỗi số đơn slot 08h-10h!"
                assert h["revenue"] == 450000.0, "Lỗi doanh thu slot 08h-10h!"
            elif h["hour_slot"] == "14h - 16h":
                assert h["orders"] == 1, "Lỗi số đơn slot 14h-16h!"
                assert h["revenue"] == 350000.0, "Lỗi doanh thu slot 14h-16h!"
            elif h["hour_slot"] == "20h - 22h":
                assert h["orders"] == 1, "Lỗi số đơn slot 20h-22h!"
                assert h["revenue"] == 240000.0, "Lỗi doanh thu slot 20h-22h!"
                
    assert found_slots == 3, f"Lỗi: Số lượng slot giờ có doanh thu không khớp! Nhận: {found_slots}"
    print("✅ Hourly API xác thực thành công 100%!")

    print("\n✅ KẾT QUẢ: Hệ thống Dashboard ROI theo sản phẩm & khung giờ hoạt động hoàn hảo 100%!")

if __name__ == "__main__":
    asyncio.run(main())
