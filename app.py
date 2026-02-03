"""
海外仓 EDI 业务系统 - Web界面
"""
from flask import Flask, render_template_string, request, jsonify
from warehouse_service import *
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

# 启动定时任务
scheduler = BackgroundScheduler()
scheduler.add_job(func=sync_full_inventory, trigger="interval", hours=1, id='sync_inventory')
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# 启动时同步一次
sync_full_inventory()

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>海外仓 EDI 业务系统</title>
    <style>
        *{box-sizing:border-box;margin:0;padding:0}
        body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f0f2f5}
        .header{background:linear-gradient(135deg,#1a365d 0%,#2c5282 100%);color:#fff;padding:20px;display:flex;justify-content:space-between;align-items:center}
        .header h1{font-size:22px}
        .stats{display:flex;gap:20px}
        .stat{background:rgba(255,255,255,0.15);padding:8px 16px;border-radius:6px;text-align:center}
        .stat-num{font-size:20px;font-weight:700}
        .stat-label{font-size:11px;opacity:0.8}
        .container{max-width:1400px;margin:20px auto;padding:0 20px}
        .tabs{display:flex;gap:4px;margin-bottom:20px}
        .tab{padding:12px 24px;background:#fff;border:none;cursor:pointer;font-size:14px;border-radius:8px 8px 0 0;color:#666}
        .tab.active{background:#2c5282;color:#fff}
        .panel{display:none;background:#fff;border-radius:0 8px 8px 8px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
        .panel.active{display:block}
        .panel-header{padding:16px 20px;border-bottom:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center}
        .panel-body{padding:20px}
        .form-row{display:flex;gap:12px;margin-bottom:12px}
        .form-group{flex:1}
        .form-group label{display:block;margin-bottom:4px;font-size:13px;color:#4a5568}
        .form-group input,.form-group select{width:100%;padding:10px;border:1px solid #e2e8f0;border-radius:6px;font-size:14px}
        .btn{padding:10px 20px;border:none;border-radius:6px;cursor:pointer;font-size:14px;font-weight:500}
        .btn-primary{background:#2c5282;color:#fff}
        .btn-success{background:#276749;color:#fff}
        .btn-warning{background:#c05621;color:#fff}
        .btn-sm{padding:6px 12px;font-size:12px}
        table{width:100%;border-collapse:collapse}
        th,td{padding:12px;text-align:left;border-bottom:1px solid #e2e8f0}
        th{background:#f7fafc;font-weight:600;color:#4a5568;font-size:13px}
        tr:hover{background:#f7fafc}
        .badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600}
        .badge-success{background:#c6f6d5;color:#276749}
        .badge-warning{background:#feebc8;color:#c05621}
        .badge-info{background:#bee3f8;color:#2b6cb0}
        .badge-gray{background:#e2e8f0;color:#4a5568}
        .search-box{display:flex;gap:8px}
        .search-box input{flex:1;padding:10px;border:1px solid #e2e8f0;border-radius:6px}
        .items-container{border:1px solid #e2e8f0;border-radius:6px;padding:12px;margin-bottom:12px}
        .item-row{display:flex;gap:8px;margin-bottom:8px;align-items:center}
        .item-row input{flex:1;padding:8px;border:1px solid #e2e8f0;border-radius:4px}
        .quota-info{background:#ebf8ff;border:1px solid #90cdf4;padding:12px;border-radius:6px;margin-bottom:16px;font-size:13px}
        .modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1000}
        .modal.show{display:flex;align-items:center;justify-content:center}
        .modal-content{background:#fff;border-radius:12px;width:90%;max-width:700px;max-height:80vh;overflow:hidden}
        .modal-header{padding:16px 20px;border-bottom:1px solid #e2e8f0;display:flex;justify-content:space-between}
        .modal-body{padding:20px;overflow-y:auto;max-height:calc(80vh - 60px)}
        .close-btn{background:none;border:none;font-size:24px;cursor:pointer;color:#a0aec0}
        .edi-raw{background:#1a202c;color:#e2e8f0;padding:16px;border-radius:8px;font-family:monospace;font-size:12px;white-space:pre-wrap;max-height:200px;overflow-y:auto}
        .detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
        .detail-item{padding:8px 12px;background:#f7fafc;border-radius:6px}
        .detail-label{font-size:11px;color:#718096}
        .detail-value{font-size:14px;font-weight:500;color:#2d3748}
        .empty{text-align:center;padding:40px;color:#a0aec0}
        .refresh-time{font-size:12px;color:#a0aec0}
    </style>
</head>
<body>
    <div class="header">
        <h1>🏭 海外仓 EDI 业务系统</h1>
        <div class="stats">
            <div class="stat"><div class="stat-num" id="statInventory">-</div><div class="stat-label">库存查询剩余</div></div>
            <div class="stat"><div class="stat-num" id="statOrder">-</div><div class="stat-label">推单剩余</div></div>
            <div class="stat"><div class="stat-num" id="statPacking">-</div><div class="stat-label">箱单下载剩余</div></div>
        </div>
    </div>
    
    <div class="container">
        <div class="tabs">
            <button class="tab active" onclick="showPanel(0)">📦 库存管理</button>
            <button class="tab" onclick="showPanel(1)">📤 推送订单</button>
            <button class="tab" onclick="showPanel(2)">📥 入库管理</button>
            <button class="tab" onclick="showPanel(3)">📋 订单查询</button>
            <button class="tab" onclick="showPanel(4)">📜 EDI日志</button>
        </div>
        
        <!-- 库存管理 -->
        <div class="panel active" id="panel0">
            <div class="panel-header">
                <div>
                    <strong>库存列表</strong>
                    <span class="refresh-time" id="lastSync">上次同步: -</span>
                </div>
                <div class="search-box">
                    <input type="text" id="skuSearch" placeholder="输入SKU查询实时库存">
                    <button class="btn btn-primary" onclick="queryInventory()">实时查询</button>
                    <button class="btn btn-sm" onclick="loadInventory()">🔄</button>
                </div>
            </div>
            <div class="panel-body">
                <div class="quota-info">📊 全量库存每小时自动同步 | 实时查询限额: <b>300次/天</b> (100单×3次)</div>
                <table>
                    <thead><tr><th>SKU</th><th>总库存</th><th>可用库存</th><th>预留</th><th>更新时间</th><th>操作</th></tr></thead>
                    <tbody id="inventoryTable"><tr><td colspan="6" class="empty">加载中...</td></tr></tbody>
                </table>
            </div>
        </div>
        
        <!-- 推送订单 -->
        <div class="panel" id="panel1">
            <div class="panel-header"><strong>创建出库订单</strong></div>
            <div class="panel-body">
                <div class="quota-info">📤 推单限额: <b>300次/天</b> (100单×3次)</div>
                <form id="orderForm">
                    <div class="form-row">
                        <div class="form-group"><label>订单号 *</label><input name="order_id" id="orderId" required></div>
                        <div class="form-group"><label>收件人 *</label><input name="ship_to_name" value="John Doe" required></div>
                    </div>
                    <div class="form-row">
                        <div class="form-group"><label>地址 *</label><input name="ship_to_address" value="123 Main St" required></div>
                        <div class="form-group"><label>城市</label><input name="city" value="Los Angeles"></div>
                        <div class="form-group"><label>州</label><input name="state" value="CA" style="width:60px"></div>
                        <div class="form-group"><label>邮编</label><input name="zip" value="90001" style="width:100px"></div>
                    </div>
                    <div class="form-group">
                        <label>商品明细 *</label>
                        <div class="items-container" id="orderItems">
                            <div class="item-row">
                                <input placeholder="SKU" value="SKU001">
                                <input type="number" placeholder="数量" value="2" style="width:80px">
                                <button type="button" class="btn btn-sm" onclick="this.parentElement.remove()">✕</button>
                            </div>
                        </div>
                        <button type="button" class="btn btn-sm" onclick="addOrderItem()">+ 添加商品</button>
                    </div>
                    <button type="submit" class="btn btn-primary" style="width:100%;margin-top:12px">推送订单 (940)</button>
                </form>
            </div>
        </div>
        
        <!-- 入库管理 -->
        <div class="panel" id="panel2">
            <div class="panel-header">
                <strong>入库单管理</strong>
                <button class="btn btn-sm" onclick="loadInbounds()">🔄</button>
            </div>
            <div class="panel-body">
                <div class="quota-info">📥 入库限额: <b>300次/天</b> | 943 入库通知 → 944 入库确认</div>
                <div style="display:flex;gap:20px">
                    <div style="flex:1">
                        <h4 style="margin-bottom:12px">创建入库单 (943)</h4>
                        <form id="inboundForm">
                            <div class="form-row">
                                <div class="form-group"><label>入库单号 *</label><input name="asn_id" id="asnId" required></div>
                                <div class="form-group"><label>预计到货日期</label><input name="expected_date" type="date"></div>
                            </div>
                            <div class="form-group"><label>发货方</label><input name="ship_from" placeholder="供应商名称"></div>
                            <div class="form-group">
                                <label>入库商品 *</label>
                                <div class="items-container" id="inboundItems">
                                    <div class="item-row">
                                        <input placeholder="SKU" value="SKU001">
                                        <input type="number" placeholder="数量" value="100" style="width:80px">
                                        <button type="button" class="btn btn-sm" onclick="this.parentElement.remove()">✕</button>
                                    </div>
                                </div>
                                <button type="button" class="btn btn-sm" onclick="addInboundItem()">+ 添加商品</button>
                            </div>
                            <button type="submit" class="btn btn-primary" style="width:100%;margin-top:12px">发送入库通知 (943)</button>
                        </form>
                    </div>
                    <div style="flex:1">
                        <h4 style="margin-bottom:12px">入库单列表</h4>
                        <table>
                            <thead><tr><th>入库单号</th><th>状态</th><th>预计到货</th><th>操作</th></tr></thead>
                            <tbody id="inboundTable"><tr><td colspan="4" class="empty">暂无入库单</td></tr></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 订单查询 -->
        <div class="panel" id="panel3">
            <div class="panel-header">
                <strong>订单列表</strong>
                <div class="search-box">
                    <input type="text" id="orderSearch" placeholder="订单号">
                    <button class="btn btn-primary btn-sm" onclick="searchOrder()">查询</button>
                    <button class="btn btn-sm" onclick="loadOrders()">🔄</button>
                </div>
            </div>
            <div class="panel-body">
                <table>
                    <thead><tr><th>订单号</th><th>收件人</th><th>商品</th><th>状态</th><th>快递单号</th><th>创建时间</th><th>操作</th></tr></thead>
                    <tbody id="orderTable"><tr><td colspan="7" class="empty">暂无订单</td></tr></tbody>
                </table>
            </div>
        </div>
        
        <!-- EDI日志 -->
        <div class="panel" id="panel4">
            <div class="panel-header">
                <strong>EDI交易日志</strong>
                <button class="btn btn-sm" onclick="loadLogs()">🔄</button>
            </div>
            <div class="panel-body">
                <table>
                    <thead><tr><th>时间</th><th>类型</th><th>方向</th><th>单号</th><th>操作</th></tr></thead>
                    <tbody id="logTable"><tr><td colspan="5" class="empty">暂无记录</td></tr></tbody>
                </table>
            </div>
        </div>
    </div>
    
    <!-- 详情弹窗 -->
    <div id="modal" class="modal" onclick="if(event.target===this)closeModal()">
        <div class="modal-content">
            <div class="modal-header"><h3 id="modalTitle">详情</h3><button class="close-btn" onclick="closeModal()">&times;</button></div>
            <div class="modal-body" id="modalBody"></div>
        </div>
    </div>

<script>
function showPanel(i){document.querySelectorAll('.panel').forEach((p,j)=>p.classList.toggle('active',i===j));document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('active',i===j))}
function closeModal(){document.getElementById('modal').classList.remove('show')}
function addOrderItem(){document.getElementById('orderItems').insertAdjacentHTML('beforeend','<div class="item-row"><input placeholder="SKU"><input type="number" placeholder="数量" value="1" style="width:80px"><button type="button" class="btn btn-sm" onclick="this.parentElement.remove()">✕</button></div>')}

// 生成订单号
document.getElementById('orderId').value = 'ORD' + Date.now().toString().slice(-8);
document.getElementById('asnId').value = 'ASN' + Date.now().toString().slice(-8);

function addInboundItem(){document.getElementById('inboundItems').insertAdjacentHTML('beforeend','<div class="item-row"><input placeholder="SKU"><input type="number" placeholder="数量" value="50" style="width:80px"><button type="button" class="btn btn-sm" onclick="this.parentElement.remove()">✕</button></div>')}

// 加载库存
async function loadInventory(){
    const r = await fetch('/api/inventory');
    const d = await r.json();
    document.getElementById('lastSync').textContent = '上次同步: ' + (d.last_sync || '-');
    const tb = document.getElementById('inventoryTable');
    if(!d.items?.length){tb.innerHTML='<tr><td colspan="6" class="empty">暂无库存数据</td></tr>';return}
    tb.innerHTML = d.items.map(i=>`<tr>
        <td><b>${i.sku}</b></td>
        <td>${i.quantity}</td>
        <td style="color:${i.available<50?'#c53030':'#276749'}">${i.available}</td>
        <td>${i.reserved||0}</td>
        <td>${i.last_updated||'-'}</td>
        <td><button class="btn btn-sm btn-primary" onclick="queryInventory('${i.sku}')">实时查询</button></td>
    </tr>`).join('');
}

// 实时查询库存
async function queryInventory(sku){
    sku = sku || document.getElementById('skuSearch').value;
    if(!sku){alert('请输入SKU');return}
    const r = await fetch('/api/inventory/query?sku='+sku);
    const d = await r.json();
    if(d.error){alert(d.error);return}
    document.getElementById('modalTitle').textContent = 'SKU: ' + sku + ' 实时库存';
    document.getElementById('modalBody').innerHTML = `
        <div class="detail-grid">
            <div class="detail-item"><div class="detail-label">总库存</div><div class="detail-value">${d.quantity}</div></div>
            <div class="detail-item"><div class="detail-label">可用库存</div><div class="detail-value">${d.available}</div></div>
            <div class="detail-item"><div class="detail-label">预留</div><div class="detail-value">${d.reserved||0}</div></div>
            <div class="detail-item"><div class="detail-label">更新时间</div><div class="detail-value">${d.last_updated||'-'}</div></div>
        </div>`;
    document.getElementById('modal').classList.add('show');
    loadQuota();
}

// 推送订单
document.getElementById('orderForm').onsubmit = async e => {
    e.preventDefault();
    const f = e.target;
    const items = [...document.querySelectorAll('#orderItems .item-row')].map(r=>{
        const[s,q]=r.querySelectorAll('input');
        return s.value?{sku:s.value,quantity:+q.value||1}:null
    }).filter(Boolean);
    
    const r = await fetch('/api/order/push', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            order_id: f.order_id.value,
            ship_to_name: f.ship_to_name.value,
            ship_to_address: f.ship_to_address.value,
            city: f.city.value,
            state: f.state.value,
            zip: f.zip.value,
            items: items
        })
    });
    const d = await r.json();
    if(d.error){alert('失败: '+d.error);return}
    alert('订单推送成功！订单号: '+d.order_id);
    document.getElementById('orderId').value = 'ORD' + Date.now().toString().slice(-8);
    loadOrders();
    loadQuota();
};

// 加载订单
async function loadOrders(){
    const r = await fetch('/api/orders');
    const d = await r.json();
    const tb = document.getElementById('orderTable');
    if(!d.length){tb.innerHTML='<tr><td colspan="7" class="empty">暂无订单</td></tr>';return}
    tb.innerHTML = d.map(o=>`<tr>
        <td><b>${o.order_id}</b></td>
        <td>${o.ship_to_name}</td>
        <td>${o.items_count}个SKU</td>
        <td><span class="badge badge-${o.status==='shipped'?'success':'warning'}">${o.status==='shipped'?'已发货':'待处理'}</span></td>
        <td>${o.tracking_number||'-'}</td>
        <td>${o.created_at}</td>
        <td>
            <button class="btn btn-sm btn-primary" onclick="viewOrder('${o.order_id}')">详情</button>
            <button class="btn btn-sm btn-success" onclick="downloadPacking('${o.order_id}')">箱单</button>
            ${o.status!=='shipped'?`<button class="btn btn-sm btn-warning" onclick="simulateShip('${o.order_id}')">模拟发货</button>`:''}
        </td>
    </tr>`).join('');
}

// 查看订单详情
async function viewOrder(id){
    const r = await fetch('/api/order/'+id);
    const d = await r.json();
    document.getElementById('modalTitle').textContent = '订单详情: ' + id;
    document.getElementById('modalBody').innerHTML = `
        <div class="detail-grid">
            <div class="detail-item"><div class="detail-label">订单号</div><div class="detail-value">${d.order_id}</div></div>
            <div class="detail-item"><div class="detail-label">状态</div><div class="detail-value">${d.status}</div></div>
            <div class="detail-item"><div class="detail-label">收件人</div><div class="detail-value">${d.ship_to_name}</div></div>
            <div class="detail-item"><div class="detail-label">地址</div><div class="detail-value">${d.ship_to_address}</div></div>
            <div class="detail-item"><div class="detail-label">快递单号</div><div class="detail-value">${d.tracking_number||'-'}</div></div>
            <div class="detail-item"><div class="detail-label">承运商</div><div class="detail-value">${d.carrier||'-'}</div></div>
        </div>
        <h4 style="margin:16px 0 8px">商品明细</h4>
        <table><tr><th>SKU</th><th>数量</th></tr>${d.items?.map(i=>`<tr><td>${i.sku}</td><td>${i.quantity}</td></tr>`).join('')||''}</table>`;
    document.getElementById('modal').classList.add('show');
}

// 下载箱单
async function downloadPacking(id){
    const r = await fetch('/api/order/'+id+'/packing');
    const d = await r.json();
    if(d.error){alert(d.error);return}
    document.getElementById('modalTitle').textContent = '箱单: ' + id;
    document.getElementById('modalBody').innerHTML = d.map((p,i)=>`
        <div style="background:#f7fafc;padding:16px;border-radius:8px;margin-bottom:12px">
            <h4>📦 箱号 ${p.box_number||i+1}</h4>
            <div class="detail-grid" style="margin-top:8px">
                <div class="detail-item"><div class="detail-label">重量</div><div class="detail-value">${p.weight} kg</div></div>
                <div class="detail-item"><div class="detail-label">尺寸</div><div class="detail-value">${p.dimensions}</div></div>
            </div>
            <h5 style="margin:12px 0 4px">装箱明细</h5>
            <table><tr><th>SKU</th><th>数量</th></tr>${(typeof p.items==='string'?JSON.parse(p.items):p.items)?.map(i=>`<tr><td>${i.sku}</td><td>${i.quantity}</td></tr>`).join('')||''}</table>
        </div>
    `).join('');
    document.getElementById('modal').classList.add('show');
    loadQuota();
}

// 模拟发货
async function simulateShip(id){
    const tracking = 'TRK' + Date.now().toString().slice(-10);
    const r = await fetch('/api/order/'+id+'/ship', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tracking: tracking, carrier: 'FEDEX'})
    });
    const d = await r.json();
    if(d.error){alert(d.error);return}
    alert('发货成功！快递单号: ' + tracking);
    loadOrders();
}

// 加载EDI日志
async function loadLogs(){
    const r = await fetch('/api/logs');
    const d = await r.json();
    const tb = document.getElementById('logTable');
    if(!d.length){tb.innerHTML='<tr><td colspan="5" class="empty">暂无记录</td></tr>';return}
    const types = {'940':'出库指令','943':'入库通知','944':'入库确认','945':'出库确认','846':'库存报告'};
    tb.innerHTML = d.map(l=>`<tr>
        <td>${l.created_at}</td>
        <td><span class="badge badge-info">${l.edi_type}</span> ${types[l.edi_type]||''}</td>
        <td><span class="badge badge-${l.direction==='outbound'?'warning':'success'}">${l.direction==='outbound'?'发送':'接收'}</span></td>
        <td>${l.ref_number}</td>
        <td><button class="btn btn-sm btn-primary" onclick="viewLog(${l.id})">查看EDI</button></td>
    </tr>`).join('');
}

// 查看EDI日志
async function viewLog(id){
    const r = await fetch('/api/log/'+id);
    const d = await r.json();
    const types = {'940':'出库指令','943':'入库通知','944':'入库确认','945':'出库确认','846':'库存报告'};
    document.getElementById('modalTitle').textContent = d.edi_type + ' ' + (types[d.edi_type]||'');
    
    let b2biHtml = '';
    if(d.b2bi_parsed){
        try{
            const b2bi = typeof d.b2bi_parsed === 'string' ? JSON.parse(d.b2bi_parsed) : d.b2bi_parsed;
            b2biHtml = `<h4 style="margin:16px 0 8px;color:#276749">✅ AWS B2BI 解析结果</h4>
                <div style="background:#f0fff4;border:1px solid #9ae6b4;padding:12px;border-radius:6px;font-family:monospace;font-size:12px;max-height:200px;overflow-y:auto">${JSON.stringify(b2bi,null,2)}</div>`;
        }catch(e){}
    }
    
    document.getElementById('modalBody').innerHTML = `
        <div class="detail-grid">
            <div class="detail-item"><div class="detail-label">单号</div><div class="detail-value">${d.ref_number}</div></div>
            <div class="detail-item"><div class="detail-label">方向</div><div class="detail-value">${d.direction==='outbound'?'发送':'接收'}</div></div>
            <div class="detail-item"><div class="detail-label">时间</div><div class="detail-value">${d.created_at}</div></div>
            <div class="detail-item"><div class="detail-label">服务</div><div class="detail-value" style="color:#276749">AWS B2BI</div></div>
        </div>
        <h4 style="margin:16px 0 8px">EDI 原始报文</h4>
        <div class="edi-raw">${d.raw_content?.replace(/~/g,'~\\n')||'-'}</div>
        ${b2biHtml}`;
    document.getElementById('modal').classList.add('show');
}

// 加载配额
async function loadQuota(){
    const r = await fetch('/api/quota');
    const d = await r.json();
    document.getElementById('statInventory').textContent = d.inventory_query || '-';
    document.getElementById('statOrder').textContent = d.push_order || '-';
    document.getElementById('statPacking').textContent = d.packing_list || '-';
}

function searchOrder(){
    const v = document.getElementById('orderSearch').value;
    if(v) viewOrder(v);
}

// 初始化
loadInventory();
loadOrders();
loadInbounds();
loadLogs();
loadQuota();

// 入库单提交
document.getElementById('inboundForm').onsubmit = async e => {
    e.preventDefault();
    const f = e.target;
    const items = [...document.querySelectorAll('#inboundItems .item-row')].map(r=>{
        const[s,q]=r.querySelectorAll('input');
        return s.value?{sku:s.value,quantity:+q.value||1}:null
    }).filter(Boolean);
    
    const r = await fetch('/api/inbound/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            asn_id: f.asn_id.value,
            expected_date: f.expected_date.value?.replace(/-/g,'') || '',
            ship_from: f.ship_from.value,
            items: items
        })
    });
    const d = await r.json();
    if(d.error){alert('失败: '+d.error);return}
    alert('入库通知发送成功！单号: '+d.asn_id);
    document.getElementById('asnId').value = 'ASN' + Date.now().toString().slice(-8);
    loadInbounds();
    loadLogs();
};

// 加载入库单
async function loadInbounds(){
    const r = await fetch('/api/inbounds');
    const d = await r.json();
    const tb = document.getElementById('inboundTable');
    if(!d.length){tb.innerHTML='<tr><td colspan="4" class="empty">暂无入库单</td></tr>';return}
    tb.innerHTML = d.map(i=>`<tr>
        <td><b>${i.asn_id}</b></td>
        <td><span class="badge badge-${i.status==='received'?'success':'warning'}">${i.status==='received'?'已入库':'待收货'}</span></td>
        <td>${i.expected_date||'-'}</td>
        <td>
            <button class="btn btn-sm btn-primary" onclick="viewInbound('${i.asn_id}')">详情</button>
            ${i.status!=='received'?`<button class="btn btn-sm btn-success" onclick="confirmInbound('${i.asn_id}')">模拟入库</button>`:''}
        </td>
    </tr>`).join('');
}

// 查看入库单详情
async function viewInbound(id){
    const r = await fetch('/api/inbound/'+id);
    const d = await r.json();
    document.getElementById('modalTitle').textContent = '入库单详情: ' + id;
    document.getElementById('modalBody').innerHTML = `
        <div class="detail-grid">
            <div class="detail-item"><div class="detail-label">入库单号</div><div class="detail-value">${d.asn_id}</div></div>
            <div class="detail-item"><div class="detail-label">状态</div><div class="detail-value">${d.status==='received'?'已入库':'待收货'}</div></div>
            <div class="detail-item"><div class="detail-label">发货方</div><div class="detail-value">${d.ship_from||'-'}</div></div>
            <div class="detail-item"><div class="detail-label">预计到货</div><div class="detail-value">${d.expected_date||'-'}</div></div>
            <div class="detail-item"><div class="detail-label">实际入库</div><div class="detail-value">${d.received_date||'-'}</div></div>
        </div>
        <h4 style="margin:16px 0 8px">商品明细</h4>
        <table><tr><th>SKU</th><th>预期数量</th><th>实收数量</th></tr>${d.items?.map(i=>`<tr><td>${i.sku}</td><td>${i.expected_qty}</td><td>${i.received_qty||'-'}</td></tr>`).join('')||''}</table>`;
    document.getElementById('modal').classList.add('show');
}

// 模拟入库确认
async function confirmInbound(id){
    const r = await fetch('/api/inbound/'+id+'/confirm', {method: 'POST'});
    const d = await r.json();
    if(d.error){alert(d.error);return}
    alert('入库确认成功！库存已更新');
    loadInbounds();
    loadInventory();
    loadLogs();
}
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/inventory')
def api_inventory():
    conn = get_db()
    items = conn.execute("SELECT * FROM inventory ORDER BY sku").fetchall()
    last = conn.execute("SELECT MAX(last_updated) as t FROM inventory").fetchone()
    conn.close()
    return jsonify({
        'items': [dict(i) for i in items],
        'last_sync': last['t'] if last else None
    })

@app.route('/api/inventory/query')
def api_inventory_query():
    sku = request.args.get('sku')
    result, error = query_inventory_realtime(sku)
    if error:
        return jsonify({'error': error})
    return jsonify(result)

@app.route('/api/order/push', methods=['POST'])
def api_push_order():
    data = request.json
    order_id, error = push_order(data)
    if error:
        return jsonify({'error': error})
    return jsonify({'order_id': order_id})

@app.route('/api/orders')
def api_orders():
    conn = get_db()
    orders = conn.execute('''
        SELECT o.*, COUNT(oi.id) as items_count 
        FROM orders o LEFT JOIN order_items oi ON o.order_id = oi.order_id 
        GROUP BY o.order_id ORDER BY o.created_at DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(o) for o in orders])

@app.route('/api/order/<order_id>')
def api_order_detail(order_id):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
    items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    conn.close()
    if not order:
        return jsonify({'error': '订单不存在'})
    result = dict(order)
    result['items'] = [dict(i) for i in items]
    return jsonify(result)

@app.route('/api/order/<order_id>/packing')
def api_packing(order_id):
    result, error = get_packing_list(order_id)
    if error:
        return jsonify({'error': error})
    return jsonify(result)

@app.route('/api/order/<order_id>/ship', methods=['POST'])
def api_ship(order_id):
    data = request.json
    try:
        simulate_shipment_confirm(order_id, data['tracking'], data.get('carrier', 'FEDEX'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/logs')
def api_logs():
    conn = get_db()
    logs = conn.execute("SELECT * FROM edi_logs ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(l) for l in logs])

@app.route('/api/log/<int:log_id>')
def api_log_detail(log_id):
    conn = get_db()
    log = conn.execute("SELECT * FROM edi_logs WHERE id=?", (log_id,)).fetchone()
    conn.close()
    return jsonify(dict(log) if log else {})

@app.route('/api/quota')
def api_quota():
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    result = {}
    for api_type, limit in [('inventory_query', 300), ('push_order', 300), ('packing_list', 300), ('inbound_order', 300)]:
        count = conn.execute(
            "SELECT COUNT(*) FROM api_calls WHERE api_type=? AND date(called_at)=?",
            (api_type, today)
        ).fetchone()[0]
        result[api_type] = limit - count
    conn.close()
    return jsonify(result)

@app.route('/api/inbound/create', methods=['POST'])
def api_create_inbound():
    data = request.json
    asn_id, error = create_inbound_order(data)
    if error:
        return jsonify({'error': error})
    return jsonify({'asn_id': asn_id})

@app.route('/api/inbounds')
def api_inbounds():
    conn = get_db()
    inbounds = conn.execute("SELECT * FROM inbound_orders ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(i) for i in inbounds])

@app.route('/api/inbound/<asn_id>')
def api_inbound_detail(asn_id):
    conn = get_db()
    inbound = conn.execute("SELECT * FROM inbound_orders WHERE asn_id=?", (asn_id,)).fetchone()
    items = conn.execute("SELECT * FROM inbound_items WHERE asn_id=?", (asn_id,)).fetchall()
    conn.close()
    if not inbound:
        return jsonify({'error': '入库单不存在'})
    result = dict(inbound)
    result['items'] = [dict(i) for i in items]
    return jsonify(result)

@app.route('/api/inbound/<asn_id>/confirm', methods=['POST'])
def api_confirm_inbound(asn_id):
    try:
        simulate_inbound_confirm(asn_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
