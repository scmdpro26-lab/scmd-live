import logging
from google import genai
from google.genai import types
from typing import Optional, Dict, Any, List
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIBrain")

def predict_vietnamese_pronoun(username: str) -> str:
    """Dự đoán xưng hô 'anh' hoặc 'chị' hoặc 'bạn' dựa trên tên tiếng Việt của người dùng."""
    if not username:
        return "anh/chị"
        
    username_lower = username.strip().lower()
    words = username_lower.split()
    
    # 1. Check trực tiếp trong từ đầu tiên hoặc toàn bộ username
    if words:
        first_word = words[0]
        if first_word in ["anh", "mr", "boy", "man", "bro"]:
            return "anh"
        if first_word in ["chị", "chi", "ms", "mrs", "girl", "lady", "sis"]:
            return "chị"
            
    # 2. Danh sách các tên hoặc chữ lót phổ biến của nữ
    female_indicators = [
        "thị", "thi", "vy", "nhi", "trang", "hương", "huong", "lan", "mai", "hoa", 
        "nga", "hạnh", "hanh", "ngọc", "ngoc", "quỳnh", "quynh", "phương", "phuong", 
        "linh", "hà", "ha", "chi", "tuyết", "tuyet", "yến", "yen", "oanh", "thảo", "thao",
        "huyền", "huyen", "dung", "hằng", "hang", "thu", "thủy", "thuy", "trúc", "truc",
        "nữ", "nu", "trinh", "kiều", "kieu", "nhung", "liên", "lien", "hồng", "hong",
        "my", "mỹ", "kiều", "bích", "bich", "diệp", "diep", "trà", "tra", "nhã", "nha"
    ]
    
    # 3. Danh sách các tên hoặc chữ lót phổ biến của nam
    male_indicators = [
        "văn", "van", "hùng", "hung", "cường", "cuong", "mạnh", "manh", "tuấn", "tuan", 
        "kiên", "kien", "minh", "đức", "duc", "hải", "hai", "sơn", "son", "nam", 
        "bình", "binh", "phong", "quang", "khánh", "khanh", "thành", "thanh", "hoàng", "hoang", 
        "dũng", "dung_male", "trung", "quân", "quan", "thắng", "thang", "long", "bách", "bach",
        "hào", "hao", "vũ", "vu", "huy", "đạt", "dat", "tiến", "tien", "sỹ", "sy", "khoa",
        "kiệt", "kiet", "phúc", "phuc", "lộc", "loc", "thọ", "tho", "khải", "khai",
        "kiên", "quốc", "quoc", "bảo", "bao", "duy", "gia", "phong", "sơn"
    ]
    
    # Ưu tiên tìm đệm đặc trưng nhất trước
    if "thị" in words or "thi" in words:
        return "chị"
    if "văn" in words or "van" in words:
        return "anh"
        
    # Check từ cuối cùng (tên chính)
    if words:
        last_word = words[-1]
        if last_word in female_indicators:
            return "chị"
        if last_word in male_indicators:
            return "anh"
            
    # Check các từ khác lân cận
    for word in words:
        if word in female_indicators:
            return "chị"
        if word in male_indicators:
            return "anh"
            
    # Mặc định an toàn
    return "anh/chị"

