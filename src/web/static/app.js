// App.js for Web Dashboard Controls

// Helper function to escape HTML string to prevent XSS
function escapeHTML(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

// Lấy token bảo mật từ query params của URL hoặc sessionStorage
const urlParams = new URLSearchParams(window.location.search);
let token = urlParams.get('token') || sessionStorage.getItem('web_console_token');

if (!token) {
    token = prompt("Vui lòng nhập Token bảo mật (WEB_TOKEN) để truy cập Web Console:");
    if (token) {
        sessionStorage.setItem('web_console_token', token);
    } else {
        token = "unauthorized_fallback";
    }
} else {
    sessionStorage.setItem('web_console_token', token);
}

const wsUri = `ws://${window.location.host}/ws?token=${token}`;

let socket = null;
let reconnectTimer = null;

function connectWebSocket() {
    console.log("Đang kết nối WebSocket tới: " + wsUri);
    socket = new WebSocket(wsUri);

    socket.onopen = function() {
        console.log("WebSocket connected.");
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
    };

    socket.onmessage = function(event) {
        const state = JSON.parse(event.data);
        if (state.error === "Unauthorized") {
            alert("Token bảo mật không chính xác. Vui lòng nhấn OK để nhập lại!");
            sessionStorage.removeItem('web_console_token');
            window.location.href = window.location.pathname;
            return;
        }
        updateUI(state);
    };

    socket.onclose = function(event) {
        console.log("WebSocket disconnected. Reconnecting in 3s...");
        socket = null;
        if (!reconnectTimer) {
            reconnectTimer = setTimeout(connectWebSocket, 3000);
        }
        // Set offline statuses
        const obsStatus = document.getElementById("obs-status");
        if (obsStatus) {
            obsStatus.innerHTML = `<span class="dot red"></span> OBS: Offline (Mất kết nối server)`;
        }
    };

    socket.onerror = function(err) {
        console.error("WebSocket error:", err);
    };
}

function updateUI(state) {
    if (state.status === "loading") return;

    // 1. Update OBS Status
    const obsStatus = document.getElementById("obs-status");
    if (obsStatus) {
        if (state.obs_connected) {
            obsStatus.innerHTML = `<span class="dot green"></span> OBS: Connected (${state.obs_host}:${state.obs_port})`;
        } else {
            obsStatus.innerHTML = `<span class="dot red"></span> OBS: Disconnected`;
        }
    }

    // 2. Update TTS Status
    const ttsStatus = document.getElementById("tts-status");
    if (ttsStatus) {
        if (state.tts_is_playing) {
            ttsStatus.innerHTML = `<span class="dot yellow"></span> TTS: Đang nói...`;
        } else {
            ttsStatus.innerHTML = `<span class="dot green"></span> TTS: Sẵn sàng`;
        }
    }

    // Update VMC Renderer Status & Warning Banner
    const renStatus = document.getElementById("renderer-status");
    const renBanner = document.getElementById("renderer-warning-banner");
    
    if (renStatus && renBanner) {
        if (state.renderer_online) {
            renStatus.innerHTML = `<span class="dot green"></span> MC ảo: Sẵn sàng`;
            renBanner.style.display = "none";
        } else {
            renStatus.innerHTML = `<span class="dot red"></span> MC ảo: Offline`;
            renBanner.style.display = "flex";
        }
    }

    // 3. Update Queue Counters
    if (state.queue_sizes) {
        const qHigh = document.getElementById("q-high-num");
        const qMed = document.getElementById("q-med-num");
        const qLow = document.getElementById("q-low-num");
        if (qHigh) qHigh.innerText = state.queue_sizes.high;
        if (qMed) qMed.innerText = state.queue_sizes.medium;
        if (qLow) qLow.innerText = state.queue_sizes.low;
    }

    // 4. Update Connectors (Read-Only Badges for Web Console security)
    if (state.connectors) {
        // TikTok
        const tkBadge = document.getElementById("badge-tiktok");
        if (tkBadge) {
            if (state.connectors.tiktok) {
                tkBadge.innerText = "ONLINE";
                tkBadge.className = "status-badge online";
            } else {
                tkBadge.innerText = "OFFLINE";
                tkBadge.className = "status-badge offline";
            }
        }
        // Facebook
        const fbBadge = document.getElementById("badge-facebook");
        if (fbBadge) {
            if (state.connectors.facebook) {
                fbBadge.innerText = "ONLINE";
                fbBadge.className = "status-badge online";
            } else {
                fbBadge.innerText = "OFFLINE";
                fbBadge.className = "status-badge offline";
            }
        }
        // YouTube
        const ytBadge = document.getElementById("badge-youtube");
        if (ytBadge) {
            if (state.connectors.youtube) {
                ytBadge.innerText = "ONLINE";
                ytBadge.className = "status-badge online";
            } else {
                ytBadge.innerText = "OFFLINE";
                ytBadge.className = "status-badge offline";
            }
        }
    }

    // 5. Update Products
    const prodContainer = document.getElementById("products-container");
    if (prodContainer) {
        if (state.products && state.products.length > 0) {
            prodContainer.innerHTML = state.products.map(p => `
                <div class="product-item">
                    <div>
                        <div class="prod-name">${escapeHTML(p.name)} (${escapeHTML(p.code)})</div>
                        <div class="prod-qty">Tồn: ${p.quantity} | Scene: ${escapeHTML(p.obs_scene || 'Chưa đặt')}</div>
                    </div>
                    <div class="prod-price">${parseFloat(p.price).toLocaleString('vi-VN')}đ</div>
                </div>
            `).join("");
        } else {
            prodContainer.innerHTML = `<p class="empty-hint">Không có sản phẩm nào trong kho.</p>`;
        }
    }

    // 5b. Update TikTok Shop Cart
    const cartContainer = document.getElementById("web-cart-container");
    if (cartContainer && state.products) {
        if (state.products.length > 0) {
            cartContainer.innerHTML = state.products.map(p => {
                const isPinned = state.pinned_product_code === p.code;
                const isOutOfStock = p.quantity <= 0;
                
                let badgeHtml = "";
                let actionButtonHtml = "";
                
                if (isPinned) {
                    badgeHtml = `<span class="status-badge online animate-pulse" style="margin-left: 8px;">ĐANG GHIM</span>`;
                    actionButtonHtml = `<button class="emergency-btn-small" style="font-size: 11px; padding: 4px 8px; background-color: var(--danger-color);" onclick="unpinProduct()">Bỏ Ghim</button>`;
                } else {
                    if (isOutOfStock) {
                        badgeHtml = `<span class="status-badge offline" style="margin-left: 8px; background-color: rgba(243, 139, 168, 0.05); color: #7f849c;">HẾT HÀNG</span>`;
                        actionButtonHtml = `<button class="emergency-btn-small" style="font-size: 11px; padding: 4px 8px; background-color: #585b70; cursor: not-allowed;" disabled>Ghim</button>`;
                    } else {
                        actionButtonHtml = `<button class="emergency-btn-small" style="font-size: 11px; padding: 4px 8px; background-color: var(--primary-color); color: #11111b;" onclick="pinProduct('${escapeHTML(p.code)}')">Ghim</button>`;
                    }
                }
                
                return `
                    <div class="product-item" style="padding: 10px; margin-bottom: 2px;">
                        <div style="flex-grow: 1;">
                            <div class="prod-name" style="font-size: 13px;">${escapeHTML(p.name)} (${escapeHTML(p.code)}) ${badgeHtml}</div>
                            <div class="prod-qty" style="font-size: 11px;">Tồn kho: ${p.quantity} cái</div>
                        </div>
                        <div>
                            ${actionButtonHtml}
                        </div>
                    </div>
                `;
            }).join("");
        } else {
            cartContainer.innerHTML = `<p class="empty-hint">Không có sản phẩm nào để hiển thị.</p>`;
        }
    }
    
    // 5c. Update Live Activity Stream
    const activityFeed = document.getElementById("live-activity-feed");
    if (activityFeed) {
        if (state.live_events && state.live_events.length > 0) {
            activityFeed.innerHTML = state.live_events.map(e => {
                let icon = "🔔";
                let color = "var(--text-color)";
                
                if (e.type === "gift") {
                    icon = "🎁";
                    color = "#f5c2e7"; // Pink
                } else if (e.type === "follow") {
                    icon = "👤";
                    color = "#89b4fa"; // Blue
                } else if (e.type === "share") {
                    icon = "🔗";
                    color = "#cba6f7"; // Purple
                } else if (e.type === "cart_click") {
                    icon = "🛒";
                    color = "#f9e2af"; // Yellow
                } else if (e.type === "cart_update") {
                    icon = "📍";
                    color = "#a6e3a1"; // Green
                }
                
                return `
                    <div style="padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.02); line-height: 1.4; color: ${color};">
                        <span style="color: var(--text-muted); font-size: 10px; font-family: monospace; margin-right: 4px;">[${escapeHTML(e.timestamp)}]</span>
                        <span style="margin-right: 4px;">${icon}</span>
                        <strong style="color: #cdd6f4;">${escapeHTML(e.username)}</strong>
                        <span>${escapeHTML(e.details)}</span>
                    </div>
                `;
            }).reverse().join(""); // Show newest events at the top of the container
        } else {
            activityFeed.innerHTML = `<p class="empty-hint" style="margin: auto; font-style: italic;">Chưa có hoạt động nào...</p>`;
        }
    }

    // 5d. Update Simulator Options
    const simCartSelect = document.getElementById("sim-cart-product");
    if (simCartSelect && state.products) {
        if (simCartSelect.options.length !== state.products.length) {
            simCartSelect.innerHTML = state.products.map(p => `
                <option value="${escapeHTML(p.code)}">${escapeHTML(p.name)} (${escapeHTML(p.code)})</option>
              `).join("");
        }
    }


    // 6. Update Autopilot Level
    const autoSelect = document.getElementById("autopilot-level");
    if (autoSelect && state.autopilot_level !== undefined) {
        autoSelect.value = state.autopilot_level;
    }

    // 7. Update Pending Approvals (Level 1)
    const pendingContainer = document.getElementById("pending-approvals-container");
    if (pendingContainer) {
        if (state.pending_approvals && state.pending_approvals.length > 0) {
            pendingContainer.innerHTML = state.pending_approvals.map(item => {
                const escapedId = escapeHTML(item.id);
                return `
                    <div class="pending-item" data-id="${escapedId}">
                        <div class="pending-meta">
                            <span>👤 ${escapeHTML(item.username)} (${escapeHTML(item.platform)})</span>
                            <span style="color: ${item.is_checkout ? '#f38ba8' : '#89b4fa'}">
                                ${item.is_checkout ? '🛒 Chốt đơn' : '💬 Bình luận'}
                            </span>
                        </div>
                        <div class="pending-comment">
                            "${escapeHTML(item.comment)}"
                        </div>
                        <div class="pending-edit-area">
                            <textarea id="edit-ans-${escapedId}">${escapeHTML(item.answer)}</textarea>
                        </div>
                        <div class="pending-actions">
                            <button class="btn-approve" onclick="approveComment('${escapedId}')">Duyệt Phát (Enter)</button>
                            <button class="btn-reject" onclick="rejectComment('${escapedId}')">Bỏ qua (Reject)</button>
                        </div>
                    </div>
                `;
            }).join("");
        } else {
            pendingContainer.innerHTML = `<p class="empty-hint">Không có câu trả lời nào đang chờ duyệt.</p>`;
        }
    }
}

// BIND ACTIONS
document.addEventListener("DOMContentLoaded", () => {
    connectWebSocket();

    // Tab switching logic
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            tab.classList.add('active');
            const target = tab.getAttribute('data-target');
            const targetEl = document.getElementById(target);
            if (targetEl) {
                targetEl.classList.add('active');
            }
        });
    });

    // Emergency Mute
    const emergencyBtn = document.getElementById("btn-emergency-mute");
    if (emergencyBtn) {
        emergencyBtn.addEventListener("click", () => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ action: "mute" }));
            }
        });
    }

    // Send Comment Sim (Moved from Desktop)
    const simForm = document.getElementById("comment-sim-form");
    if (simForm) {
        simForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const username = document.getElementById("sim-username").value;
            const comment = document.getElementById("sim-comment").value;

            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    action: "send_comment",
                    params: { username, comment }
                }));
            }
        });
    }

    // Send Override Voice
    const overrideBtn = document.getElementById("btn-send-override");
    if (overrideBtn) {
        overrideBtn.addEventListener("click", () => {
            const textInput = document.getElementById("override-text");
            const text = textInput.value.trim();

            if (text && socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    action: "override",
                    params: { text }
                }));
                textInput.value = ""; // Clear input after sending
            }
        });
    }

    // Autopilot Level Changed
    const autopilotSelect = document.getElementById("autopilot-level");
    if (autopilotSelect) {
        autopilotSelect.addEventListener("change", (e) => {
            const level = parseInt(e.target.value);
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    action: "set_autopilot_level",
                    params: { level }
                }));
            }
        });
    }
});

