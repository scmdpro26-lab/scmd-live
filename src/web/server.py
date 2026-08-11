import os
import asyncio
import logging
import threading
import uvicorn
import hmac
import hashlib
from dotenv import load_dotenv
load_dotenv() # Load environment variables early

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse
from typing import List, Dict, Any
from pydantic import BaseModel
from PySide6.QtCore import QMetaObject, Qt
from src.event_broker import global_broker
from ai_live.integrations.vnyan.exceptions import CapabilityUnavailable
from src.action_engine import ActionSource

logger = logging.getLogger("WebServer")


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Live Studio Control Panel")

# Khởi tạo CORS Middleware để bảo vệ ứng dụng chéo nguồn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bắt buộc phải có WEB_TOKEN trong cấu hình để đảm bảo an toàn cho Web Console
WEB_TOKEN = os.getenv("WEB_TOKEN")
if not WEB_TOKEN:
    logger.critical("Mã WEB_TOKEN chưa được cấu hình trong file .env! Ứng dụng dừng khởi động để bảo mật.")
    raise RuntimeError("WEB_TOKEN is not configured in .env")

# Cấu hình FB_APP_SECRET cho Facebook Webhook (không dùng fallback mặc định)
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
if not FB_APP_SECRET:
    logger.warning("FB_APP_SECRET chưa được cấu hình trong file .env. Các webhook Facebook POST sẽ bị từ chối.")

# Khởi tạo FB_VERIFY_TOKEN động hoặc từ cấu hình
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")
if not FB_VERIFY_TOKEN:
    import secrets
    FB_VERIFY_TOKEN = secrets.token_hex(16)
    logger.warning("==================================================")
    logger.warning("CẢNH BÁO: Không tìm thấy biến môi trường FB_VERIFY_TOKEN!")
    logger.warning("Đã tự động tạo mã FB_VERIFY_TOKEN ngẫu nhiên để bảo mật.")
    logger.warning("==================================================")

async def verify_api_token(authorization: str = Header(None), token: str = Query(None)):
    """Xác thực Token bảo mật cho các REST API quan trọng."""
    req_token = None
    if authorization and authorization.startswith("Bearer "):
        req_token = authorization.split(" ")[1]
    elif token:
        req_token = token
        
    if req_token != WEB_TOKEN:
        logger.warning(f"Từ chối truy cập REST API trái phép! (Token nhận được: {req_token})")
        raise HTTPException(status_code=401, detail="Unauthorized API access")

# State sharing
shared_state = {
    "mainwindow": None,  # Reference to PySide6 MainWindow
    "logs": [],          # Log history
    "live_events": []    # Livestream activity feed
}


# Autopilot mode level and pending approvals
autopilot_level = 3
pending_approvals = []
pending_lock = threading.Lock()

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def get_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            headers = {
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "Content-Security-Policy": (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                    "style-src 'self' 'unsafe-inline'; "
                    "connect-src 'self' ws: wss: https://cdn.jsdelivr.net; "
                    "img-src 'self' data:;"
                )
            }
            return HTMLResponse(content=f.read(), headers=headers)
    return HTMLResponse("<h3>Web Static Files are loading... Please refresh.</h3>")

@app.get("/webhook/facebook", response_class=PlainTextResponse)
async def verify_facebook_webhook(
    mode: str = Query(None, alias="hub.mode"),
    challenge: str = Query(None, alias="hub.challenge"),
    verify_token: str = Query(None, alias="hub.verify_token")
):
    expected_verify_token = FB_VERIFY_TOKEN
    if mode == "subscribe" and verify_token == expected_verify_token:
        logger.info("Facebook Webhook verified successfully.")
        return challenge
    logger.warning(f"Facebook Webhook verification failed. Received token: {verify_token}")
    return "Verification failed"

