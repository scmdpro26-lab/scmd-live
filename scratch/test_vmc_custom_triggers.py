import sys
import os
import urllib.request
import json
import asyncio
from unittest.mock import MagicMock, patch

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vmc_client import VMCClient

async def main():
    print("=== START TEST: CUSTOM VMC REST ACTION TRIGGERS ===")
    
    vmc = VMCClient()
    
    # Capture sent requests
    sent_requests = []
    
    def mock_urlopen(req, timeout=None):
        url = req.full_url
        data = req.data
        method = req.get_method()
        
        payload = json.loads(data.decode("utf-8"))
        sent_requests.append((url, method, payload))
        print(f"[Mock REST] Request: {method} {url} -> {payload}")
        
        # Return a dummy response object
        response = MagicMock()
        response.__enter__.return_value.status = 200
        return response
        
    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        print("\n1. Gửi sự kiện: CheckoutSuccess cho sản phẩm 'Áo Thun Cotton Basic'")
        vmc.trigger_checkout_success("Áo Thun Cotton Basic")
        
        print("\n2. Gửi sự kiện: MinigameStart (Minigame bắt đầu)")
        vmc.trigger_minigame_start()
        
        print("\n3. Gửi sự kiện: VoucherDrop (Tung voucher giảm giá)")
        vmc.trigger_voucher_drop()
        
        print("\n4. Gửi sự kiện: Apology (Cúi đầu xin lỗi khách hàng)")
        vmc.trigger_apology(duration=3.0)
        
        # Chờ một lúc nhỏ vì các hàm send_action_trigger chạy trong một Thread phụ bất đồng bộ
        await asyncio.sleep(0.5)

    # Assertions
    actions_sent = [req[2]["action"] for req in sent_requests]
    print(f"Actions sent: {actions_sent}")
    assert "CheckoutSuccess" in actions_sent, "CheckoutSuccess action missing"
    assert "MinigameStart" in actions_sent, "MinigameStart action missing"
    assert "VoucherDrop" in actions_sent, "VoucherDrop action missing"
    assert "Apology" in actions_sent, "Apology action missing"
    
    # Kiểm tra payload chốt đơn
    checkout_req = [req for req in sent_requests if req[2]["action"] == "CheckoutSuccess"][0]
    assert checkout_req[2]["payload"]["text1"] == "Áo Thun Cotton Basic"
    
    print("\n✅ KẾT QUẢ: Toàn bộ Custom REST triggers hoạt động bình thường, HTTP POST JSON đã gửi đi!")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