// GLOBAL APPROVE/REJECT ACTIONS FOR CLICK EVENTS
window.approveComment = function(id) {
    const approved_text = document.getElementById(`edit-ans-${id}`).value.trim();
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            action: "approve_comment",
            params: { id, approved_text }
        }));
    }
};

window.rejectComment = function(id) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            action: "reject_comment",
            params: { id }
        }));
    }
};

window.pinProduct = function(code) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            action: "pin_product",
            params: { product_code: code }
        }));
    }
};

window.unpinProduct = function() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            action: "unpin_product"
        }));
    }
};

window.simulateLiveEvent = function(type) {
    const usernameInput = document.getElementById("sim-event-user");
    const username = usernameInput ? usernameInput.value.trim() : "Khách Live";
    if (!username) return;
    
    let params = { event_type: type, username: username };
    
    if (type === "gift") {
        const giftSelect = document.getElementById("sim-gift-name");
        const giftCountInput = document.getElementById("sim-gift-count");
        params.gift_name = giftSelect ? giftSelect.value : "Hoa hồng";
        params.gift_count = giftCountInput ? parseInt(giftCountInput.value) : 1;
    } else if (type === "cart_click") {
        const productSelect = document.getElementById("sim-cart-product");
        params.product_code = productSelect ? productSelect.value : "SP001";
    }
    
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            action: "simulate_live_event",
            params: params
        }));
    }
};

