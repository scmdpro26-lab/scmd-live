import os
import asyncio
import threading
from PySide6.QtCore import Qt, QObject, Signal, Slot, QTimer, QThread
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout,
    QComboBox, QMessageBox, QCheckBox, QFileDialog, QProgressBar,
    QGridLayout
)
from PySide6.QtGui import QIcon, QFont

from src.config import Config
import src.database as db
from src.obs_client import OBSClient
from src.ai_brain import AIBrain
from src.tts_engine import TTSEngine
from src.event_broker import global_broker
from src.connectors.tiktok import TikTokConnector
from src.connectors.facebook import FacebookConnector
from src.connectors.youtube import YoutubeConnector
from src.priority_queue import PriorityQueueProcessor
from src.ai_director import AIDirector

class AppSignals(QObject):
    log_event = Signal(str)
    ai_response_ready = Signal(str, str, str)   # username, comment, answer
    tts_status = Signal(str, bool)              # status text, is_playing
    queue_updated = Signal(dict)                # dict of sizes: {"high": h, "medium": m, "low": l}
    connector_status = Signal(str, bool)        # connector name, is_running
    order_created = Signal()                    # Signal refresh products & orders data
    new_teleprompter_line = Signal(str)         # Signal new line for teleprompter tab

def run_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

class VnyanSetupWorker(QThread):
    progress_signal = Signal(int, str, str, str) # step_num, step_name, status, detail
    finished_signal = Signal(object) # SetupResult

    def __init__(self, service, vnyan_path, avatar_path):
        super().__init__()
        self.service = service
        self.vnyan_path = vnyan_path
        self.avatar_path = avatar_path

    def run(self):
        def on_progress(step, desc, status, detail=""):
            self.progress_signal.emit(step, desc, status, detail)
        try:
            result = self.service.run_setup(self.vnyan_path, self.avatar_path, on_progress=on_progress)
            self.finished_signal.emit(result)
        except Exception as e:
            from ai_live.integrations.vnyan.models import SetupResult, VNyanHealth
            self.finished_signal.emit(SetupResult(False, "FAILED", None, VNyanHealth(), [], [], [str(e)], False))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Live Studio - Complete Production Core")
        self.resize(1150, 800)
        self.setup_worker = None

        # Initialize engines
        self.obs = OBSClient(Config.OBS_HOST, Config.OBS_PORT, Config.OBS_PASSWORD)
        self.ai = AIBrain()
        self.tts = TTSEngine()
        self.signals = AppSignals()

        # Connectors & Processors
        self.tiktok_conn = TikTokConnector()
        self.facebook_conn = FacebookConnector()
        self.youtube_conn = YoutubeConnector()
        
        # Initialize Event Loop in a separate thread
        self.loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=run_async_loop, args=(self.loop,), daemon=True)
        self.async_thread.start()

        # Instantiate Priority Queue Processor
        self.queue_processor = PriorityQueueProcessor(
            ai_brain=self.ai,
            tts_engine=self.tts,
            obs_client=self.obs,
            on_queue_change_callback=self.on_queue_changed,
            app_signals=self.signals
        )
        self.queue_processor.on_ai_response_callback = self.on_ai_response
        self.queue_processor.teleprompter.on_new_line_callback = lambda line: self.signals.new_teleprompter_line.emit(line)

        # Instantiate AI Director
        self.director = AIDirector(
            obs_client=self.obs,
            ai_brain=self.ai,
            tts_engine=self.tts,
            timeline_path="timeline.json"
        )
        self.web_server_running = False

        # Connect QT Signals
        self.signals.log_event.connect(self.add_log)
        self.signals.ai_response_ready.connect(self.on_ai_response_ready)
        self.signals.tts_status.connect(self.on_tts_status)
        self.signals.queue_updated.connect(self.update_queue_ui)
        self.signals.connector_status.connect(self.update_connector_ui)
        self.signals.order_created.connect(self.on_order_created)
        self.signals.new_teleprompter_line.connect(self.on_new_teleprompter_line)

        # Load QSS stylesheet
        self.load_stylesheet()

        # Build UI
        self.setup_ui()
        
        # Load products & orders from Database
        self.load_products()
        self.load_orders()

        # Start Core Async tasks
        self.start_core_tasks()

        # QTimer cập nhật trạng thái Renderer
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_renderer_status_ui)
        self.status_timer.start(2000)

        # Tự động khởi chạy Web Server khi mở ứng dụng để người dùng vào được ngay
        self.toggle_web_server()

        # Log system status
        self.signals.log_event.emit("=== AI Live Studio v3.0 (Full Roadmap) Khởi động ===")
        if self.ai.api_configured:
            self.signals.log_event.emit("Hệ thống: Gemini API hoạt động.")
        else:
            self.signals.log_event.emit("Hệ thống: Gemini API chưa cấu hình. Đang chạy ở chế độ giả lập offline.")

    def load_stylesheet(self):
        qss_path = os.path.join(os.path.dirname(__file__), "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Header Title and Status Row
        header_layout = QHBoxLayout()
        title_label = QLabel("🎭 AI Live Studio (Full Production Suite)")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title_label.setStyleSheet("color: #89b4fa; margin-bottom: 5px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.lbl_gemini_status = QLabel("Gemini: Offline Mode")
        self.lbl_gemini_status.setStyleSheet("color: #f38ba8; font-weight: bold; padding: 4px 8px; border: 1px solid #f38ba8; border-radius: 5px;")
        if self.ai.api_configured:
            self.lbl_gemini_status.setText("Gemini: Connected")
            self.lbl_gemini_status.setStyleSheet("color: #a6e3a1; font-weight: bold; padding: 4px 8px; border: 1px solid #a6e3a1; border-radius: 5px;")
        header_layout.addWidget(self.lbl_gemini_status)

        self.lbl_obs_status = QLabel("OBS: Disconnected")
        self.lbl_obs_status.setStyleSheet("color: #f38ba8; font-weight: bold; padding: 4px 8px; border: 1px solid #f38ba8; border-radius: 5px;")
        header_layout.addWidget(self.lbl_obs_status)

        main_layout.addLayout(header_layout)

        # Tab Widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_dashboard = QWidget()
        self.tab_products = QWidget()
        self.tab_orders = QWidget()
        self.tab_teleprompter = QWidget()
        self.tab_logs = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_dashboard, "🚀 Bảng Điều Khiển")
        self.tabs.addTab(self.tab_products, "📦 Quản Lý Sản Phẩm")
        self.tabs.addTab(self.tab_orders, "🛒 Quản Lý Đơn Hàng")
        self.tabs.addTab(self.tab_teleprompter, "🎤 Teleprompter")
        self.tabs.addTab(self.tab_logs, "📊 Nhật Ký Hệ Thống")
        self.tabs.addTab(self.tab_settings, "⚙️ Cài Đặt Hệ Thống")

        self.setup_dashboard_tab()
        self.setup_products_tab()
        self.setup_orders_tab()
        self.setup_teleprompter_tab()
        self.setup_logs_tab()
        self.setup_settings_tab()

    # ==================== TAB 1: DASHBOARD ====================
    def setup_dashboard_tab(self):
        layout = QHBoxLayout(self.tab_dashboard)

        # Left Column: Connectors & Services
        left_layout = QVBoxLayout()
        
        # 1. Web Control & AI Director Box
        group_web_dir = QGroupBox("Quản lý Web Server & Đạo Diễn AI")
        web_dir_layout = QVBoxLayout(group_web_dir)
        
        web_row = QHBoxLayout()
        self.lbl_web_status = QLabel("Web Server: Offline")
        self.lbl_web_status.setStyleSheet("color: #a6adc8; font-weight: bold;")
        self.btn_web_toggle = QPushButton("Chạy Web Server")
        self.btn_web_toggle.setObjectName("successBtn")
        self.btn_web_toggle.clicked.connect(self.toggle_web_server)
        web_row.addWidget(self.lbl_web_status)
        web_row.addWidget(self.btn_web_toggle)
        web_dir_layout.addLayout(web_row)
        
        dir_row = QHBoxLayout()
        self.lbl_dir_status = QLabel("Đạo Diễn AI: Tắt")
        self.lbl_dir_status.setStyleSheet("color: #a6adc8; font-weight: bold;")
        self.btn_dir_toggle = QPushButton("Bật Đạo Diễn")
        self.btn_dir_toggle.setObjectName("successBtn")
        self.btn_dir_toggle.clicked.connect(self.toggle_ai_director)
        dir_row.addWidget(self.lbl_dir_status)
        dir_row.addWidget(self.btn_dir_toggle)
        web_dir_layout.addLayout(dir_row)
        
        left_layout.addWidget(group_web_dir)

        # 2. Connectors Box
        group_connectors = QGroupBox("Quản lý nguồn Livestream (Connectors)")
        conn_layout = QVBoxLayout(group_connectors)
        
        tiktok_row = QHBoxLayout()
        self.lbl_tiktok_status = QLabel("TikTok: Offline")
        self.lbl_tiktok_status.setStyleSheet("color: #a6adc8; font-weight: bold;")
        self.btn_tiktok_toggle = QPushButton("Bật Mock Live")
        self.btn_tiktok_toggle.setObjectName("secondaryBtn")
        self.btn_tiktok_toggle.clicked.connect(self.toggle_tiktok)
        tiktok_row.addWidget(self.lbl_tiktok_status)
        tiktok_row.addWidget(self.btn_tiktok_toggle)
        conn_layout.addLayout(tiktok_row)

        facebook_row = QHBoxLayout()
        self.lbl_facebook_status = QLabel("Facebook: Offline")
        self.lbl_facebook_status.setStyleSheet("color: #a6adc8; font-weight: bold;")
        self.btn_facebook_toggle = QPushButton("Bật Mock Live")
        self.btn_facebook_toggle.setObjectName("secondaryBtn")
        self.btn_facebook_toggle.clicked.connect(self.toggle_facebook)
        facebook_row.addWidget(self.lbl_facebook_status)
        facebook_row.addWidget(self.btn_facebook_toggle)
        conn_layout.addLayout(facebook_row)

        youtube_row = QHBoxLayout()
        self.lbl_youtube_status = QLabel("YouTube: Offline")
        self.lbl_youtube_status.setStyleSheet("color: #a6adc8; font-weight: bold;")
        self.btn_youtube_toggle = QPushButton("Bật Mock Live")
        self.btn_youtube_toggle.setObjectName("secondaryBtn")
        self.btn_youtube_toggle.clicked.connect(self.toggle_youtube)
        youtube_row.addWidget(self.lbl_youtube_status)
        youtube_row.addWidget(self.btn_youtube_toggle)
        conn_layout.addLayout(youtube_row)

        left_layout.addWidget(group_connectors)
        left_layout.addStretch()
        layout.addLayout(left_layout, stretch=1)

        # Right Column: System State & Connections
        right_layout = QVBoxLayout()
        
        # 3. OBS Connection Box
        group_obs = QGroupBox("Kết nối OBS Studio")
        obs_form = QFormLayout(group_obs)
        self.txt_obs_host = QLineEdit(self.obs.host)
        self.txt_obs_port = QLineEdit(str(self.obs.port))
        self.txt_obs_password = QLineEdit(self.obs.password)
        self.txt_obs_password.setEchoMode(QLineEdit.Password)
        obs_form.addRow("Host:", self.txt_obs_host)
        obs_form.addRow("Port:", self.txt_obs_port)
        obs_form.addRow("Mật khẩu:", self.txt_obs_password)

        obs_btn_layout = QHBoxLayout()
        self.btn_obs_connect = QPushButton("Kết nối")
        self.btn_obs_connect.setObjectName("successBtn")
        self.btn_obs_connect.clicked.connect(self.connect_obs)
        self.btn_obs_disconnect = QPushButton("Ngắt")
        self.btn_obs_disconnect.setObjectName("dangerBtn")
        self.btn_obs_disconnect.clicked.connect(self.disconnect_obs)
        self.btn_obs_disconnect.setEnabled(False)
        obs_btn_layout.addWidget(self.btn_obs_connect)
        obs_btn_layout.addWidget(self.btn_obs_disconnect)
        obs_form.addRow("", obs_btn_layout)
        right_layout.addWidget(group_obs)

        # 4. Queue Status Box
        group_queue = QGroupBox("Thống kê Hàng Đợi (Priority Queue)")
        queue_grid = QVBoxLayout(group_queue)
        
        self.lbl_q_high = QLabel("🔥 Ưu tiên CAO (Giá/Chốt đơn): 0 comment")
        self.lbl_q_high.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 13px;")
        self.lbl_q_med = QLabel("⚡ Ưu tiên TRUNG BÌNH (Ship/Size): 0 comment")
        self.lbl_q_med.setStyleSheet("color: #f9e2af; font-weight: bold; font-size: 13px;")
        self.lbl_q_low = QLabel("💬 Ưu tiên THẤP (Chào hỏi/Xã giao): 0 comment")
        self.lbl_q_low.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 13px;")
        
        queue_grid.addWidget(self.lbl_q_high)
        queue_grid.addWidget(self.lbl_q_med)
        queue_grid.addWidget(self.lbl_q_low)
        right_layout.addWidget(group_queue)
        
        right_layout.addStretch()
        layout.addLayout(right_layout, stretch=1)

    # ==================== TAB 2: PRODUCT MANAGER ====================
    def setup_products_tab(self):
        layout = QHBoxLayout(self.tab_products)

        # Table showing products
        self.table_products = QTableWidget()
        self.table_products.setColumnCount(7)
        self.table_products.setHorizontalHeaderLabels(["ID", "Mã", "Tên sản phẩm", "Giá", "Tồn kho", "OBS Scene", "OBS Source"])
        self.table_products.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_products.itemSelectionChanged.connect(self.on_product_selected)
        layout.addWidget(self.table_products, stretch=3)

        # Panel to Add/Edit Product
        right_panel = QVBoxLayout()
        group_edit = QGroupBox("Chi tiết & Thao tác")
        form_edit = QFormLayout(group_edit)
        
        self.txt_prod_id = QLineEdit()
        self.txt_prod_id.setReadOnly(True)
        self.txt_prod_code = QLineEdit()
        self.txt_prod_name = QLineEdit()
        self.txt_prod_price = QLineEdit()
        self.txt_prod_quantity = QLineEdit()
        self.txt_prod_desc = QTextEdit()
        self.txt_prod_desc.setMaximumHeight(80)
        self.txt_prod_scene = QLineEdit()
        self.txt_prod_source = QLineEdit()

        form_edit.addRow("ID:", self.txt_prod_id)
        form_edit.addRow("Mã SP (Dùng để nhận diện):", self.txt_prod_code)
        form_edit.addRow("Tên sản phẩm:", self.txt_prod_name)
        form_edit.addRow("Giá bán (VNĐ):", self.txt_prod_price)
        form_edit.addRow("Số lượng tồn:", self.txt_prod_quantity)
        form_edit.addRow("Mô tả chi tiết:", self.txt_prod_desc)
        form_edit.addRow("OBS Scene để switch:", self.txt_prod_scene)
        form_edit.addRow("OBS Source để bật:", self.txt_prod_source)

        btn_layout_1 = QHBoxLayout()
        self.btn_prod_save = QPushButton("Lưu / Cập nhật")
        self.btn_prod_save.clicked.connect(self.save_product)
        self.btn_prod_add = QPushButton("Thêm mới")
        self.btn_prod_add.setObjectName("successBtn")
        self.btn_prod_add.clicked.connect(self.add_product)
        btn_layout_1.addWidget(self.btn_prod_save)
        btn_layout_1.addWidget(self.btn_prod_add)
        form_edit.addRow("", btn_layout_1)

        btn_layout_2 = QHBoxLayout()
        self.btn_prod_delete = QPushButton("Xóa")
        self.btn_prod_delete.setObjectName("dangerBtn")
        self.btn_prod_delete.clicked.connect(self.delete_product)
        self.btn_show_obs = QPushButton("Hiện OBS")
        self.btn_show_obs.clicked.connect(self.show_product_obs)
        self.btn_hide_obs = QPushButton("Ẩn OBS")
        self.btn_hide_obs.setObjectName("secondaryBtn")
        self.btn_hide_obs.clicked.connect(self.hide_product_obs)
        btn_layout_2.addWidget(self.btn_prod_delete)
        btn_layout_2.addWidget(self.btn_show_obs)
        btn_layout_2.addWidget(self.btn_hide_obs)
        form_edit.addRow("", btn_layout_2)

        right_panel.addWidget(group_edit)
        layout.addLayout(right_panel, stretch=2)

    # ==================== TAB 4: ORDER MANAGER ====================
    def setup_orders_tab(self):
        layout = QHBoxLayout(self.tab_orders)

        # Table showing orders
        self.table_orders = QTableWidget()
        self.table_orders.setColumnCount(8)
        self.table_orders.setHorizontalHeaderLabels(["ID", "Khách hàng", "Nền tảng", "Mã sản phẩm", "Giá", "Số lượng", "Trạng thái", "Ngày tạo"])
        self.table_orders.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_orders.itemSelectionChanged.connect(self.on_order_selected)
        layout.addWidget(self.table_orders, stretch=3)

        # Panel to View/Edit Order Status
        right_panel = QVBoxLayout()
        group_edit = QGroupBox("Chi tiết & Trạng thái")
        form_edit = QFormLayout(group_edit)

        self.txt_order_id = QLineEdit()
        self.txt_order_id.setReadOnly(True)
        self.txt_order_cust = QLineEdit()
        self.txt_order_cust.setReadOnly(True)
        self.txt_order_prod = QLineEdit()
        self.txt_order_prod.setReadOnly(True)
        self.txt_order_price = QLineEdit()
        self.txt_order_price.setReadOnly(True)
        self.cb_order_status = QComboBox()
        self.cb_order_status.addItems(["Chờ xác nhận", "Đã chốt", "Đã giao"])

        form_edit.addRow("Đơn hàng ID:", self.txt_order_id)
        form_edit.addRow("Khách hàng:", self.txt_order_cust)
        form_edit.addRow("Sản phẩm:", self.txt_order_prod)
        form_edit.addRow("Giá bán:", self.txt_order_price)
        form_edit.addRow("Trạng thái đơn:", self.cb_order_status)

        btn_layout = QHBoxLayout()
        self.btn_order_save = QPushButton("Cập nhật trạng thái")
        self.btn_order_save.setObjectName("successBtn")
        self.btn_order_save.clicked.connect(self.update_selected_order_status)
        self.btn_order_delete = QPushButton("Xóa / Hủy đơn")
        self.btn_order_delete.setObjectName("dangerBtn")
        self.btn_order_delete.clicked.connect(self.delete_selected_order)
        btn_layout.addWidget(self.btn_order_save)
        btn_layout.addWidget(self.btn_order_delete)
        form_edit.addRow("", btn_layout)

        right_panel.addWidget(group_edit)
        layout.addLayout(right_panel, stretch=2)

    def load_orders(self):
        self.table_orders.setRowCount(0)
        orders = db.get_all_orders()
        for row_idx, order in enumerate(orders):
            self.table_orders.insertRow(row_idx)
            self.table_orders.setItem(row_idx, 0, QTableWidgetItem(str(order['id'])))
            self.table_orders.setItem(row_idx, 1, QTableWidgetItem(order['customer_name']))
            self.table_orders.setItem(row_idx, 2, QTableWidgetItem(order['platform']))
            self.table_orders.setItem(row_idx, 3, QTableWidgetItem(order['product_code']))
            self.table_orders.setItem(row_idx, 4, QTableWidgetItem(f"{order['price']:,.0f}"))
            self.table_orders.setItem(row_idx, 5, QTableWidgetItem(str(order['quantity'])))
            self.table_orders.setItem(row_idx, 6, QTableWidgetItem(order['status']))
            self.table_orders.setItem(row_idx, 7, QTableWidgetItem(order['created_at']))
        if orders:
            self.table_orders.selectRow(0)

    def on_order_selected(self):
        selected_rows = self.table_orders.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()

        self.txt_order_id.setText(self.table_orders.item(row, 0).text())
        self.txt_order_cust.setText(self.table_orders.item(row, 1).text())
        self.txt_order_prod.setText(self.table_orders.item(row, 3).text())
        self.txt_order_price.setText(self.table_orders.item(row, 4).text())
        
        status_text = self.table_orders.item(row, 6).text()
        index = self.cb_order_status.findText(status_text)
        if index >= 0:
            self.cb_order_status.setCurrentIndex(index)

    def update_selected_order_status(self):
        order_id_str = self.txt_order_id.text()
        if not order_id_str:
            return
        order_id = int(order_id_str)
        new_status = self.cb_order_status.currentText()

        if db.update_order_status(order_id, new_status):
            QMessageBox.information(self, "Thành công", f"Đã cập nhật đơn hàng #{order_id} sang trạng thái '{new_status}'!")
            self.load_orders()

    def delete_selected_order(self):
        order_id_str = self.txt_order_id.text()
        if not order_id_str:
            return
        order_id = int(order_id_str)
        confirm = QMessageBox.question(self, "Xác nhận", f"Bạn có chắc muốn xóa/hủy đơn hàng #{order_id}?\nHành động này sẽ hoàn trả số lượng sản phẩm lại kho.", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            if db.delete_order(order_id):
                QMessageBox.information(self, "Thành công", f"Đã xóa đơn hàng #{order_id} và hoàn trả tồn kho!")
                self.load_products()
                self.load_orders()
            else:
                QMessageBox.warning(self, "Lỗi", "Không thể xóa đơn hàng.")

    @Slot()
    def on_order_created(self):
        """Hàm callback nhận tín hiệu đơn hàng mới được tạo thành công."""
        self.load_products()
        self.load_orders()

    # ==================== TAB 4: TELEPROMPTER ====================
    def setup_teleprompter_tab(self):
        layout = QHBoxLayout(self.tab_teleprompter)
        
        # Left Panel: Large Prompter view & history
        left_panel = QVBoxLayout()
        
        # 1. Large Screen Label Box
        group_screen = QGroupBox("Màn hình nhắc lời (Teleprompter Screen)")
        screen_layout = QVBoxLayout(group_screen)
        
        self.lbl_prompt_text = QLabel("Chưa có câu nhắc nào. Hãy bắt đầu livestream!")
        self.lbl_prompt_text.setWordWrap(True)
        self.lbl_prompt_text.setAlignment(Qt.AlignCenter)
        self.lbl_prompt_text.setFont(QFont("Arial", 22, QFont.Bold))
        # High contrast styling (dark background, bright green text)
        self.lbl_prompt_text.setStyleSheet(
            "background-color: #1e1e2e; color: #a6e3a1; border-radius: 10px; padding: 20px; min-height: 180px;"
        )
        screen_layout.addWidget(self.lbl_prompt_text)
        left_panel.addWidget(group_screen)
        
        # 2. History Box
        group_history = QGroupBox("Lịch sử câu nhắc trong phiên")
        hist_layout = QVBoxLayout(group_history)
        self.txt_prompter_history = QTextEdit()
        self.txt_prompter_history.setReadOnly(True)
        self.txt_prompter_history.setStyleSheet("font-size: 13px; color: #cdd6f4;")
        hist_layout.addWidget(self.txt_prompter_history)
        
        btn_clear_prompter = QPushButton("Xóa lịch sử nhắc")
        btn_clear_prompter.clicked.connect(self.clear_prompter)
        hist_layout.addWidget(btn_clear_prompter)
        left_panel.addWidget(group_history)
        
        layout.addLayout(left_panel, 7)
        
        # Right Panel: Stream Session & Responsible Person Identity
        right_panel = QVBoxLayout()
        group_session = QGroupBox("Khai báo Danh tính & Phiên Live (Luật 1/7/2026)")
        session_form = QFormLayout(group_session)
        
        self.cmb_session_platform = QComboBox()
        self.cmb_session_platform.addItems(["TikTok", "Facebook", "YouTube", "Other"])
        session_form.addRow("Nền tảng:", self.cmb_session_platform)
        
        self.txt_responsible_person = QLineEdit()
        self.txt_responsible_person.setPlaceholderText("Ví dụ: Nguyễn Văn A")
        session_form.addRow("Người chịu trách nhiệm:", self.txt_responsible_person)
        
        self.txt_verification_ref = QLineEdit()
        self.txt_verification_ref.setPlaceholderText("Số CCCD / Mã định danh")
        session_form.addRow("Xác thực định danh:", self.txt_verification_ref)
        
        self.lbl_session_status = QLabel("Trạng thái: Chưa đăng ký phiên live")
        self.lbl_session_status.setStyleSheet("color: #f38ba8; font-weight: bold;")
        session_form.addRow(self.lbl_session_status)
        
        self.btn_start_session = QPushButton("Đăng ký & Bắt đầu Phiên Live")
        self.btn_start_session.setObjectName("successBtn")
        self.btn_start_session.clicked.connect(self.start_stream_session_from_gui)
        session_form.addRow(self.btn_start_session)
        
        self.btn_end_session = QPushButton("Kết thúc Phiên Live")
        self.btn_end_session.setObjectName("dangerBtn")
        self.btn_end_session.setEnabled(False)
        self.btn_end_session.clicked.connect(self.end_stream_session_from_gui)
        session_form.addRow(self.btn_end_session)
        
        right_panel.addWidget(group_session)
        right_panel.addStretch()
        
        layout.addLayout(right_panel, 3)
        
        # State variables
        self.current_session_id = None

    @Slot(str)
    def on_new_teleprompter_line(self, line: str):
        """Cập nhật giao diện khi có câu nhắc lời thoại AI MC mới."""
        self.lbl_prompt_text.setText(line)
        self.txt_prompter_history.append(f"• {line}\n")
        
    def clear_prompter(self):
        self.lbl_prompt_text.setText("Đã xóa lịch sử. Đang chờ câu nhắc tiếp theo...")
        self.txt_prompter_history.clear()
        
    def start_stream_session_from_gui(self):
        platform = self.cmb_session_platform.currentText()
        name = self.txt_responsible_person.text().strip()
        ref = self.txt_verification_ref.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Yêu cầu", "Vui lòng nhập tên người chịu trách nhiệm!")
            return
            
        from src.compliance_engine import get_policy
        policy = get_policy(platform)
        voice_mode_str = policy.voice_mode.value
        
        try:
            self.current_session_id = db.start_stream_session(platform, name, ref, voice_mode_str)
            self.lbl_session_status.setText(f"Phiên #{self.current_session_id}: Đang live ({platform} - {voice_mode_str})")
            self.lbl_session_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            
            self.btn_start_session.setEnabled(False)
            self.btn_end_session.setEnabled(True)
            self.cmb_session_platform.setEnabled(False)
            self.txt_responsible_person.setEnabled(False)
            self.txt_verification_ref.setEnabled(False)
            self.add_log(f"📋 Đã đăng ký phiên live #{self.current_session_id}. Người chịu trách nhiệm: {name}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu phiên live: {e}")
            
    def end_stream_session_from_gui(self):
        if self.current_session_id is None:
            return
            
        try:
            db.end_stream_session(self.current_session_id)
            self.add_log(f"📋 Đã đóng phiên live #{self.current_session_id}")
            self.current_session_id = None
            
            self.lbl_session_status.setText("Trạng thái: Đã kết thúc phiên live")
            self.lbl_session_status.setStyleSheet("color: #a6adc8; font-weight: bold;")
            
            self.btn_start_session.setEnabled(True)
            self.btn_end_session.setEnabled(False)
            self.cmb_session_platform.setEnabled(True)
            self.txt_responsible_person.setEnabled(True)
            self.txt_verification_ref.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể đóng phiên live: {e}")

    # ==================== TAB 5: SYSTEM LOGS ====================
    def setup_logs_tab(self):
        layout = QVBoxLayout(self.tab_logs)
        group_logs = QGroupBox("Nhật ký hoạt động hệ thống (System Logs)")
        logs_layout = QVBoxLayout(group_logs)
        
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setStyleSheet("background-color: #11111b; color: #a6e3a1; font-family: Consolas, monospace; font-size: 13px;")
        logs_layout.addWidget(self.txt_logs)
        
        self.btn_clear_logs = QPushButton("Xóa Nhật Ký")
        self.btn_clear_logs.setObjectName("secondaryBtn")
        self.btn_clear_logs.clicked.connect(self.txt_logs.clear)
        logs_layout.addWidget(self.btn_clear_logs)
        
        layout.addWidget(group_logs)

    # ==================== TAB 6: SETTINGS ====================
    def setup_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)

        group_config = QGroupBox("Cấu hình văn bản hiển thị lên OBS Subtitle / Overlay")
        form_config = QFormLayout(group_config)
        self.txt_subtitle_source = QLineEdit(self.queue_processor.subtitle_source)
        self.txt_comment_source = QLineEdit(self.queue_processor.comment_source)
        self.txt_subtitle_source.textChanged.connect(self.update_subtitle_source_name)
        self.txt_comment_source.textChanged.connect(self.update_comment_source_name)
        form_config.addRow("Tên Text Source phụ đề (Subtitle):", self.txt_subtitle_source)
        form_config.addRow("Tên Text Source comment ghim:", self.txt_comment_source)
        
        # Autopilot config switches
        self.chk_auto_scene = QCheckBox("Tự động chuyển đổi scene trong OBS")
        self.chk_auto_scene.setChecked(self.queue_processor.auto_scene)
        self.chk_auto_scene.stateChanged.connect(self.toggle_auto_scene)
        self.chk_auto_show_source = QCheckBox("Tự động hiển thị ảnh/source sản phẩm trong OBS")
        self.chk_auto_show_source.setChecked(self.queue_processor.auto_show_source)
        self.chk_auto_show_source.stateChanged.connect(self.toggle_auto_show_source)
        
        form_config.addRow("", self.chk_auto_scene)
        form_config.addRow("", self.chk_auto_show_source)
        layout.addWidget(group_config)

        group_tts = QGroupBox("Cài đặt giọng đọc (Text to Speech)")
        form_tts = QFormLayout(group_tts)
        self.cb_voice = QComboBox()
        self.cb_voice.addItem("Giọng Nữ Nam Bộ (vi-VN-HoaiMyNeural)", "vi-VN-HoaiMyNeural")
        self.cb_voice.addItem("Giọng Nam Bắc Bộ (vi-VN-NamMinhNeural)", "vi-VN-NamMinhNeural")
        index = self.cb_voice.findData(self.tts.voice)
        if index >= 0:
            self.cb_voice.setCurrentIndex(index)
        self.cb_voice.currentIndexChanged.connect(self.change_voice)
        form_tts.addRow("Giọng đọc tiếng Việt:", self.cb_voice)
        
        self.btn_test_tts = QPushButton("Thử giọng đọc (Test Voice)")
        self.btn_test_tts.setObjectName("secondaryBtn")
        self.btn_test_tts.clicked.connect(self.test_voice)
        form_tts.addRow("", self.btn_test_tts)
        layout.addWidget(group_tts)

        # Cấu hình VMC MC ảo
        group_vmc = QGroupBox("Cấu hình & Vận hành MC ảo (Renderer 3D)")
        form_vmc = QFormLayout(group_vmc)
        
        # 1. VNyan.exe Path
        self.txt_vnyan_path = QLineEdit(os.getenv("VNYAN_EXE_PATH", ""))
        self.btn_vnyan_browse = QPushButton("Chọn tệp VNyan.exe")
        self.btn_vnyan_browse.setObjectName("secondaryBtn")
        self.btn_vnyan_browse.clicked.connect(self.browse_vnyan_exe)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.txt_vnyan_path)
        path_layout.addWidget(self.btn_vnyan_browse)
        form_vmc.addRow("Đường dẫn VNyan.exe:", path_layout)
        
        # 2. Avatar VRM Path
        self.txt_avatar_path = QLineEdit(os.getenv("AVATAR_VRM_PATH", ""))
        self.btn_avatar_browse = QPushButton("Chọn tệp Avatar.vrm")
        self.btn_avatar_browse.setObjectName("secondaryBtn")
        self.btn_avatar_browse.clicked.connect(self.browse_avatar_vrm)
        
        avatar_layout = QHBoxLayout()
        avatar_layout.addWidget(self.txt_avatar_path)
        avatar_layout.addWidget(self.btn_avatar_browse)
        form_vmc.addRow("Đường dẫn Avatar VRM:", avatar_layout)
        
        # 3. MC Controls Button Row
        self.btn_mc_on = QPushButton("Bật MC ảo")
        self.btn_mc_on.setObjectName("successBtn")
        self.btn_mc_on.clicked.connect(self.start_mc_setup)
        
        self.btn_mc_off = QPushButton("Tắt MC ảo")
        self.btn_mc_off.setObjectName("dangerBtn")
        self.btn_mc_off.clicked.connect(self.stop_mc_setup)
        
        self.btn_mc_sync = QPushButton("Đồng bộ Node Graph")
        self.btn_mc_sync.setObjectName("secondaryBtn")
        self.btn_mc_sync.clicked.connect(self.sync_node_graph_only)
        
        self.btn_mc_check = QPushButton("Kiểm tra kết nối")
        self.btn_mc_check.setObjectName("secondaryBtn")
        self.btn_mc_check.clicked.connect(self.manual_connection_check)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_mc_on)
        btn_layout.addWidget(self.btn_mc_off)
        btn_layout.addWidget(self.btn_mc_sync)
        btn_layout.addWidget(self.btn_mc_check)
        form_vmc.addRow("", btn_layout)
        
        # 4. Progress bar & step description
        self.progress_setup = QProgressBar()
        self.progress_setup.setRange(0, 18)
        self.progress_setup.setValue(0)
        self.progress_setup.setTextVisible(True)
        self.progress_setup.setMaximumHeight(15)
        self.progress_setup.setStyleSheet("QProgressBar { background-color: #313244; border: 1px solid #45475a; border-radius: 4px; text-align: center; } QProgressBar::chunk { background-color: #89b4fa; border-radius: 4px; }")
        
        self.lbl_setup_step = QLabel("Đang chờ lệnh...")
        self.lbl_setup_step.setStyleSheet("color: #a6adc8; font-style: italic;")
        
        form_vmc.addRow("Tiến trình Setup:", self.progress_setup)
        form_vmc.addRow("", self.lbl_setup_step)
        
        # 5. Overall status label
        self.lbl_vnyan_status = QLabel("MC ẢO — CHƯA KHỞI CHẠY")
        self.lbl_vnyan_status.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 14px;")
        form_vmc.addRow("Trạng thái:", self.lbl_vnyan_status)
        
        # 6. Detailed checklist panel (3x2 grid)
        checklist_group = QGroupBox("Danh sách kiểm tra chi tiết (Detailed Status)")
        grid_layout = QGridLayout(checklist_group)
        
        self.lbl_status_process = QLabel("🖥️ Tiến trình VNyan (FAIL)")
        self.lbl_status_avatar = QLabel("👤 Avatar VRM (FAIL)")
        self.lbl_status_vmc = QLabel("🌐 Kết nối VMC (FAIL)")
        self.lbl_status_nodegraph = QLabel("📊 Đồ thị Node Graph (FAIL)")
        self.lbl_status_mapping = QLabel("🎬 Ánh xạ Hoạt ảnh (FAIL)")
        self.lbl_status_control = QLabel("🤖 Điều khiển AI Live (FAIL)")
        
        # Set default styles
        for lbl in [self.lbl_status_process, self.lbl_status_avatar, self.lbl_status_vmc, 
                    self.lbl_status_nodegraph, self.lbl_status_mapping, self.lbl_status_control]:
            lbl.setStyleSheet("color: #f38ba8; font-weight: bold;")
            
        grid_layout.addWidget(self.lbl_status_process, 0, 0)
        grid_layout.addWidget(self.lbl_status_avatar, 0, 1)
        grid_layout.addWidget(self.lbl_status_vmc, 1, 0)
        grid_layout.addWidget(self.lbl_status_nodegraph, 1, 1)
        grid_layout.addWidget(self.lbl_status_mapping, 2, 0)
        grid_layout.addWidget(self.lbl_status_control, 2, 1)
        form_vmc.addRow("", checklist_group)
        
        # 7. Log & Detail text display
        self.txt_setup_logs = QTextEdit()
        self.txt_setup_logs.setReadOnly(True)
        self.txt_setup_logs.setMaximumHeight(80)
        self.txt_setup_logs.setStyleSheet("background-color: #11111b; color: #a6e3a1; font-family: Consolas, monospace; font-size: 11px;")
        form_vmc.addRow("Nhật ký Setup:", self.txt_setup_logs)
        
        layout.addWidget(group_vmc)

        layout.addStretch()

    def browse_vnyan_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn tệp thực thi VNyan",
            "",
            "Executable Files (*.exe);;All Files (*)"
        )
        if file_path:
            self.txt_vnyan_path.setText(file_path)
            from src.config import Config
            Config.VNYAN_EXE_PATH = file_path
            self.update_env_file("VNYAN_EXE_PATH", file_path)

    def update_env_file(self, key: str, value: str):
        env_path = ".env"
        tmp_path = ".env.tmp"
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = []
                key_found = False
                for line in lines:
                    if line.strip().startswith(f"{key}="):
                        new_lines.append(f"{key}={value}\n")
                        key_found = True
                    else:
                        new_lines.append(line)
                if not key_found:
                    new_lines.append(f"{key}={value}\n")
                
                # Thực hiện ghi nguyên tử (Atomic Write)
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                os.replace(tmp_path, env_path)
            except Exception as e:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                self.signals.log_event.emit(f"Lỗi cập nhật .env: {e}")

    def browse_avatar_vrm(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn tệp Avatar VRM",
            "",
            "VRM Files (*.vrm);;All Files (*)"
        )
        if file_path:
            self.txt_avatar_path.setText(file_path)
            from src.config import Config
            Config.AVATAR_VRM_PATH = file_path
            self.update_env_file("AVATAR_VRM_PATH", file_path)
            # Tải vào VMC Client
            self.queue_processor.vmc_client.load_avatar(file_path)
            self.signals.log_event.emit(f"🎭 Đã lưu cấu hình đường dẫn Avatar VRM: {file_path}")

    def start_mc_setup(self):
        vnyan_path = self.txt_vnyan_path.text().strip()
        avatar_path = self.txt_avatar_path.text().strip()
        
        if not vnyan_path:
            QMessageBox.warning(self, "Yêu cầu", "Vui lòng nhập hoặc chọn đường dẫn VNyan.exe!")
            return
        if not avatar_path:
            QMessageBox.warning(self, "Yêu cầu", "Vui lòng nhập hoặc chọn đường dẫn Avatar VRM!")
            return
            
        # Lưu vào config & env
        from src.config import Config
        Config.VNYAN_EXE_PATH = vnyan_path
        Config.AVATAR_VRM_PATH = avatar_path
        self.update_env_file("VNYAN_EXE_PATH", vnyan_path)
        self.update_env_file("AVATAR_VRM_PATH", avatar_path)
        
        # Vô hiệu hóa các nút điều khiển trong khi cài đặt
        self.btn_mc_on.setEnabled(False)
        self.btn_mc_sync.setEnabled(False)
        self.txt_setup_logs.clear()
        self.progress_setup.setValue(0)
        self.lbl_setup_step.setText("Bắt đầu quy trình setup...")
        
        # Khởi chạy Worker Thread
        from ai_live.integrations.vnyan.service import VnyanService
        service = VnyanService()
        
        self.setup_worker = VnyanSetupWorker(service, vnyan_path, avatar_path)
        self.setup_worker.progress_signal.connect(self.on_setup_progress)
        self.setup_worker.finished_signal.connect(self.on_setup_finished)
        self.setup_worker.start()
        
        self.signals.log_event.emit("🎭 [MC ảo] Đang khởi động tiến trình 1-Click Setup VNyan...")

    def on_setup_progress(self, step, name, status, detail=""):
        self.progress_setup.setValue(step)
        detail_str = f" - {detail}" if detail else ""
        log_line = f"[{step}/18] {name}: {status}{detail_str}"
        self.lbl_setup_step.setText(f"[{step}/18] {name}... ({status})")
        self.txt_setup_logs.append(log_line)
        
    def on_setup_finished(self, result):
        self.btn_mc_on.setEnabled(True)
        self.btn_mc_sync.setEnabled(True)
        
        if result.success:
            self.progress_setup.setValue(18)
            self.lbl_setup_step.setText("Thiết lập thành công! MC Sẵn sàng.")
            self.lbl_vnyan_status.setText("MC ẢO — SẴN SÀNG ĐIỀU KHIỂN")
            self.lbl_vnyan_status.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 14px;")
            self.signals.log_event.emit("🎭 [MC ảo] 1-Click Setup thành công! MC ảo sẵn sàng điều khiển.")
            QMessageBox.information(self, "Thành công", "Tích hợp VNyan hoàn tất! MC ảo đã sẵn sàng hoạt động.")
        else:
            self.lbl_setup_step.setText("Thiết lập thất bại.")
            self.lbl_vnyan_status.setText("MC ẢO — CHƯA SẴN SÀNG")
            self.lbl_vnyan_status.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 14px;")
            
            errs = "\n".join(result.errors)
            self.signals.log_event.emit(f"⚠️ [MC ảo] Cài đặt thất bại: {errs}")
            QMessageBox.critical(self, "Lỗi cài đặt", f"Cài đặt tích hợp VNyan thất bại!\nChi tiết: {errs}")
            
        # Cập nhật nhanh checklist indicators
        self.manual_connection_check()

    def stop_mc_setup(self):
        from ai_live.integrations.vnyan.service import VnyanService
        VnyanService().stop_mc()
        self.signals.log_event.emit("🎭 [MC ảo] Đã gửi lệnh tắt tiến trình VNyan.")
        QMessageBox.information(self, "Đã tắt", "Đã gửi lệnh dừng MC ảo (VNyan).")
        self.manual_connection_check()

    def sync_node_graph_only(self):
        self.signals.log_event.emit("🎭 [MC ảo] Đang tiến hành đồng bộ Node Graph...")
        from ai_live.integrations.vnyan.service import VnyanService
        service = VnyanService()
        success = service.setup_manager.installer.install_ai_live_bridge()
        if success:
            self.signals.log_event.emit("🎭 [MC ảo] Đồng bộ Node Graph thành công.")
            QMessageBox.information(self, "Thành công", "Đồng bộ Node Graph thành công (Lũy đẳng).")
        else:
            self.signals.log_event.emit("⚠️ [MC ảo] Đồng bộ Node Graph thất bại.")
            QMessageBox.warning(self, "Lỗi", "Đồng bộ Node Graph thất bại. Vui lòng kiểm tra lại!")
        self.manual_connection_check()

    def manual_connection_check(self):
        self.update_renderer_status_ui()

    def update_renderer_status_ui(self):
        """Được gọi định kỳ bằng QTimer để cập nhật trạng thái online của Renderer 3D."""
        try:
            from ai_live.integrations.vnyan.service import VnyanService
            service = VnyanService()
            details = service.get_status_details()
            
            # Cập nhật trạng thái từng cấu phần
            def format_label(label, passed, text):
                if passed:
                    label.setText(f"{text} (PASS)")
                    label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
                else:
                    label.setText(f"{text} (FAIL)")
                    label.setStyleSheet("color: #f38ba8; font-weight: bold;")
                    
            format_label(self.lbl_status_process, details["process"][0], "🖥️ Tiến trình VNyan")
            format_label(self.lbl_status_avatar, details["avatar"][0], "👤 Avatar VRM")
            format_label(self.lbl_status_vmc, details["vmc"][0], "🌐 Kết nối VMC")
            format_label(self.lbl_status_nodegraph, details["node_graph"][0], "📊 Đồ thị Node Graph")
            format_label(self.lbl_status_mapping, details["animation_mapping"][0], "🎬 Ánh xạ Hoạt ảnh")
            format_label(self.lbl_status_control, details["control"][0], "🤖 Điều khiển AI Live")
            
            # Trạng thái tổng quát
            all_ready = all(status for status, _ in details.values())
            if all_ready:
                self.lbl_vnyan_status.setText("MC ẢO — SẴN SÀNG ĐIỀU KHIỂN")
                self.lbl_vnyan_status.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 14px;")
            else:
                self.lbl_vnyan_status.setText("MC ẢO — CHƯA SẴN SÀNG")
                self.lbl_vnyan_status.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 14px;")
        except Exception as e:
            # Fallback nếu service chưa được khởi tạo đầy đủ
            online = self.queue_processor.vmc_client.renderer_online
            if online:
                self.lbl_vnyan_status.setText("MC ẢO — SẴN SÀNG ĐIỀU KHIỂN")
                self.lbl_vnyan_status.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 14px;")
            else:
                self.lbl_vnyan_status.setText("MC ẢO — CHƯA KHỞI CHẠY")
                self.lbl_vnyan_status.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 14px;")

    # ==================== CORE ASYNC LOOPS INTEGRATION ====================
    def start_core_tasks(self):
        # 1. Start Priority Queue Processor loop
        asyncio.run_coroutine_threadsafe(self.queue_processor.start(), self.loop)
        
        # 2. Subscribe to comment_received event and pipe into queue processor
        async def comment_event_listener():
            queue = await global_broker.subscribe("comment_received")
            try:
                while True:
                    comment_data = await queue.get()
                    await self.queue_processor.enqueue(comment_data)
            except asyncio.CancelledError:
                pass
            finally:
                await global_broker.unsubscribe("comment_received", queue)
                
        asyncio.run_coroutine_threadsafe(comment_event_listener(), self.loop)

        # 3. Khởi chạy HighlightDirector
        from src.highlight_director import HighlightDirector
        self.highlight_director = HighlightDirector(self.obs, self.signals)
        asyncio.run_coroutine_threadsafe(self.highlight_director.start(), self.loop)

    # UI updates callbacks called from threads/async processes
    def on_queue_changed(self, sizes: dict):
        self.signals.queue_updated.emit(sizes)

    def on_ai_response(self, username: str, comment: str, answer: str):
        self.signals.ai_response_ready.emit(username, comment, answer)

    @Slot(dict)
    def update_queue_ui(self, sizes: dict):
        self.lbl_q_high.setText(f"🔥 Ưu tiên CAO (Giá/Chốt đơn): {sizes['high']} comment")
        self.lbl_q_med.setText(f"⚡ Ưu tiên TRUNG BÌNH (Ship/Size): {sizes['medium']} comment")
        self.lbl_q_low.setText(f"💬 Ưu tiên THẤP (Chào hỏi/Xã giao): {sizes['low']} comment")

    @Slot(str, str, str)
    def on_ai_response_ready(self, username: str, comment: str, answer: str):
        self.signals.log_event.emit(f"🤖 AI trả lời {username}: {answer}")

    @Slot(str)
    def add_log(self, text: str):
        self.txt_logs.append(text)

    # Web Server & AI Director Controls
    def toggle_web_server(self):
        from src.web.server import start_api_server, stop_api_server, WEB_TOKEN
        if not self.web_server_running:
            start_api_server(self, host="127.0.0.1", port=8000)
            self.web_server_running = True
            url_with_token = f"http://127.0.0.1:8000/?token={WEB_TOKEN}"
            self.lbl_web_status.setText(f"Web URL: {url_with_token}")
            self.lbl_web_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.lbl_web_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.btn_web_toggle.setText("Dừng Web Server")
            self.btn_web_toggle.setObjectName("dangerBtn")
            self.load_stylesheet()
            self.signals.log_event.emit(f"🌐 [Web Server] FastAPI đã khởi chạy tại: {url_with_token}")
        else:
            stop_api_server()
            self.web_server_running = False
            self.lbl_web_status.setText("Web Server: Offline")
            self.lbl_web_status.setStyleSheet("color: #a6adc8; font-weight: bold;")
            self.btn_web_toggle.setText("Chạy Web Server")
            self.btn_web_toggle.setObjectName("successBtn")
            self.load_stylesheet()
            self.signals.log_event.emit("🌐 [Web Server] Đã dừng FastAPI Web Server.")

    def toggle_ai_director(self):
        if not self.director.is_running:
            self.btn_dir_toggle.setText("Tắt Đạo Diễn")
            self.btn_dir_toggle.setObjectName("dangerBtn")
            self.load_stylesheet()
            self.lbl_dir_status.setText("Đạo Diễn AI: Đang chạy")
            self.lbl_dir_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.signals.log_event.emit("🎬 [Đạo Diễn AI] Bắt đầu chạy kịch bản tự động...")
            asyncio.run_coroutine_threadsafe(self.director.start(), self.loop)
        else:
            self.btn_dir_toggle.setText("Bật Đạo Diễn")
            self.btn_dir_toggle.setObjectName("successBtn")
            self.load_stylesheet()
            self.lbl_dir_status.setText("Đạo Diễn AI: Tắt")
            self.lbl_dir_status.setStyleSheet("color: #a6adc8; font-weight: bold;")
            self.signals.log_event.emit("🎬 [Đạo Diễn AI] Đã dừng kịch bản tự động.")
            asyncio.run_coroutine_threadsafe(self.director.stop(), self.loop)

    # Connector control
    @Slot()
    def toggle_tiktok(self):
        if not self.tiktok_conn.is_running:
            self.btn_tiktok_toggle.setText("Dừng Mock Live")
            self.btn_tiktok_toggle.setObjectName("dangerBtn")
            self.load_stylesheet()
            self.signals.log_event.emit("▶️ Khởi động trình giả lập TikTok...")
            asyncio.run_coroutine_threadsafe(self.tiktok_conn.start(), self.loop)
            self.signals.connector_status.emit("TikTok", True)
        else:
            self.btn_tiktok_toggle.setText("Bật Mock Live")
            self.btn_tiktok_toggle.setObjectName("secondaryBtn")
            self.load_stylesheet()
            self.signals.log_event.emit("⏹️ Dừng trình giả lập TikTok.")
            asyncio.run_coroutine_threadsafe(self.tiktok_conn.stop(), self.loop)
            self.signals.connector_status.emit("TikTok", False)

    @Slot()
    def toggle_facebook(self):
        if not self.facebook_conn.is_running:
            self.btn_facebook_toggle.setText("Dừng Mock Live")
            self.btn_facebook_toggle.setObjectName("dangerBtn")
            self.load_stylesheet()
            self.signals.log_event.emit("▶️ Khởi động trình giả lập Facebook...")
            asyncio.run_coroutine_threadsafe(self.facebook_conn.start(), self.loop)
            self.signals.connector_status.emit("Facebook", True)
        else:
            self.btn_facebook_toggle.setText("Bật Mock Live")
            self.btn_facebook_toggle.setObjectName("secondaryBtn")
            self.load_stylesheet()
            self.signals.log_event.emit("⏹️ Dừng trình giả lập Facebook.")
            asyncio.run_coroutine_threadsafe(self.facebook_conn.stop(), self.loop)
            self.signals.connector_status.emit("Facebook", False)

    @Slot()
    def toggle_youtube(self):
        if not self.youtube_conn.is_running:
            self.btn_youtube_toggle.setText("Dừng Mock Live")
            self.btn_youtube_toggle.setObjectName("dangerBtn")
            self.load_stylesheet()
            self.signals.log_event.emit("▶️ Khởi động trình giả lập YouTube...")
            asyncio.run_coroutine_threadsafe(self.youtube_conn.start(), self.loop)
            self.signals.connector_status.emit("YouTube", True)
        else:
            self.btn_youtube_toggle.setText("Bật Mock Live")
            self.btn_youtube_toggle.setObjectName("secondaryBtn")
            self.load_stylesheet()
            self.signals.log_event.emit("⏹️ Dừng trình giả lập YouTube.")
            asyncio.run_coroutine_threadsafe(self.youtube_conn.stop(), self.loop)
            self.signals.connector_status.emit("YouTube", False)

    @Slot(str, bool)
    def update_connector_ui(self, name: str, is_running: bool):
        if name == "TikTok":
            lbl = self.lbl_tiktok_status
        elif name == "Facebook":
            lbl = self.lbl_facebook_status
        else:
            lbl = self.lbl_youtube_status
            
        if is_running:
            lbl.setText(f"{name}: Online (Running)")
            lbl.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        else:
            lbl.setText(f"{name}: Offline")
            lbl.setStyleSheet("color: #a6adc8; font-weight: bold;")

    # Simulate manual comments
    def simulate_comment(self):
        username = self.txt_sim_user.text().strip()
        comment = self.cb_sim_comment.currentText().strip()
        if not username or not comment:
            return
            
        platform = self.cmb_session_platform.currentText()
        self.signals.log_event.emit(f"\n💬 Gửi comment thủ công: {username}: '{comment}' ({platform})")
        event_data = {
            "platform": platform,
            "username": username,
            "comment": comment
        }
        asyncio.run_coroutine_threadsafe(
            global_broker.publish("comment_received", event_data), 
            self.loop
        )

    # OBS connection setup
    def connect_obs(self):
        self.obs.host = self.txt_obs_host.text()
        self.obs.port = int(self.txt_obs_port.text())
        self.obs.password = self.txt_obs_password.text()
        self.signals.log_event.emit(f"Đang kết nối OBS {self.obs.host}:{self.obs.port}...")
        
        def connect_thread():
            if self.obs.connect():
                self.signals.log_event.emit("Đã kết nối thành công với OBS!")
                self.signals.tts_status.emit("OBS: Connected", True)
                # Tự động kích hoạt Replay Buffer
                self.obs.start_replay_buffer()
            else:
                self.signals.log_event.emit("Lỗi: Không thể kết nối với OBS.")
                self.signals.tts_status.emit("OBS: Disconnected", False)
                
        threading.Thread(target=connect_thread, daemon=True).start()

    def disconnect_obs(self):
        if self.obs.is_connected:
            self.obs.stop_replay_buffer()
        self.obs.disconnect()
        self.signals.tts_status.emit("OBS: Disconnected", False)
        self.signals.log_event.emit("Đã ngắt kết nối OBS.")

    @Slot(str, bool)
    def on_tts_status(self, text: str, connected: bool):
        if "OBS" in text:
            if connected:
                self.lbl_obs_status.setText("OBS: Connected")
                self.lbl_obs_status.setStyleSheet("color: #a6e3a1; font-weight: bold; padding: 4px 8px; border: 1px solid #a6e3a1; border-radius: 5px;")
                self.btn_obs_connect.setEnabled(False)
                self.btn_obs_disconnect.setEnabled(True)
            else:
                self.lbl_obs_status.setText("OBS: Disconnected")
                self.lbl_obs_status.setStyleSheet("color: #f38ba8; font-weight: bold; padding: 4px 8px; border: 1px solid #f38ba8; border-radius: 5px;")
                self.btn_obs_connect.setEnabled(True)
                self.btn_obs_disconnect.setEnabled(False)

    # Settings and Voice configuration
    def change_voice(self, index):
        voice_data = self.cb_voice.itemData(index)
        self.tts.voice = voice_data
        self.signals.log_event.emit(f"⚙️ Thay đổi giọng đọc thành: {self.cb_voice.itemText(index)}")

    def test_voice(self):
        test_text = "Hệ thống hàng đợi âm thanh tuần tự đang hoạt động ổn định."
        self.signals.log_event.emit("🗣️ Đang phát thử giọng nói...")
        self.tts.speak(test_text, on_finished=lambda: self.signals.log_event.emit("🔇 Đã hoàn thành phát thử."))

    def update_subtitle_source_name(self, text):
        self.queue_processor.subtitle_source = text.strip()

    def update_comment_source_name(self, text):
        self.queue_processor.comment_source = text.strip()

    def toggle_auto_scene(self, state):
        self.queue_processor.auto_scene = bool(state)

    def toggle_auto_show_source(self, state):
        self.queue_processor.auto_show_source = bool(state)

    # Product management functions
    def load_products(self):
        self.table_products.setRowCount(0)
        products = db.get_all_products()
        for row_idx, prod in enumerate(products):
            self.table_products.insertRow(row_idx)
            self.table_products.setItem(row_idx, 0, QTableWidgetItem(str(prod['id'])))
            self.table_products.setItem(row_idx, 1, QTableWidgetItem(prod['code']))
            self.table_products.setItem(row_idx, 2, QTableWidgetItem(prod['name']))
            self.table_products.setItem(row_idx, 3, QTableWidgetItem(f"{prod['price']:,.0f}"))
            self.table_products.setItem(row_idx, 4, QTableWidgetItem(str(prod['quantity'])))
            self.table_products.setItem(row_idx, 5, QTableWidgetItem(prod['obs_scene']))
            self.table_products.setItem(row_idx, 6, QTableWidgetItem(prod['obs_source']))
        if products:
            self.table_products.selectRow(0)

    def on_product_selected(self):
        selected_rows = self.table_products.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        
        self.txt_prod_id.setText(self.table_products.item(row, 0).text())
        self.txt_prod_code.setText(self.table_products.item(row, 1).text())
        self.txt_prod_name.setText(self.table_products.item(row, 2).text())
        price_val = self.table_products.item(row, 3).text().replace(",", "")
        self.txt_prod_price.setText(price_val)
        self.txt_prod_quantity.setText(self.table_products.item(row, 4).text())
        self.txt_prod_scene.setText(self.table_products.item(row, 5).text())
        self.txt_prod_source.setText(self.table_products.item(row, 6).text())
        
        prod_id = int(self.txt_prod_id.text())
        products = db.get_all_products()
        for p in products:
            if p['id'] == prod_id:
                self.txt_prod_desc.setPlainText(p['description'] or "")
                break

    def save_product(self):
        prod_id_str = self.txt_prod_id.text()
        if not prod_id_str:
            return
        prod_id = int(prod_id_str)
        code = self.txt_prod_code.text().strip()
        name = self.txt_prod_name.text().strip()
        try:
            price = float(self.txt_prod_price.text().strip())
            quantity = int(self.txt_prod_quantity.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Lỗi", "Giá và số lượng phải là số.")
            return
        desc = self.txt_prod_desc.toPlainText().strip()
        scene = self.txt_prod_scene.text().strip()
        source = self.txt_prod_source.text().strip()

        if db.update_product(prod_id, code, name, price, quantity, desc, "", scene, source):
            QMessageBox.information(self, "Thành công", "Đã cập nhật sản phẩm!")
            self.load_products()

    def add_product(self):
        code = self.txt_prod_code.text().strip()
        name = self.txt_prod_name.text().strip()
        if not code or not name:
            return
        try:
            price = float(self.txt_prod_price.text().strip()) if self.txt_prod_price.text().strip() else 0.0
            quantity = int(self.txt_prod_quantity.text().strip()) if self.txt_prod_quantity.text().strip() else 0
        except ValueError:
            QMessageBox.warning(self, "Lỗi", "Giá và số lượng phải là số.")
            return
        desc = self.txt_prod_desc.toPlainText().strip()
        scene = self.txt_prod_scene.text().strip()
        source = self.txt_prod_source.text().strip()

        if db.add_product(code, name, price, quantity, desc, "", scene, source):
            QMessageBox.information(self, "Thành công", "Đã thêm sản phẩm!")
            self.load_products()

    def delete_product(self):
        prod_id_str = self.txt_prod_id.text()
        if not prod_id_str:
            return
        confirm = QMessageBox.question(self, "Xác nhận", "Xóa sản phẩm này?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            db.delete_product(int(prod_id_str))
            self.load_products()

    def show_product_obs(self):
        scene = self.txt_prod_scene.text().strip()
        source = self.txt_prod_source.text().strip()
        if self.obs.is_connected and scene and source:
            self.obs.set_source_visibility(scene, source, True)

    def hide_product_obs(self):
        scene = self.txt_prod_scene.text().strip()
        source = self.txt_prod_source.text().strip()
        if self.obs.is_connected and scene and source:
            self.obs.set_source_visibility(scene, source, False)

    def closeEvent(self, event):
        """Dừng tất cả các luồng chạy ngầm khi đóng cửa sổ."""
        # Stop Web Server
        from src.web.server import stop_api_server
        stop_api_server()
        
        # Stop connectors
        asyncio.run_coroutine_threadsafe(self.tiktok_conn.stop(), self.loop)
        asyncio.run_coroutine_threadsafe(self.facebook_conn.stop(), self.loop)
        asyncio.run_coroutine_threadsafe(self.youtube_conn.stop(), self.loop)
        
        # Stop Highlight Director
        if hasattr(self, 'highlight_director'):
            asyncio.run_coroutine_threadsafe(self.highlight_director.stop(), self.loop)
        
        # Stop queue processor & director
        asyncio.run_coroutine_threadsafe(self.queue_processor.stop(), self.loop)
        asyncio.run_coroutine_threadsafe(self.director.stop(), self.loop)
        
        # Stop async event loop
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.async_thread.join(timeout=1.0)
        
        self.tts.stop()
        if self.obs.is_connected:
            self.obs.stop_replay_buffer()
        self.obs.disconnect()
        event.accept()