@app.post("/webhook/facebook")
async def receive_facebook_webhook(request: Request):
    # 1. Đọc signature từ header
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        logger.warning("Facebook Webhook thiếu X-Hub-Signature-256 header!")
        raise HTTPException(status_code=401, detail="Missing signature")
        
    # 2. Đọc raw body bytes
    body = await request.body()
    
    # 3. Tính toán chữ ký mong muốn dùng FB_APP_SECRET
    app_secret = FB_APP_SECRET
    if not app_secret:
        logger.error("Facebook Webhook POST failed: FB_APP_SECRET is not configured in .env!")
        raise HTTPException(status_code=500, detail="Facebook Webhook is not configured on this server")
        
    expected_sig = "sha256=" + hmac.new(app_secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    
    # 4. Xác thực signature an toàn
    if not hmac.compare_digest(expected_sig, signature):
        logger.warning(f"Facebook Webhook chữ ký không hợp lệ! Dự kiến: {expected_sig}, Nhận: {signature}")
        raise HTTPException(status_code=403, detail="Invalid signature")
        
    # 5. Phân tích cú pháp JSON
    try:
        import json
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON data")

    mw = shared_state["mainwindow"]
    if not mw:
        return {"status": "error", "message": "MainWindow not initialized"}
        
    if not mw.facebook_conn.is_running:
        return {"status": "ignored", "message": "Facebook Connector is not running"}

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "feed":
                    val = change.get("value", {})
                    item = val.get("item")
                    verb = val.get("verb")
                    if item == "comment" and verb == "add":
                        username = val.get("from", {}).get("name", "Người dùng Facebook")
                        comment = val.get("message", "")
                        if comment:
                            await mw.facebook_conn.handle_webhook_comment(username, comment)
    return {"status": "ok"}

active_websockets: List[WebSocket] = []

def get_current_system_state() -> Dict[str, Any]:
    """Lấy trạng thái thực tế hiện tại của hệ thống từ MainWindow."""
    mw = shared_state["mainwindow"]
    if not mw:
        return {"status": "loading"}
        
    queue_sizes = mw.queue_processor.get_queue_sizes()
    products = []
    orders = []
    try:
        import src.database as db
        products = db.get_all_products()
        orders = db.get_all_orders()
    except Exception:
        pass
        
    global autopilot_level, pending_approvals
    with pending_lock:
        serializable_pending = []
        for item in pending_approvals:
            # Matched product might contain raw database row or be dict, convert securely
            prod = item.get("matched_product")
            safe_prod = dict(prod) if prod else None
            
            safe_item = {
                "id": item.get("id"),
                "username": item.get("username"),
                "comment": item.get("comment"),
                "platform": item.get("platform"),
                "answer": item.get("answer"),
                "is_checkout": item.get("is_checkout", False),
                "order_success": item.get("order_success", False),
                "order_error_reason": item.get("order_error_reason", ""),
                "matched_product": safe_prod
            }
            serializable_pending.append(safe_item)
        
    from src.tiktok_shop import global_tiktok_shop
    return {
        "obs_connected": mw.obs.is_connected,
        "obs_host": mw.obs.host,
        "obs_port": mw.obs.port,
        "tts_is_playing": mw.tts.is_playing,
        "tts_voice": mw.tts.voice,
        "connectors": {
            "tiktok": mw.tiktok_conn.is_running,
            "facebook": mw.facebook_conn.is_running,
            "youtube": mw.youtube_conn.is_running
        },
        "queue_sizes": queue_sizes,
        "products": [dict(p) for p in products],
        "orders": [dict(o) for o in orders],
        "logs": shared_state["logs"][-30:], # Lấy 30 dòng log gần nhất
        "autopilot_level": autopilot_level,
        "pending_approvals": serializable_pending,
        "renderer_online": mw.queue_processor.vmc_client.renderer_online,
        "pinned_product_code": global_tiktok_shop.pinned_product_code,
        "live_events": shared_state["live_events"][-20:] # Lấy 20 sự kiện gần nhất
    }


async def handle_websocket_message(data: Dict[str, Any]):
    """Xử lý các gói tin nhận từ Web Dashboard (Human-in-the-loop)."""
    global autopilot_level, pending_approvals
    mw = shared_state["mainwindow"]
    if not mw:
        return
        
    action = data.get("action")
    params = data.get("params", {})
    
    logger.info(f"Nhận lệnh từ Web Dashboard: {action} - {params}")
    
    if action == "mute":
        # Dừng phát âm thanh ngay lập tức (Nút cứu sinh)
        mw.tts.stop()
        mw.signals.log_event.emit("🚨 [Web Control] Bấm dừng khẩn cấp phát giọng đọc MC!")
        
    elif action == "override":
        # Người vận hành can thiệp: Ghim chữ lên phụ đề OBS và đọc giọng nói theo ý muốn
        text = params.get("text", "").strip()
        if text:
            mw.signals.log_event.emit(f"✍️ [Web Control] Ghi đè giọng nói & Phụ đề: '{text}'")
            if mw.obs.is_connected:
                # Run in main GUI loop or thread executor
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, mw.obs.update_text_source, mw.queue_processor.subtitle_source, text)
            
            # Kích hoạt biểu cảm nói chuyện VMC và phát âm thanh
            try:
                mw.queue_processor.vmc_client.trigger_expression("happy", 1.5)
            except CapabilityUnavailable as e:
                logger.warning(f"Không thể kích hoạt biểu cảm: {e}")
                
            def tts_start():
                try:
                    mw.queue_processor.vmc_client.start_talking()
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể bắt đầu lipsync: {e}")
            def tts_stop():
                try:
                    mw.queue_processor.vmc_client.stop_talking()
                except CapabilityUnavailable as e:
                    logger.warning(f"Không thể dừng lipsync: {e}")
            mw.tts.speak(text, on_start=tts_start, on_finished=tts_stop)
            
    elif action == "send_comment":
        # Giả lập comment từ giao diện web
        username = params.get("username", "Web Admin")
        comment = params.get("comment", "")
        if comment:
            mw.signals.log_event.emit(f"💬 [Web Control] Comment giả lập: {username}: '{comment}'")
            event_data = {
                "platform": "Web",
                "username": username,
                "comment": comment
            }
            await global_broker.publish("comment_received", event_data)

    elif action == "toggle_connector":
        # Bật/tắt các connector từ xa bằng cách chuyển tiếp an toàn sang GUI Thread
        platform = params.get("platform")
        if platform == "tiktok":
            QMetaObject.invokeMethod(mw, "toggle_tiktok", Qt.QueuedConnection)
        elif platform == "facebook":
            QMetaObject.invokeMethod(mw, "toggle_facebook", Qt.QueuedConnection)
        elif platform == "youtube":
            QMetaObject.invokeMethod(mw, "toggle_youtube", Qt.QueuedConnection)
            
    elif action == "set_autopilot_level":
        level = params.get("level", 3)
        autopilot_level = level
        mw.queue_processor.autopilot_level = level
        mw.signals.log_event.emit(f"🤖 [Web Control] Thay đổi chế độ Auto-Pilot thành Level {level}")
        
    elif action == "approve_comment":
        cid = params.get("id")
        approved_text = params.get("approved_text", "")
        matched_item = None
        with pending_lock:
            for item in pending_approvals:
                if item.get("id") == cid:
                    matched_item = item
                    pending_approvals.remove(item)
                    break
        if matched_item:
            matched_item["answer"] = approved_text
            mw.signals.log_event.emit(f"✅ [Web Control] Duyệt phát bình luận của {matched_item['username']}: '{approved_text}'")
            # Thực thi comment đã duyệt trên GUI loop
            mw.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(mw.queue_processor.execute_approved_comment(matched_item))
            )
            
    elif action == "reject_comment":
        cid = params.get("id")
        matched_item = None
        with pending_lock:
            for item in pending_approvals:
                if item.get("id") == cid:
                    matched_item = item
                    pending_approvals.remove(item)
                    break
        if matched_item:
            mw.signals.log_event.emit(f"❌ [Web Control] Bỏ qua bình luận của {matched_item['username']}")

    elif action == "pin_product":
        product_code = params.get("product_code")
        if product_code:
            from src.tiktok_shop import global_tiktok_shop
            # Chạy an toàn bất đồng bộ
            asyncio.create_task(global_tiktok_shop.pin_product(product_code))

    elif action == "unpin_product":
        from src.tiktok_shop import global_tiktok_shop
        asyncio.create_task(global_tiktok_shop.unpin_product())

    elif action == "simulate_live_event":
        event_type = params.get("event_type")
        username = params.get("username", "Khách Live")
        if event_type == "gift":
            gift_name = params.get("gift_name", "Hoa hồng")
            gift_count = int(params.get("gift_count", 1))
            mw.signals.log_event.emit(f"🎁 [Web Control] Giả lập tặng quà: {username} tặng {gift_count}x {gift_name}")
            event_data = {
                "platform": "TikTok",
                "username": username,
                "gift_name": gift_name,
                "gift_count": gift_count
            }
            asyncio.create_task(global_broker.publish("gift_received", event_data))
        elif event_type == "follow":
            mw.signals.log_event.emit(f"👤 [Web Control] Giả lập follow: {username} follow shop")
            event_data = {
                "platform": "TikTok",
                "username": username
            }
            asyncio.create_task(global_broker.publish("follow_received", event_data))
        elif event_type == "share":
            mw.signals.log_event.emit(f"🔗 [Web Control] Giả lập chia sẻ: {username} chia sẻ live")
            event_data = {
                "platform": "TikTok",
                "username": username
            }
            asyncio.create_task(global_broker.publish("share_received", event_data))
        elif event_type == "cart_click":
            product_code = params.get("product_code", "SP001")
            mw.signals.log_event.emit(f"🛒 [Web Control] Giả lập xem giỏ hàng: {username} click xem {product_code}")
            event_data = {
                "platform": "TikTok",
                "username": username,
                "product_code": product_code
            }
            asyncio.create_task(global_broker.publish("cart_click_received", event_data))
            
    elif action == "trigger_mc_gesture":
        g_type = params.get("type")
        g_name = params.get("name")
        mw.signals.log_event.emit(f"🎭 [Web Control] Kích hoạt thủ công {g_type}: {g_name}")
        
        def safe_trigger_expression(name: str, dur: float):
            try:
                mw.queue_processor.vmc_client.trigger_expression(name, dur)
            except CapabilityUnavailable as e:
                logger.warning(f"Không thể kích hoạt biểu cảm '{name}': {e}")
            except Exception as e:
                logger.error(f"Lỗi biểu cảm '{name}': {e}", exc_info=True)

        def safe_trigger_gesture(name: str):
            try:
                vmc = mw.queue_processor.vmc_client
                # Gọi thẳng send_action_trigger và chuyển nguồn WEB để được ưu tiên cao nhất
                success = vmc.send_action_trigger(f"/VMC/Ext/Action/{name}", [], source=ActionSource.WEB)
                if success:
                    logger.info(f"[Web Control] safe_trigger_gesture '{name}' -> OK")
                else:
                    logger.warning(f"[Web Control] safe_trigger_gesture '{name}' -> BỊ TỪ CHỐI / THẤT BẠI")
            except CapabilityUnavailable as e:
                logger.warning(f"Không thể kích hoạt cử chỉ '{name}': {e}")
            except Exception as e:
                logger.error(f"Lỗi cử chỉ '{name}': {e}", exc_info=True)


        loop = asyncio.get_running_loop()
        if g_type == "expression":
            loop.run_in_executor(None, safe_trigger_expression, g_name, 3.0)
        elif g_type == "gesture":
            loop.run_in_executor(None, safe_trigger_gesture, g_name)