window.triggerMCGesture = function(type, name) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            action: "trigger_mc_gesture",
            params: {
                type: type,
                name: name
            }
        }));
        console.log(`Sent manual MC gesture command: ${type} - ${name}`);
    }
};



// ==================== ROI ANALYTICS DASHBOARD ENGINE ====================
let productRoiChart = null;
let hourlyRevenueChart = null;

async function fetchAnalytics() {
    // Only fetch analytics if the Analytics tab is active to preserve bandwidth
    const analyticsTab = document.getElementById("analytics-section");
    if (analyticsTab && !analyticsTab.classList.contains("active")) {
        return;
    }
    
    try {
        const urlParams = new URLSearchParams(window.location.search);
        let token = urlParams.get('token') || sessionStorage.getItem('web_console_token') || "";
        const headers = { 'Authorization': `Bearer ${token}` };

        // Fetch Summary
        const resSummary = await fetch('/api/analytics/summary', { headers });
        const summary = await resSummary.json();
        if (!summary.error) {
            document.getElementById("kpi-revenue").innerText = parseFloat(summary.total_revenue).toLocaleString('vi-VN') + "đ";
            document.getElementById("kpi-orders").innerText = summary.total_orders + " đơn";
            document.getElementById("kpi-cr").innerText = summary.overall_cr + "%";
            document.getElementById("kpi-bestseller").innerText = `${summary.best_seller.name}`;
            document.getElementById("kpi-bestseller").title = `${summary.best_seller.name} (Mã: ${summary.best_seller.code}, Bán: ${summary.best_seller.sold})`;
        }

        // Fetch Product ROI
        const resProducts = await fetch('/api/analytics/products', { headers });
        const products = await resProducts.json();
        if (!products.error) {
            updateProductRoiChart(products);
        }

        // Fetch Hourly Revenue
        const resHourly = await fetch('/api/analytics/hourly', { headers });
        const hourly = await resHourly.json();
        if (!hourly.error) {
            updateHourlyRevenueChart(hourly);
        }
    } catch (err) {
        console.error("Lỗi khi fetch dữ liệu analytics:", err);
    }
}

