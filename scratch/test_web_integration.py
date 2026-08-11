import asyncio
import json
import websockets
import urllib.request

TOKEN = "autolive_console_secret_token"
WS_URL = f"ws://127.0.0.1:8000/ws?token={TOKEN}"
API_URL = "http://127.0.0.1:8000/api/analytics/summary"

async def test_integration():
    print("=== BẮT ĐẦU KIỂM THỬ TÍCH HỢP WEB CONSOLE ===")
    
    # 1. Test REST API with Token
    print("\n--- 1. Kiểm tra REST API Analytics ---")
    req = urllib.request.Request(API_URL)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            print(f"✅ Kết nối REST API thành công! Doanh thu: {res_data.get('total_revenue')}đ")
    except Exception as e:
        print(f"❌ Lỗi REST API: {e}")
        return

    # 2. Test WebSocket connection and actions
    print("\n--- 2. Kết nối WebSocket ---")
    try:
        async with websockets.connect(WS_URL) as ws:
            # Nhận state ban đầu
            init_state = await ws.recv()
            state = json.loads(init_state)
            print("✅ Kết nối WebSocket thành công! Nhận state ban đầu:")
            print(f"   - OBS Connected: {state.get('obs_connected')}")
            print(f"   - Autopilot Level: {state.get('autopilot_level')}")
            
            # Gửi hành động comment giả lập (send_comment)
            print("\n--- 3. Gửi comment giả lập từ Web ---")
            comment_payload = {
                "action": "send_comment",
                "params": {
                    "username": "Web Tester Pro",
                    "comment": "áo thun SP001 bao nhiêu shop ơi?"
                }
            }
            await ws.send(json.dumps(comment_payload))
            print("✅ Đã gửi lệnh comment giả lập.")
            
            # Gửi hành động override giọng nói (override)
            print("\n--- 4. Gửi lệnh ghi đè giọng nói khẩn cấp ---")
            override_payload = {
                "action": "override",
                "params": {
                    "text": "Kiểm tra kết nối âm thanh từ xa"
                }
            }
            await ws.send(json.dumps(override_payload))
            print("✅ Đã gửi lệnh override giọng nói.")
            
            # Gửi hành động đổi Autopilot level
            print("\n--- 5. Thay đổi Autopilot Level ---")
            level_payload = {
                "action": "set_autopilot_level",
                "params": {
                    "level": 1
                }
            }
            await ws.send(json.dumps(level_payload))
            print("✅ Đã gửi lệnh đổi Autopilot level sang L1.")

            # Nhận state cập nhật
            await asyncio.sleep(0.5)
    except Exception as e:
        print(f"❌ Lỗi WebSocket: {e}")
        return
        
    print("\n🎉 KIỂM THỬ HOÀN TẤT THÀNH CÔNG!")

if __name__ == "__main__":
    asyncio.run(test_integration())