class OrderStatusUpdateRequest(BaseModel):
    status: str

def _update_order_status_db(order_id: int, status: str) -> bool:
    import src.database as db
    return db.update_order_status(order_id, status)

@app.post("/api/orders/{order_id}/status", dependencies=[Depends(verify_api_token)])
async def update_order_status_api(order_id: int, request: OrderStatusUpdateRequest):
    mw = shared_state["mainwindow"]
    success = await asyncio.to_thread(_update_order_status_db, order_id, request.status)
    if not success:
        return {"status": "error", "message": "Failed to update order status"}
    if mw:
        mw.signals.order_created.emit()
        mw.signals.log_event.emit(f"🛒 [Web Control] Cập nhật đơn hàng #{order_id} thành '{request.status}'")
    return {"status": "ok"}

def _get_analytics_summary_db() -> Dict[str, Any]:
    import src.database as db
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # 1. Tổng doanh thu & tổng đơn hàng
    cursor.execute("SELECT COUNT(*) as total_orders, SUM(price * quantity) as total_revenue FROM orders WHERE status = 'Chờ xác nhận' OR status = 'Đã chốt' OR status = 'Đã giao'")
    row = cursor.fetchone()
    total_orders = row['total_orders'] or 0
    total_revenue = row['total_revenue'] or 0.0
    
    # 2. Tổng số lượt tương tác (từ bảng products)
    cursor.execute("SELECT SUM(interactions) as total_interactions FROM products")
    total_interactions = cursor.fetchone()['total_interactions'] or 0
    
    # 3. Tính tỷ lệ chuyển đổi chung
    overall_cr = 0.0
    if total_interactions > 0:
        overall_cr = (total_orders * 100.0) / max(total_interactions, total_orders)
        overall_cr = min(overall_cr, 100.0)
        
    # 4. Tìm sản phẩm bán chạy nhất (best seller)
    cursor.execute('''
        SELECT product_code, products.name as product_name, SUM(orders.quantity) as sold_count
        FROM orders
        JOIN products ON orders.product_code = products.code
        GROUP BY product_code
        ORDER BY sold_count DESC
        LIMIT 1
    ''')
    best_seller_row = cursor.fetchone()
    best_seller = {
        "code": best_seller_row["product_code"],
        "name": best_seller_row["product_name"],
        "sold": best_seller_row["sold_count"]
    } if best_seller_row else {"code": "N/A", "name": "Chưa có", "sold": 0}
    
    conn.close()
    return {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "total_interactions": total_interactions,
        "overall_cr": round(overall_cr, 2),
        "best_seller": best_seller
    }