function renderProductRoiTableFallback(products) {
    const el = document.getElementById('productRoiChart');
    if (!el) return;
    const parent = el.parentElement;
    parent.innerHTML = `
        <h3 style="margin-top: 0; margin-bottom: 15px; font-size: 14px; color: #cdd6f4; text-align: center;">ROI Hiệu suất sản phẩm (Chế độ Offline Fallback)</h3>
        <div style="max-height: 220px; overflow-y: auto; font-size: 12px; color: #cdd6f4;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="border-bottom: 1px solid #313244; color: #a6adc8;">
                        <th style="padding: 6px;">Sản phẩm</th>
                        <th style="padding: 6px; text-align: right;">Doanh thu</th>
                        <th style="padding: 6px; text-align: right;">Tỷ lệ CR</th>
                    </tr>
                </thead>
                <tbody>
                    \${products.map(p => \`
                        <tr style="border-bottom: 1px solid #1e1e2e;">
                            <td style="padding: 6px;">\${escapeHTML(p.name)} (\${escapeHTML(p.code)})</td>
                            <td style="padding: 6px; text-align: right; color: #a6e3a1;">\${parseFloat(p.revenue).toLocaleString('vi-VN')}đ</td>
                            <td style="padding: 6px; text-align: right; color: #f9e2af;">\${p.conversion_rate}%</td>
                        </tr>
                    \`).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function updateProductRoiChart(products) {
    if (typeof Chart === 'undefined') {
        renderProductRoiTableFallback(products);
        return;
    }
    const labels = products.map(p => `${p.name} (${p.code})`);
    const revenues = products.map(p => p.revenue);
    const conversionRates = products.map(p => p.conversion_rate);

    if (productRoiChart) {
        productRoiChart.data.labels = labels;
        productRoiChart.data.datasets[0].data = revenues;
        productRoiChart.data.datasets[1].data = conversionRates;
        productRoiChart.update();
    } else {
        const el = document.getElementById('productRoiChart');
        if (!el) return;
        const ctx = el.getContext('2d');
        productRoiChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Doanh thu (đ)',
                        data: revenues,
                        backgroundColor: 'rgba(166, 227, 161, 0.6)',
                        borderColor: 'rgb(166, 227, 161)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Tỷ lệ chuyển đổi (%)',
                        data: conversionRates,
                        type: 'line',
                        borderColor: 'rgb(249, 226, 175)',
                        backgroundColor: 'rgba(249, 226, 175, 0.2)',
                        borderWidth: 2,
                        yAxisID: 'y1',
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: '#313244' },
                        ticks: { color: '#cdd6f4' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#cdd6f4', callback: value => value + '%' }
                    },
                    x: {
                        grid: { color: '#313244' },
                        ticks: { color: '#cdd6f4' }
                    }
                },
                plugins: {
                    legend: { labels: { color: '#cdd6f4' } }
                }
            }
        });
    }
}

function renderHourlyTableFallback(hourly) {
    const el = document.getElementById('hourlyRevenueChart');
    if (!el) return;
    const parent = el.parentElement;
    const activeSlots = hourly.filter(h => h.orders > 0 || h.revenue > 0);
    parent.innerHTML = `
        <h3 style="margin-top: 0; margin-bottom: 15px; font-size: 14px; color: #cdd6f4; text-align: center;">Doanh thu theo khung giờ (Chế độ Offline Fallback)</h3>
        <div style="max-height: 220px; overflow-y: auto; font-size: 12px; color: #cdd6f4;">
            \${activeSlots.length === 0 ? '<p style="text-align: center; color: #a6adc8; margin-top: 50px;">Chưa có dữ liệu khung giờ</p>' : \`
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="border-bottom: 1px solid #313244; color: #a6adc8;">
                        <th style="padding: 6px;">Khung giờ</th>
                        <th style="padding: 6px; text-align: right;">Đơn hàng</th>
                        <th style="padding: 6px; text-align: right;">Doanh thu</th>
                    </tr>
                </thead>
                <tbody>
                    \${activeSlots.map(h => \`
                        <tr style="border-bottom: 1px solid #1e1e2e;">
                            <td style="padding: 6px;">\${escapeHTML(h.hour_slot)}</td>
                            <td style="padding: 6px; text-align: right; color: #f5c2e7;">\${h.orders} đơn</td>
                            <td style="padding: 6px; text-align: right; color: #89b4fa;">\${parseFloat(h.revenue).toLocaleString('vi-VN')}đ</td>
                        </tr>
                    \`).join("")}
                </tbody>
            </table>
            \`}
        </div>
    `;
}

function updateHourlyRevenueChart(hourly) {
    if (typeof Chart === 'undefined') {
        renderHourlyTableFallback(hourly);
        return;
    }
    hourly.sort((a, b) => a.hour_slot.localeCompare(b.hour_slot));
    
    const labels = hourly.map(h => h.hour_slot);
    const revenues = hourly.map(h => h.revenue);
    const orders = hourly.map(h => h.orders);

    if (hourlyRevenueChart) {
        hourlyRevenueChart.data.labels = labels;
        hourlyRevenueChart.data.datasets[0].data = revenues;
        hourlyRevenueChart.data.datasets[1].data = orders;
        hourlyRevenueChart.update();
    } else {
        const el = document.getElementById('hourlyRevenueChart');
        if (!el) return;
        const ctx = el.getContext('2d');
        hourlyRevenueChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Doanh thu (đ)',
                        data: revenues,
                        borderColor: 'rgb(137, 180, 250)',
                        backgroundColor: 'rgba(137, 180, 250, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        yAxisID: 'y',
                        tension: 0.3
                    },
                    {
                        label: 'Số đơn hàng',
                        data: orders,
                        type: 'bar',
                        backgroundColor: 'rgba(245, 194, 231, 0.4)',
                        borderColor: 'rgb(245, 194, 231)',
                        borderWidth: 1,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: '#313244' },
                        ticks: { color: '#cdd6f4' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#cdd6f4', stepSize: 1 }
                    },
                    x: {
                        grid: { color: '#313244' },
                        ticks: { color: '#cdd6f4' }
                    }
                },
                plugins: {
                    legend: { labels: { color: '#cdd6f4' } }
                }
            }
        });
    }
}

// Khởi tạo vòng lặp tự động cập nhật Analytics
document.addEventListener("DOMContentLoaded", () => {
    fetchAnalytics();
    setInterval(fetchAnalytics, 5000);
});