class AIBrain:
    def __init__(self):
        self.api_configured = False
        self.client = None
        self.system_instruction = (
            "Bạn là một MC Livestream bán hàng vui nhộn, thân thiện, tràn đầy năng lượng.\n"
            "Nhiệm vụ của bạn là trả lời bình luận của khách hàng thật ngắn gọn (tối đa 2 câu, khoảng 30 từ),\n"
            "phù hợp để đọc trực tiếp trên livestream. Câu trả lời cần cuốn hút, sử dụng tiếng Việt tự nhiên.\n"
            "Nếu khách hàng hỏi về một sản phẩm cụ thể, hãy dùng thông tin sản phẩm được cung cấp để trả lời.\n"
            "Nếu không có thông tin sản phẩm, trả lời xã giao lịch sự, cảm ơn họ đã tương tác và kêu gọi chốt đơn.\n\n"
            "[QUAN TRỌNG - TƯƠNG TÁC SỰ KIỆN PHÒNG LIVE (LIVE EVENTS)]\n"
            "Bạn cần phản hồi cực kỳ hào hứng khi khách hàng thực hiện các hành động sau:\n"
            "- Lượt theo dõi mới ('đã follow shop'): Chào đón nồng nhiệt, cảm ơn họ đã bấm theo dõi kênh shop.\n"
            "- Lượt chia sẻ ('đã chia sẻ livestream'): Cảm ơn sâu sắc và kêu gọi mọi người vào xem đông vui.\n"
            "- Quà tặng ('đã tặng [số lượng] [tên quà]'): Cực kỳ vui mừng, cảm ơn món quà ngọt ngào của họ.\n"
            "- Nhấp xem giỏ hàng ('đã click xem sản phẩm [mã]'): Hãy lập tức chào mời và thúc giục họ chốt đơn sản phẩm đó ngay vì số lượng có hạn.\n\n"
            "[QUAN TRỌNG - PHÂN TÍCH CẢM XÚC (SENTIMENT ANALYSIS)]\n"
            "Bạn bắt buộc phải phân tích cảm xúc của bình luận khách hàng thành một trong 4 loại sau:\n"
            "- 'vui': Nếu khách hàng vui vẻ, chào hỏi, khen ngợi shop, chốt đơn, tặng quà, follow, hoặc chia sẻ.\n"
            "- 'khó chịu': Nếu khách hàng phàn nàn, cáu gắt, chê sản phẩm đắt, chê giao hàng lâu hoặc chỉ trích shop.\n"
            "- 'nghi ngờ': Nếu khách hàng nghi ngờ chất lượng vải, hỏi kỹ nguồn gốc, sợ hàng giả hàng nhái hoặc chất lượng kém.\n"
            "- 'bình thường': Cho các câu hỏi thăm bình thường, hỏi size, hỏi ship một cách trung tính.\n\n"
            "Bạn BẮT BUỘC phải định dạng câu trả lời bắt đầu bằng mã cảm xúc như sau:\n"
            "[SENTIMENT: <vui/khó chịu/nghi ngờ/bình thường>] <Câu trả lời của MC>\n"
            "Ví dụ:\n"
            "- Khách hỏi: 'Áo này vải có pha nilon không?' -> Trả về: '[SENTIMENT: nghi ngờ] Dạ sản phẩm cotton 100% chị yên tâm nhé, không hề pha nilon nóng bí đâu ạ!'\n"
            "- Khách chốt: 'Chốt SP001 nha' -> Trả về: '[SENTIMENT: vui] Tuyệt vời quá! Cảm ơn anh/chị đã chốt đơn thành công Áo thun basic ạ!'\n"
            "Hãy luôn tuân thủ cấu trúc '[SENTIMENT: ...] ' ở đầu câu trả lời."
        )

        self.model = Config.GEMINI_MODEL
        self.setup_gemini()

    def setup_gemini(self):
        """Khởi tạo Gemini API nếu cấu hình khả dụng."""
        if Config.is_gemini_configured():
            try:
                # Khởi tạo client theo SDK google-genai mới
                self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
                self.api_configured = True
                logger.info("Cấu hình Gemini API (google-genai) thành công!")
            except Exception as e:
                logger.error(f"Lỗi khi cấu hình Gemini API: {e}")
                self.api_configured = False
                self.client = None
        else:
            logger.warning("Gemini API chưa được cấu hình. Hệ thống sẽ sử dụng Trình Phản Hồi Giả Lập.")
            self.api_configured = False
            self.client = None

    def generate_response(self, username: str, comment: str, product_info: Optional[Dict[str, Any]] = None, 
                          history_context: Optional[str] = None, is_checkout: bool = False, 
                          order_success: bool = False, order_error_reason: str = "",
                          order_history: Optional[List[Dict[str, Any]]] = None,
                          all_products: Optional[List[Dict[str, Any]]] = None) -> str:
        """Sinh câu trả lời dựa trên bình luận của khách hàng và thông tin sản phẩm (nếu có)."""
        if self.api_configured and self.client:
            try:
                prompt = f"Khách hàng tên '{username}' bình luận: '{comment}'\n"
                if history_context:
                    prompt += f"Lịch sử tương tác của khách hàng này:\n{history_context}\n(Hãy thân mật, chào đón khách quay lại nếu có lịch sử)\n"
                
                if product_info:
                    prompt += (
                        f"Thông tin sản phẩm đang được nhắc đến:\n"
                        f"- Mã sản phẩm: {product_info['code']}\n"
                        f"- Tên sản phẩm: {product_info['name']}\n"
                        f"- Giá bán: {product_info['price']:,.0f} VNĐ\n"
                        f"- Số lượng tồn kho: {product_info['quantity']} cái\n"
                        f"- Mô tả sản phẩm: {product_info['description']}\n"
                    )
                    # Cảnh báo hết hàng
                    if product_info['quantity'] <= 0:
                        prompt += (
                            f"\n[QUAN TRỌNG: SẢN PHẨM NÀY ĐÃ HẾT HÀNG]\n"
                            f"Số lượng tồn kho hiện tại là 0 cái. MC tuyệt đối không được mời chốt đơn hoặc giới thiệu mua sản phẩm '{product_info['name']}'.\n"
                            f"Hãy lịch sự thông báo sản phẩm đã hết hàng, xin lỗi họ và khéo léo mời họ tham khảo các sản phẩm khác đang bán chạy.\n"
                        )
                else:
                    prompt += "Không có thông tin sản phẩm cụ thể đi kèm."
 
                # Lịch sử đơn hàng để bán chéo (Cross-sell)
                if order_history:
                    prompt += "\nLịch sử mua hàng đã chốt thành công của khách hàng này:\n"
                    for order in order_history:
                        prompt += f"- Sản phẩm: {order['product_code']} - Giá: {order['price']:,.0f} VNĐ - Trạng thái: {order['status']} (Mua ngày: {order['created_at']})\n"
                else:
                    prompt += "\nKhách hàng này chưa từng mua sản phẩm nào trước đây.\n"

                # Danh sách tất cả sản phẩm khác để bán chéo
                if all_products:
                    prompt += "\nDanh sách tất cả sản phẩm khác đang bán trong kho để bạn gợi ý bán chéo (Cross-sell):\n"
                    for prod in all_products:
                        if prod['quantity'] > 0:
                            prompt += f"- [{prod['code']}] {prod['name']} (Giá: {prod['price']:,.0f} VNĐ, Tồn: {prod['quantity']}): {prod['description']}\n"

                # Chỉ thị gợi ý bán chéo
                prompt += (
                    f"\n[CHỈ THỊ GỢI Ý BÁN CHÉO - CROSS-SELL]\n"
                    f"MC hãy tận dụng triệt để lịch sử mua hàng cũ của khách hàng '{username}' để gợi ý giới thiệu sản phẩm liên quan.\n"
                    f"Ví dụ: Nếu khách hàng từng mua hoặc hỏi sản phẩm mã SP001, và hôm nay họ hỏi hoặc chốt quần SP002 hoặc hỏi gì khác, hãy khéo léo nói: "
                    f"'Lần trước anh/chị {username} đã mua/hỏi áo SP001 mặc rất hợp, hôm nay bên em có quần Jean Slimfit SP002 phối cùng cực ngầu luôn ạ!'.\n"
                    f"Lời thoại phải rất tự nhiên, vui vẻ, tạo cảm giác cá nhân hóa cao độ để tăng uy tín và kích thích mua sắm.\n"
                )

                if is_checkout:
                    if order_success:
                        prompt += (
                            f"\n[QUAN TRỌNG: CHỐT ĐƠN THÀNH CÔNG]\n"
                            f"Hệ thống đã tự động tạo đơn hàng thành công cho khách hàng '{username}' với sản phẩm này.\n"
                            f"Trạng thái đơn: 'Chờ xác nhận', số lượng: 1 cái. Tồn kho mới sau khi trừ là: {product_info['quantity']} cái.\n"
                            f"Hãy vui vẻ chúc mừng họ đã chốt đơn thành công, kêu gọi họ check inbox để xác nhận và hoàn tất đơn hàng.\n"
                        )
                    else:
                        prompt += (
                            f"\n[QUAN TRỌNG: CHỐT ĐƠN THẤT BẠI]\n"
                            f"Khách hàng muốn chốt đơn nhưng không thành công do lỗi: '{order_error_reason}'.\n"
                            f"Hãy lịch sự và nhẹ nhàng thông báo việc lên đơn thất bại vì lý do này (ví dụ: đã hết hàng tồn kho) và xin lỗi họ.\n"
                        )
                
                # Gọi API thông qua SDK google-genai mới
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction
                    )
                )
                return response.text.strip()
            except Exception as e:
                logger.error(f"Lỗi khi gọi Gemini API: {e}. Chuyển sang phản hồi giả lập.")
                # Fallback to local responder if API call fails
                return self._mock_response(username, comment, product_info, is_checkout, order_success, order_error_reason, order_history, all_products)
        else:
            return self._mock_response(username, comment, product_info, is_checkout, order_success, order_error_reason, order_history, all_products)


        
    def _mock_response_single(self, username: str, comment: str, product_info: Optional[Dict[str, Any]] = None,
                              is_checkout: bool = False, order_success: bool = False, order_error_reason: str = "",
                              order_history: Optional[List[Dict[str, Any]]] = None,
                              all_products: Optional[List[Dict[str, Any]]] = None) -> str:
        """Sinh câu trả lời đơn lẻ không kèm thẻ sentiment phục vụ cho trả lời gộp."""
        comment_lower = comment.lower()
        pronoun = predict_vietnamese_pronoun(username)
        
        # Giả lập logic cross-sell trước
        if order_history and any(o["product_code"] == "SP001" for o in order_history):
            if "sp002" in comment_lower or "phối" in comment_lower or "quần" in comment_lower or "kết hợp" in comment_lower:
                return f"Dạ chào {pronoun} {username}! Lần trước {pronoun} đã chốt Áo Thun Cotton Basic SP001 mặc rất mát và vừa vặn đúng không ạ? Hôm nay bên em có Quần Jean Slimfit SP002 phối cùng cực kỳ hợp bộ và thời trang luôn đó nha! {pronoun.capitalize()} chốt luôn SP002 mặc cùng nha!"
        
        # Nếu đây là sự kiện chốt đơn
        if is_checkout and product_info:
            if order_success:
                return f"Tuyệt vời quá! Chúc mừng {pronoun} {username} đã chốt đơn thành công sản phẩm {product_info['name']} nha! {pronoun.capitalize()} check inbox để em gửi thông tin chốt đơn nhé!"
            else:
                if "hết hàng" in order_error_reason.lower():
                    return f"Dạ rất tiếc {pronoun} {username} ơi, sản phẩm {product_info['name']} bên em vừa mới hết hàng mất rồi ạ. {pronoun.capitalize()} tham khảo mã khác nha!"
                elif "nhanh" in order_error_reason.lower():
                    return f"Dạ {pronoun} {username} ơi, bạn đang chốt đơn hơi nhanh đó ạ. Vui lòng đợi 10 giây giữa các lần chốt đơn nhé!"
                elif "gần đây" in order_error_reason.lower():
                    return f"Dạ {pronoun} {username} ơi, sản phẩm mã {product_info['code']} bạn đã chốt thành công gần đây rồi ạ. Vui lòng không chốt trùng nhé!"
                else:
                    return f"Dạ {pronoun} {username} ơi, hệ thống gặp chút lỗi khi chốt đơn {product_info['name']}. Em sẽ kiểm tra lại ngay ạ!"
        
        # Nếu có sản phẩm đi kèm
        if product_info:
            price_str = f"{product_info['price']:,.0f} đồng"
            if "giá" in comment_lower or "bao nhiêu" in comment_lower or "nhiêu" in comment_lower:
                return f"Dạ chào {pronoun} {username}, sản phẩm {product_info['name']} có giá cực kỳ ưu đãi chỉ {price_str} thôi ạ! {pronoun.capitalize()} chốt đơn ngay nhé!"
            elif "còn" in comment_lower or "số lượng" in comment_lower or "size" in comment_lower:
                return f"Dạ {product_info['name']} bên em hiện tại chỉ còn {product_info['quantity']} cái thôi ạ. {pronoun.capitalize()} {username} nhanh tay comment mã {product_info['code']} để bên em giữ hàng nhé!"
            elif "vải" in comment_lower or "mát" in comment_lower or "chất" in comment_lower or "cotton" in comment_lower:
                return f"Dạ chất vải của sản phẩm {product_info['name']} là thun cotton 100% cực kỳ mát mẻ, mịn màng và co giãn thoải mái lắm {pronoun} {username} ơi!"
            else:
                return f"Cảm ơn {pronoun} {username} đã quan tâm sản phẩm {product_info['name']}. Sản phẩm này bên em đang bán rất chạy với giá {price_str}. {pronoun.capitalize()} chốt đơn ngay hôm nay đi ạ!"
        
        # Nếu không có sản phẩm cụ thể
        words = comment_lower.split()
        if "chào" in comment_lower or "hello" in comment_lower or "hi" in words:
            return f"Em chào {pronoun} {username} nhé! Chúc {pronoun} một buổi xem livestream vui vẻ và săn được thật nhiều deal hời nha!"
        elif "ship" in comment_lower or "giao hàng" in comment_lower:
            return f"Dạ {pronoun} {username} ơi, shop bên em giao hàng toàn quốc luôn ạ, chỉ từ 2 đến 3 ngày là nhận được ngay thôi!"
        elif "uy tín" in comment_lower or "chất lượng" in comment_lower:
            return f"Dạ shop em cam kết hàng chuẩn chất lượng 100% {pronoun} {username} yên tâm đặt hàng nhé, được kiểm tra hàng thoải mái ạ!"
        else:
            return f"Cảm ơn {pronoun} {username} đã tương tác và ủng hộ livestream của em! {pronoun.capitalize()} có câu hỏi nào cứ comment bên dưới em giải đáp ngay nhé!"

    def _mock_response(self, username: str, comment: str, product_info: Optional[Dict[str, Any]] = None,
                       is_checkout: bool = False, order_success: bool = False, order_error_reason: str = "",
                       order_history: Optional[List[Dict[str, Any]]] = None,
                       all_products: Optional[List[Dict[str, Any]]] = None) -> str:
        """Sinh câu trả lời giả lập (offline/rule-based) khi không có API key."""
        comment_lower = comment.lower()
        
        # Phân tích sentiment giả lập dựa trên toàn bộ nội dung
        sentiment = "bình thường"
        if "chốt" in comment_lower or "mua" in comment_lower or "chào" in comment_lower or "hello" in comment_lower or "khen" in comment_lower or "đẹp" in comment_lower or "tuyệt vời" in comment_lower:
            sentiment = "vui"
        elif "lâu" in comment_lower or "chán" in comment_lower or "đắt" in comment_lower or "tệ" in comment_lower:
            sentiment = "khó chịu"
        elif "thật không" in comment_lower or "pha" in comment_lower or "giả" in comment_lower or "không thế" in comment_lower or "đúng là" in comment_lower or "hỏi kỹ" in comment_lower or "nghi ngờ" in comment_lower or "không?" in comment_lower:
            sentiment = "nghi ngờ"
            
        # Nếu đây là bình luận gộp từ nhiều nguồn/người dùng
        if "bình luận 1 từ" in comment_lower:
            import re
            lines = comment.split("\n")
            parsed_comments = []
            for line in lines:
                match = re.search(r"Bình luận \d+ từ (\w+) - Người dùng '([^']+)': \"([^\"]+)\"", line)
                if match:
                    parsed_comments.append({
                        "platform": match.group(1),
                        "username": match.group(2),
                        "comment": match.group(3)
                    })
            
            if parsed_comments:
                # 1. Gom nhóm/Deduplicate theo tên người dùng để tránh lặp đi lặp lại một người
                unique_users = []
                user_comments = {}
                for pc in parsed_comments:
                    u = pc["username"]
                    if u not in user_comments:
                        user_comments[u] = []
                        unique_users.append(u)
                    user_comments[u].append(pc)
                
                # 2. Xây dựng câu trả lời tự nhiên
                # Nếu chỉ có 1 người dùng gửi nhiều bình luận trùng/khác nhau trong đợt gộp
                if len(unique_users) == 1:
                    user = unique_users[0]
                    comms = user_comments[user]
                    first_comm = comms[0]["comment"]
                    
                    # Tìm sản phẩm liên quan cho bình luận đầu tiên
                    sub_p = None
                    if all_products:
                        for p in all_products:
                            if p["code"].lower() in first_comm.lower():
                                sub_p = p
                                break
                    
                    sub_ans = self._mock_response_single(user, first_comm, sub_p, is_checkout, order_success, order_error_reason, None, all_products)
                    return f"[SENTIMENT: {sentiment}] {sub_ans}"
                
                # Nếu có nhiều người dùng khác nhau trong lô gộp
                greetings = []
                actions = []
                user_greet_parts = []
                for u in unique_users:
                    u_pronoun = predict_vietnamese_pronoun(u)
                    user_greet_parts.append(f"{u_pronoun} {u}")
                user_names_str = " & ".join(user_greet_parts)
                greetings.append(f"Dạ em chào {user_names_str} nha!")
                
                for u in unique_users:
                    u_pronoun = predict_vietnamese_pronoun(u)
                    u_comms = user_comments[u]
                    rep_c = u_comms[0]
                    comm_text = rep_c["comment"]
                    comm_text_lower = comm_text.lower()
                    
                    sub_p = None
                    if all_products:
                        for p in all_products:
                            if p["code"].lower() in comm_text_lower:
                                sub_p = p
                                break
                    
                    checkout_keywords = ["chốt", "chot", "mua", "lấy", "lay", "order"]
                    is_user_checkout = any(kw in comm_text_lower for kw in checkout_keywords)
                    
                    if is_user_checkout and sub_p:
                        actions.append(f"Chúc mừng {u_pronoun} {u} đã chốt đơn {sub_p['name']} thành công, shop sẽ gửi thông tin chốt đơn ngay ạ.")
                    elif sub_p:
                        price_str = f"{sub_p['price']:,.0f} đồng"
                        if "giá" in comm_text_lower or "bao nhiêu" in comm_text_lower or "nhiêu" in comm_text_lower:
                            actions.append(f"Về mã {sub_p['code']} thì {sub_p['name']} bên em đang có giá cực kỳ ưu đãi chỉ {price_str} thôi ạ, {u_pronoun} {u} chốt ngay nha.")
                        elif "còn" in comm_text_lower or "số lượng" in comm_text_lower or "size" in comm_text_lower or "mát" in comm_text_lower or "vải" in comm_text_lower:
                            actions.append(f"Còn mẫu {sub_p['name']} vải thun cotton mặc mát mẻ co giãn tốt lắm ạ, {u_pronoun} {u} nhanh tay chốt kẻo hết nhé.")
                        else:
                            actions.append(f"Mã {sub_p['code']} {sub_p['name']} đang cực hot giá chỉ {price_str}, {u_pronoun} {u} tham khảo nhé.")
                    else:
                        if "ship" in comm_text_lower or "giao hàng" in comm_text_lower:
                            actions.append(f"Shop em giao hàng toàn quốc chỉ 2-3 ngày là tới nơi thôi {u_pronoun} {u} ơi.")
                        elif "chào" in comm_text_lower or "hello" in comm_text_lower:
                            pass # Đã chào ở trên đầu rồi
                        else:
                            actions.append(f"Cảm ơn {u_pronoun} {u} đã tương tác ủng hộ livestream nha.")
                
                combined_ans = " ".join(greetings + actions)
                return f"[SENTIMENT: {sentiment}] {combined_ans}"

        # Nếu là comment đơn bình thường
        ans = self._mock_response_single(username, comment, product_info, is_checkout, order_success, order_error_reason, order_history, all_products)
        return f"[SENTIMENT: {sentiment}] {ans}"

    def classify_moderation(self, comment: str) -> str:
        """Phân loại kiểm duyệt bình luận bằng AI (Gemini) hoặc bộ offline rule-based nâng cấp.
        
        Trả về 'SPAM' nếu chứa từ tục cách điệu hoặc spam link/quảng cáo đối thủ tinh vi.
        Trả về 'CLEAN' nếu bình luận bình thường lành mạnh.
        """
        if self.api_configured and self.client:
            try:
                prompt = (
                    "Bạn là bộ kiểm duyệt bình luận livestream tự động chuyên nghiệp.\n"
                    "Nhiệm vụ của bạn là phân tích bình luận của người dùng và phân loại thành một trong hai nhãn sau:\n"
                    "- 'SPAM': Nếu bình luận chứa từ ngữ thô tục tục tĩu (kể cả viết cách điệu như d-e-o, đ.m, l0n, đjt, đ.é.o, c*c, v.v.), hoặc chứa link spam quảng cáo đối thủ tinh vi (như shorturl, shopee/lazada của đối thủ, z a l o, số điện thoại lôi kéo, lh, v.v.), hoặc lôi kéo khách hàng sang mua ở shop khác.\n"
                    "- 'CLEAN': Nếu bình luận bình thường, văn minh, lịch sự, hỏi mua hàng, hoặc chào hỏi lành mạnh.\n\n"
                    "Bạn BẮT BUỘC chỉ trả về duy nhất một từ 'SPAM' hoặc 'CLEAN'. Không trả về thêm bất kỳ lời giải thích hay từ ngữ nào khác.\n\n"
                    f"Bình luận: \"{comment}\"\n"
                    "Nhãn: "
                )
                
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(max_output_tokens=5, temperature=0.0)
                )
                if response.text:
                    result = response.text.strip().upper()
                    if result in ["SPAM", "CLEAN"]:
                        return result

            except Exception as e:
                logger.error(f"Lỗi khi gọi AI classify_moderation: {e}")
                
        # Bộ phân loại offline nâng cấp dùng regex thông minh (Offline Fallback)
        import re
        comment_lower = comment.lower()
        
        # Bắt biến thể từ tục tinh vi
        bad_patterns = [
            r"\bđ[ịj]t\b", r"\bđ[e\. !]*[oóòỏõọ]\b", r"\bl[o0\. ]*n\b", r"\bc[ăa\* ]*c\b", r"\bđ[m\. ]\b", r"\bđ[j\. ]*t\b",
            r"\bđ[íìỉĩí\.]*m\b", r"\bđ[ĩìỉĩí\.]*e[m\. ]*", r"\bch[ửu\. ]*i\b", r"\bngu\b", r"\bkh[ốo]*n\s*n[ạa]n\b",
            r"\bd\s*e\s*o\b", r"\bl\s*0\s*n\b", r"\bc\s*a\s*c\b", r"\bd\s*e\s*0\b", r"\bđ\.m\b", r"\bđ\.é\.o\b", r"\bđ\!t\b",
            r"\bđ\s*j\s*t\b", r"\bc\*\s*c\b"
        ]
        
        # Bắt spam link ẩn, số điện thoại lôi kéo, hoặc link/shop đối thủ
        spam_patterns = [
            r"z\s*a\s*l\s*o", r"s\s*h\s*o\s*p\s*e\s*e", r"l[a-z0-9\. -]*[dđ]o[iì][\- ]*thu",
            r"zalo\.me", r"http", r"www\.", r"\.com", r"\.vn", r"\.net", 
            r"l[iì]nk[\s\-]*[dđ]o[iì][\- ]*th[uủ]", r"m[uủ]a[\s\-]*r[eẻ][\s\-]*h[oơ]n",
            r"\b[dđ]o[iì][\- ]*th[uủ]\b",
            # Bắt chuỗi số điện thoại cách điệu (ví dụ: 090 123 456, 0 9 0 1...)
            r"0[\s\.\-]*\d[\s\.\-]*\d[\s\.\-]*\d[\s\.\-]*\d[\s\.\-]*\d[\s\.\-]*\d[\s\.\-]*\d[\s\.\-]*\d"
        ]
        
        for pat in bad_patterns + spam_patterns:
            if re.search(pat, comment_lower):
                return "SPAM"
        return "CLEAN"