@app.get("/api/analytics/summary", dependencies=[Depends(verify_api_token)])
async def get_analytics_summary():
    """Lấy tổng hợp doanh thu, đơn hàng và tỷ lệ chuyển đổi chung."""
    try:
        data = await asyncio.to_thread(_get_analytics_summary_db)
        return data
    except Exception as e:
        logger.error(f"Lỗi api analytics summary: {e}")
        return {"error": str(e)}

def _get_analytics_products_db() -> List[Dict[str, Any]]:
    import src.database as db
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            p.code, 
            p.name, 
            p.price, 
            p.quantity as stock, 
            p.interactions,
            COALESCE(SUM(o.quantity), 0) as sold,
            COALESCE(SUM(o.price * o.quantity), 0) as revenue
        FROM products p
        LEFT JOIN orders o ON p.code = o.product_code
        GROUP BY p.code
    ''')
    rows = cursor.fetchall()
    products_roi = []
    for r in rows:
        sold = r['sold']
        interactions = r['interactions'] or 0
        cr = 0.0
        if interactions > 0:
            cr = (sold * 100.0) / max(interactions, sold)
            cr = min(cr, 100.0)
        products_roi.append({
            "code": r['code'],
            "name": r['name'],
            "price": r['price'],
            "stock": r['stock'],
            "interactions": interactions,
            "sold": sold,
            "revenue": r['revenue'],
            "conversion_rate": round(cr, 2)
        })
    conn.close()
    return products_roi

@app.get("/api/analytics/products", dependencies=[Depends(verify_api_token)])
async def get_analytics_products():
    """Thống kê ROI/Hiệu suất theo sản phẩm."""
    try:
        data = await asyncio.to_thread(_get_analytics_products_db)
        return data
    except Exception as e:
        logger.error(f"Lỗi api analytics products: {e}")
        return {"error": str(e)}

def _get_analytics_hourly_db() -> List[Dict[str, Any]]:
    import src.database as db
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT strftime('%H', created_at) as hour, COUNT(*) as orders_count, SUM(price * quantity) as revenue
        FROM orders
        GROUP BY hour
        ORDER BY hour ASC
    ''')
    rows = cursor.fetchall()
    hourly_data = []
    hour_map = {f"{i:02d}h - {(i+2)%24:02d}h": {"orders": 0, "revenue": 0.0} for i in range(0, 24, 2)}
    
    for r in rows:
        hr = int(r['hour'])
        slot_start = (hr // 2) * 2
        slot_key = f"{slot_start:02d}h - {(slot_start+2)%24:02d}h"
        hour_map[slot_key]["orders"] += r['orders_count']
        hour_map[slot_key]["revenue"] += r['revenue'] or 0.0
        
    for k, v in hour_map.items():
        hourly_data.append({
            "hour_slot": k,
            "orders": v["orders"],
            "revenue": v["revenue"]
        })
    conn.close()
    return hourly_data

@app.get("/api/analytics/hourly", dependencies=[Depends(verify_api_token)])
async def get_analytics_hourly():
    """Thống kê doanh thu theo khung giờ livestream."""
    try:
        data = await asyncio.to_thread(_get_analytics_hourly_db)
        return data
    except Exception as e:
        logger.error(f"Lỗi api analytics hourly: {e}")
        return {"error": str(e)}

class TikTokCartPinRequest(BaseModel):
    product_code: str

@app.post("/api/tiktok/cart/pin", dependencies=[Depends(verify_api_token)])
async def pin_tiktok_cart_api(request: TikTokCartPinRequest):
    from src.tiktok_shop import global_tiktok_shop
    success = await global_tiktok_shop.pin_product(request.product_code)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to pin product. Make sure code exists and is in stock.")
    return {"status": "ok"}

@app.post("/api/tiktok/cart/unpin", dependencies=[Depends(verify_api_token)])
async def unpin_tiktok_cart_api():
    from src.tiktok_shop import global_tiktok_shop
    await global_tiktok_shop.unpin_product()
    return {"status": "ok"}

@app.websocket("/ws")

async def websocket_endpoint(websocket: WebSocket, token: str = None):
    # 1. Bảo vệ chống tấn công Cross-Site WebSocket Hijacking (CSWSH)
    origin = websocket.headers.get("origin")
    if origin:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        if parsed.hostname not in ["localhost", "127.0.0.1"]:
            logger.warning(f"Từ chối kết nối WebSocket do Origin không hợp lệ: {origin}")
            await websocket.accept()
            await websocket.send_json({"error": "Forbidden Origin"})
            await websocket.close(code=4003)
            return

    # 2. Xác thực WebSocket bằng khóa bí mật (WEB_TOKEN) từ cấu hình
    if token != WEB_TOKEN:
        await websocket.accept()
        await websocket.send_json({"error": "Unauthorized"})
        await websocket.close(code=4003)
        logger.warning(f"Từ chối kết nối WebSocket không hợp lệ! (Token nhận được: {token})")
        return
        
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info("Web Dashboard kết nối qua WebSocket thành công.")
    try:
        # Gửi dữ liệu ban đầu
        initial_state = get_current_system_state()
        logger.info(f"DEBUG: Initial state payload -> {initial_state}")
        await websocket.send_json(initial_state)
        while True:
            # Đọc lệnh điều khiển
            data = await websocket.receive_json()
            await handle_websocket_message(data)
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
        logger.info("Web Dashboard đã ngắt kết nối WebSocket.")
    except Exception as e:
        logger.error(f"Lỗi WebSocket: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)

async def web_state_broadcaster():
    """Tự động broadcast trạng thái hệ thống tới tất cả Web Dashboard mỗi 1 giây."""
    while True:
        await asyncio.sleep(1.0)
        if not active_websockets:
            continue
            
        state = get_current_system_state()
        for ws in list(active_websockets):
            try:
                await ws.send_json(state)
            except Exception:
                if ws in active_websockets:
                    active_websockets.remove(ws)

async def listen_live_events(mainwindow_ref):
    """Lắng nghe các sự kiện live từ broker để cập nhật live activity feed và forward log."""
    import time
    from src.event_broker import global_broker
    gift_q = await global_broker.subscribe("gift_received")
    follow_q = await global_broker.subscribe("follow_received")
    share_q = await global_broker.subscribe("share_received")
    cart_click_q = await global_broker.subscribe("cart_click_received")
    cart_update_q = await global_broker.subscribe("tiktok_cart_updated")
    log_event_q = await global_broker.subscribe("system_log_event")
    
    try:
        while True:
            await asyncio.sleep(0.1)
            
            # Check gift
            while not gift_q.empty():
                evt = gift_q.get_nowait()
                shared_state["live_events"].append({
                    "type": "gift",
                    "username": evt["username"],
                    "details": f"đã tặng {evt['gift_count']}x {evt['gift_name']}",
                    "timestamp": time.strftime("%H:%M:%S")
                })
                
            # Check follow
            while not follow_q.empty():
                evt = follow_q.get_nowait()
                shared_state["live_events"].append({
                    "type": "follow",
                    "username": evt["username"],
                    "details": "đã follow shop",
                    "timestamp": time.strftime("%H:%M:%S")
                })
                
            # Check share
            while not share_q.empty():
                evt = share_q.get_nowait()
                shared_state["live_events"].append({
                    "type": "share",
                    "username": evt["username"],
                    "details": "đã chia sẻ livestream",
                    "timestamp": time.strftime("%H:%M:%S")
                })
                
            # Check cart click
            while not cart_click_q.empty():
                evt = cart_click_q.get_nowait()
                shared_state["live_events"].append({
                    "type": "cart_click",
                    "username": evt["username"],
                    "details": f"đã click xem sản phẩm {evt['product_code']}",
                    "timestamp": time.strftime("%H:%M:%S")
                })

            # Check cart update
            while not cart_update_q.empty():
                evt = cart_update_q.get_nowait()
                p_code = evt["pinned_product_code"]
                details_str = f"đã ghim {evt['product_name']} ({p_code})" if p_code else "đã hủy ghim giỏ hàng"
                shared_state["live_events"].append({
                    "type": "cart_update",
                    "username": "Hệ thống",
                    "details": details_str,
                    "timestamp": time.strftime("%H:%M:%S")
                })

            # Check system log event
            while not log_event_q.empty():
                log_text = log_event_q.get_nowait()
                mainwindow_ref.signals.log_event.emit(log_text)
                
            # Keep max 30 events
            if len(shared_state["live_events"]) > 30:
                shared_state["live_events"] = shared_state["live_events"][-30:]
    except asyncio.CancelledError:
        pass
    finally:
        await global_broker.unsubscribe("gift_received", gift_q)
        await global_broker.unsubscribe("follow_received", follow_q)
        await global_broker.unsubscribe("share_received", share_q)
        await global_broker.unsubscribe("cart_click_received", cart_click_q)
        await global_broker.unsubscribe("tiktok_cart_updated", cart_update_q)
        await global_broker.unsubscribe("system_log_event", log_event_q)

# Quản lý chạy Web Server bằng Thread
server_thread = None
server_instance = None

def start_api_server(mainwindow_ref, host="127.0.0.1", port=8000):
    global server_thread, server_instance
    shared_state["mainwindow"] = mainwindow_ref
    
    # 1. Nếu có server đang chạy, dừng hoàn toàn trước khi khởi chạy cái mới để tránh xung đột port
    if server_instance:
        stop_api_server()
    
    # Kết nối tín hiệu log_event của mainwindow để lưu vào danh sách log chia sẻ
    def append_log(text):
        shared_state["logs"].append(text)
        if len(shared_state["logs"]) > 100:
            shared_state["logs"].pop(0)
            
    mainwindow_ref.signals.log_event.connect(append_log)
    
    # Đồng bộ autopilot level hiện tại của server vào queue processor
    mainwindow_ref.queue_processor.autopilot_level = autopilot_level
    
    # Callback nhận pending comment từ PriorityQueueProcessor (Level 1 Autopilot)
    def on_pending_comment_received(comment_data):
        global pending_approvals
        import secrets
        comment_data["id"] = secrets.token_hex(8)
        with pending_lock:
            pending_approvals.append(comment_data)
        mainwindow_ref.signals.log_event.emit(f"📥 [Autopilot L1] Bình luận chờ duyệt từ {comment_data['username']}: '{comment_data['comment']}'")
        
    mainwindow_ref.queue_processor.on_pending_approval_callback = on_pending_comment_received

    # Hàm khởi chạy Uvicorn server
    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start broadcaster task
        loop.create_task(web_state_broadcaster())
        # Start live events listener task
        loop.create_task(listen_live_events(mainwindow_ref))

        
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        
        # Lưu thực thể server để có thể stop
        global server_instance
        server_instance = server
        
        loop.run_until_complete(server.serve())

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info(f"FastAPI Web Server khởi động tại http://{host}:{port}")

def stop_api_server():
    global server_instance, server_thread
    if server_instance:
        server_instance.should_exit = True
        logger.info("Đã gửi yêu cầu dừng FastAPI Web Server.")
        if server_thread and server_thread.is_alive():
            server_thread.join(timeout=2.0)
            server_thread = None
        server_instance = None
