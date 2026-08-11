import sys
import os
import asyncio

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.event_broker import global_broker

async def main():
    print("=== TEST EVENT BROKER ===")
    
    # 1. Đăng ký nhận sự kiện
    queue1 = await global_broker.subscribe("comment_received")
    queue2 = await global_broker.subscribe("comment_received")
    queue3 = await global_broker.subscribe("obs_command")
    
    received_comment1 = []
    received_comment2 = []
    received_obs = []

    # 2. Định nghĩa hàm xử lý bất đồng bộ cho subscriber
    async def worker(name, q, target_list):
        try:
            while True:
                data = await q.get()
                print(f"Worker [{name}] nhận được: {data}")
                target_list.append(data)
        except asyncio.CancelledError:
            pass

    task1 = asyncio.create_task(worker("Subscriber Comment 1", queue1, received_comment1))
    task2 = asyncio.create_task(worker("Subscriber Comment 2", queue2, received_comment2))
    task3 = asyncio.create_task(worker("Subscriber OBS", queue3, received_obs))
    
    await asyncio.sleep(0.5)
    
    # 3. Publish sự kiện
    print("\n[Publishing comment_received]")
    await global_broker.publish("comment_received", {"username": "Khach_A", "comment": "Hi shop!"})
    
    await asyncio.sleep(0.5)
    
    print("\n[Publishing obs_command]")
    await global_broker.publish("obs_command", {"action": "switch_scene", "scene": "Product_Scene"})
    
    await asyncio.sleep(0.5)
    
    # Hủy đăng ký và dọn dẹp
    print("\n[Cleaning up]")
    task1.cancel()
    task2.cancel()
    task3.cancel()
    await asyncio.gather(task1, task2, task3, return_exceptions=True)
    
    await global_broker.unsubscribe("comment_received", queue1)
    await global_broker.unsubscribe("comment_received", queue2)
    await global_broker.unsubscribe("obs_command", queue3)
    
    # Assertions
    assert len(received_comment1) == 1, "Subscriber 1 did not receive the comment"
    assert received_comment1[0]["username"] == "Khach_A", "Incorrect subscriber 1 data"
    assert len(received_comment2) == 1, "Subscriber 2 did not receive the comment"
    assert len(received_obs) == 1, "OBS Subscriber did not receive the command"
    
    print("\n=== Hoàn thành kiểm thử Event Broker ===")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
