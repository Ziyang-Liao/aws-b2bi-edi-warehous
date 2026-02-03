"""
EDI 海外仓对接 Web 系统
"""
from flask import Flask, render_template_string, request, jsonify
import boto3
import json
from datetime import datetime
from edi_simulator import EDIGenerator, EDIParser, WarehouseEDISimulator

app = Flask(__name__)

ACCOUNT_ID = boto3.client('sts').get_caller_identity()['Account']
BUCKET = f"edi-demo-{ACCOUNT_ID}"
s3 = boto3.client('s3', region_name='us-east-1')

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>EDI 海外仓对接系统</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #232f3e 0%, #37475a 100%); color: white; padding: 20px; text-align: center; }
        .header h1 { font-size: 24px; }
        .container { max-width: 1400px; margin: 20px auto; padding: 0 20px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; }
        .card-header { background: #37475a; color: white; padding: 12px 16px; font-weight: 600; }
        .card-body { padding: 16px; }
        .form-group { margin-bottom: 12px; }
        .form-group label { display: block; margin-bottom: 4px; font-weight: 500; color: #333; font-size: 13px; }
        .form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
        .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 500; }
        .btn-primary { background: #ff9900; color: #111; }
        .btn-primary:hover { background: #ec7211; }
        .btn-success { background: #1e8900; color: white; }
        .btn-info { background: #0073bb; color: white; }
        .items-list { margin: 10px 0; }
        .item-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
        .item-row input { flex: 1; }
        .edi-content { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 12px; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; }
        .json-content { background: #f8f8f8; padding: 12px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 12px; max-height: 200px; overflow-y: auto; }
        .log-panel { margin-top: 20px; }
        .log-entry { padding: 10px; border-bottom: 1px solid #eee; display: flex; align-items: flex-start; gap: 12px; }
        .log-entry:last-child { border-bottom: none; }
        .log-time { color: #666; font-size: 12px; white-space: nowrap; }
        .log-type { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .log-type.outbound { background: #fff3cd; color: #856404; }
        .log-type.inbound { background: #d4edda; color: #155724; }
        .log-msg { flex: 1; font-size: 13px; }
        .status { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
        .status.success { background: #d4edda; color: #155724; }
        .status.pending { background: #fff3cd; color: #856404; }
        .tabs { display: flex; border-bottom: 2px solid #ddd; margin-bottom: 16px; }
        .tab { padding: 10px 20px; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; }
        .tab.active { border-bottom-color: #ff9900; font-weight: 600; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .file-list { max-height: 300px; overflow-y: auto; }
        .file-item { padding: 8px 12px; border-bottom: 1px solid #eee; cursor: pointer; display: flex; justify-content: space-between; }
        .file-item:hover { background: #f5f5f5; }
        .file-name { font-family: monospace; font-size: 13px; }
        .file-time { color: #666; font-size: 12px; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal.show { display: flex; align-items: center; justify-content: center; }
        .modal-content { background: white; border-radius: 8px; width: 90%; max-width: 800px; max-height: 80vh; overflow: hidden; }
        .modal-header { padding: 16px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; }
        .modal-body { padding: 16px; overflow-y: auto; max-height: calc(80vh - 60px); }
        .close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #666; }
        .flow-diagram { display: flex; align-items: center; justify-content: center; gap: 20px; padding: 20px; background: #f8f9fa; border-radius: 8px; margin-bottom: 20px; }
        .flow-box { padding: 15px 25px; border-radius: 8px; text-align: center; font-weight: 500; }
        .flow-seller { background: #e3f2fd; border: 2px solid #2196f3; }
        .flow-aws { background: #fff3e0; border: 2px solid #ff9800; }
        .flow-warehouse { background: #e8f5e9; border: 2px solid #4caf50; }
        .flow-arrow { font-size: 24px; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏭 EDI 海外仓对接系统</h1>
        <p style="margin-top:8px;opacity:0.8">AWS B2B Data Interchange 模拟演示</p>
    </div>
    
    <div class="container">
        <div class="flow-diagram">
            <div class="flow-box flow-seller">📦 卖家系统<br><small>发送 940/943</small></div>
            <div class="flow-arrow">→</div>
            <div class="flow-box flow-aws">☁️ AWS B2BI<br><small>EDI ↔ JSON</small></div>
            <div class="flow-arrow">→</div>
            <div class="flow-box flow-warehouse">🏭 海外仓<br><small>返回 944/945/846</small></div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-header">📤 发送 EDI 指令</div>
                <div class="card-body">
                    <div class="tabs">
                        <div class="tab active" onclick="switchTab('outbound', 0)">940 出库指令</div>
                        <div class="tab" onclick="switchTab('outbound', 1)">943 入库通知</div>
                    </div>
                    
                    <div id="outbound-tab-0" class="tab-content active">
                        <form id="form-940">
                            <div class="form-group">
                                <label>订单号</label>
                                <input type="text" name="order_number" value="PO{{ now }}" required>
                            </div>
                            <div class="form-group">
                                <label>收件人</label>
                                <input type="text" name="ship_to_name" value="John Doe" required>
                            </div>
                            <div class="form-group">
                                <label>地址</label>
                                <input type="text" name="ship_to_address" value="123 Main St, Los Angeles, CA 90001">
                            </div>
                            <div class="form-group">
                                <label>商品明细</label>
                                <div class="items-list" id="items-940">
                                    <div class="item-row">
                                        <input type="text" placeholder="SKU" value="SKU001">
                                        <input type="number" placeholder="数量" value="2" style="width:80px">
                                        <button type="button" class="btn" onclick="removeItem(this)">✕</button>
                                    </div>
                                </div>
                                <button type="button" class="btn" onclick="addItem('items-940')">+ 添加商品</button>
                            </div>
                            <button type="submit" class="btn btn-primary" style="width:100%;margin-top:10px">发送 940 出库指令</button>
                        </form>
                    </div>
                    
                    <div id="outbound-tab-1" class="tab-content">
                        <form id="form-943">
                            <div class="form-group">
                                <label>ASN 编号</label>
                                <input type="text" name="asn_number" value="ASN{{ now }}" required>
                            </div>
                            <div class="form-group">
                                <label>预计到货日期</label>
                                <input type="date" name="expected_date" value="2026-02-10">
                            </div>
                            <div class="form-group">
                                <label>发货方</label>
                                <input type="text" name="ship_from" value="China Supplier, Shenzhen">
                            </div>
                            <div class="form-group">
                                <label>商品明细</label>
                                <div class="items-list" id="items-943">
                                    <div class="item-row">
                                        <input type="text" placeholder="SKU" value="SKU001">
                                        <input type="number" placeholder="数量" value="100" style="width:80px">
                                        <button type="button" class="btn" onclick="removeItem(this)">✕</button>
                                    </div>
                                </div>
                                <button type="button" class="btn" onclick="addItem('items-943')">+ 添加商品</button>
                            </div>
                            <button type="submit" class="btn btn-primary" style="width:100%;margin-top:10px">发送 943 入库通知</button>
                        </form>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">📥 仓库响应模拟</div>
                <div class="card-body">
                    <div class="tabs">
                        <div class="tab active" onclick="switchTab('inbound', 0)">945 出库确认</div>
                        <div class="tab" onclick="switchTab('inbound', 1)">944 入库确认</div>
                        <div class="tab" onclick="switchTab('inbound', 2)">846 库存报告</div>
                    </div>
                    
                    <div id="inbound-tab-0" class="tab-content active">
                        <form id="form-945">
                            <div class="form-group">
                                <label>订单号</label>
                                <input type="text" name="order_number" placeholder="对应940的订单号">
                            </div>
                            <div class="form-group">
                                <label>快递单号</label>
                                <input type="text" name="tracking" value="1Z999AA10123456784">
                            </div>
                            <div class="form-group">
                                <label>承运商</label>
                                <select name="carrier">
                                    <option value="FEDEX">FedEx</option>
                                    <option value="UPS">UPS</option>
                                    <option value="USPS">USPS</option>
                                    <option value="DHL">DHL</option>
                                </select>
                            </div>
                            <button type="submit" class="btn btn-success" style="width:100%;margin-top:10px">模拟返回 945</button>
                        </form>
                    </div>
                    
                    <div id="inbound-tab-1" class="tab-content">
                        <form id="form-944">
                            <div class="form-group">
                                <label>ASN 编号</label>
                                <input type="text" name="asn_number" placeholder="对应943的ASN编号">
                            </div>
                            <div class="form-group">
                                <label>收货状态</label>
                                <select name="status">
                                    <option value="F">全部收货</option>
                                    <option value="P">部分收货</option>
                                </select>
                            </div>
                            <button type="submit" class="btn btn-success" style="width:100%;margin-top:10px">模拟返回 944</button>
                        </form>
                    </div>
                    
                    <div id="inbound-tab-2" class="tab-content">
                        <form id="form-846">
                            <p style="color:#666;margin-bottom:12px">模拟仓库返回当前库存快照</p>
                            <button type="submit" class="btn btn-info" style="width:100%">获取 846 库存报告</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card log-panel">
            <div class="card-header" style="display:flex;justify-content:space-between;align-items:center">
                <span>📋 交易日志</span>
                <button class="btn" onclick="refreshFiles()" style="padding:5px 10px;font-size:12px">🔄 刷新</button>
            </div>
            <div class="card-body">
                <div id="log-list" class="file-list">
                    <p style="color:#666;text-align:center;padding:20px">暂无交易记录</p>
                </div>
            </div>
        </div>
    </div>
    
    <div id="modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modal-title">EDI 详情</h3>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <h4 style="margin-bottom:8px">原始 EDI</h4>
                <div id="modal-edi" class="edi-content"></div>
                <h4 style="margin:16px 0 8px">解析结果 (JSON)</h4>
                <div id="modal-json" class="json-content"></div>
            </div>
        </div>
    </div>
    
    <script>
        function switchTab(group, idx) {
            document.querySelectorAll(`#${group}-tab-0, #${group}-tab-1, #${group}-tab-2`).forEach((el, i) => {
                if(el) el.classList.toggle('active', i === idx);
            });
            const tabs = document.querySelectorAll(`.tabs`)[group === 'outbound' ? 0 : 1].querySelectorAll('.tab');
            tabs.forEach((t, i) => t.classList.toggle('active', i === idx));
        }
        
        function addItem(containerId) {
            const container = document.getElementById(containerId);
            const row = document.createElement('div');
            row.className = 'item-row';
            row.innerHTML = `
                <input type="text" placeholder="SKU" value="">
                <input type="number" placeholder="数量" value="1" style="width:80px">
                <button type="button" class="btn" onclick="removeItem(this)">✕</button>
            `;
            container.appendChild(row);
        }
        
        function removeItem(btn) {
            btn.parentElement.remove();
        }
        
        function getItems(containerId) {
            const items = [];
            document.querySelectorAll(`#${containerId} .item-row`).forEach(row => {
                const inputs = row.querySelectorAll('input');
                if(inputs[0].value) {
                    items.push({ sku: inputs[0].value, quantity: parseInt(inputs[1].value) || 1 });
                }
            });
            return items;
        }
        
        document.getElementById('form-940').onsubmit = async (e) => {
            e.preventDefault();
            const form = e.target;
            const data = {
                type: '940',
                order_number: form.order_number.value,
                ship_to_name: form.ship_to_name.value,
                ship_to_address: form.ship_to_address.value,
                items: getItems('items-940')
            };
            await sendEDI(data);
        };
        
        document.getElementById('form-943').onsubmit = async (e) => {
            e.preventDefault();
            const form = e.target;
            const data = {
                type: '943',
                asn_number: form.asn_number.value,
                expected_date: form.expected_date.value.replace(/-/g, ''),
                ship_from: form.ship_from.value,
                items: getItems('items-943')
            };
            await sendEDI(data);
        };
        
        document.getElementById('form-945').onsubmit = async (e) => {
            e.preventDefault();
            const form = e.target;
            await sendEDI({
                type: '945',
                order_number: form.order_number.value,
                tracking: form.tracking.value,
                carrier: form.carrier.value
            });
        };
        
        document.getElementById('form-944').onsubmit = async (e) => {
            e.preventDefault();
            const form = e.target;
            await sendEDI({
                type: '944',
                asn_number: form.asn_number.value,
                status: form.status.value
            });
        };
        
        document.getElementById('form-846').onsubmit = async (e) => {
            e.preventDefault();
            await sendEDI({ type: '846' });
        };
        
        async function sendEDI(data) {
            try {
                const res = await fetch('/api/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await res.json();
                if(result.success) {
                    alert(`${data.type} 发送成功！`);
                    refreshFiles();
                } else {
                    alert('发送失败: ' + result.error);
                }
            } catch(err) {
                alert('请求失败: ' + err.message);
            }
        }
        
        async function refreshFiles() {
            const res = await fetch('/api/files');
            const files = await res.json();
            const container = document.getElementById('log-list');
            
            if(files.length === 0) {
                container.innerHTML = '<p style="color:#666;text-align:center;padding:20px">暂无交易记录</p>';
                return;
            }
            
            container.innerHTML = files.map(f => `
                <div class="file-item" onclick="viewFile('${f.key}')">
                    <div>
                        <span class="log-type ${f.direction}">${f.direction === 'outbound' ? '发送' : '接收'}</span>
                        <span class="file-name">${f.type} - ${f.name}</span>
                    </div>
                    <span class="file-time">${f.time}</span>
                </div>
            `).join('');
        }
        
        async function viewFile(key) {
            const res = await fetch('/api/file?key=' + encodeURIComponent(key));
            const data = await res.json();
            document.getElementById('modal-title').textContent = key.split('/').pop();
            document.getElementById('modal-edi').textContent = data.edi.replace(/~/g, '~\\n');
            document.getElementById('modal-json').textContent = JSON.stringify(data.parsed, null, 2);
            document.getElementById('modal').classList.add('show');
        }
        
        function closeModal() {
            document.getElementById('modal').classList.remove('show');
        }
        
        document.getElementById('modal').onclick = (e) => {
            if(e.target.id === 'modal') closeModal();
        };
        
        refreshFiles();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    now = datetime.now().strftime('%Y%m%d%H%M')
    return render_template_string(HTML.replace('{{ now }}', now))

@app.route('/api/send', methods=['POST'])
def send_edi():
    data = request.json
    simulator = WarehouseEDISimulator(BUCKET)
    generator = EDIGenerator()
    
    try:
        if data['type'] == '940':
            addr_parts = data.get('ship_to_address', '').split(',')
            order = {
                'order_number': data['order_number'],
                'ship_to': {
                    'name': data['ship_to_name'],
                    'address': addr_parts[0].strip() if addr_parts else '',
                    'city': addr_parts[1].strip() if len(addr_parts) > 1 else 'City',
                    'state': addr_parts[2].strip()[:2] if len(addr_parts) > 2 else 'CA',
                    'zip': addr_parts[2].strip()[3:].strip() if len(addr_parts) > 2 else '90001'
                },
                'items': data['items']
            }
            simulator.send_outbound_order(order)
            
        elif data['type'] == '943':
            asn = {
                'asn_number': data['asn_number'],
                'expected_date': data['expected_date'],
                'ship_from': {
                    'name': data.get('ship_from', 'Supplier'),
                    'address': '456 Factory Rd',
                    'city': 'Shenzhen', 'state': 'GD', 'zip': '518000', 'country': 'CN'
                },
                'items': data['items']
            }
            simulator.send_inbound_asn(asn)
            
        elif data['type'] == '945':
            items = [{'sku': 'SKU001', 'quantity': 1}]  # 简化
            simulator.simulate_945_response(data['order_number'], data['tracking'], items)
            
        elif data['type'] == '944':
            items = [{'sku': 'SKU001', 'quantity': 100}]
            simulator.simulate_944_response(data['asn_number'], items)
            
        elif data['type'] == '846':
            simulator.get_inventory()
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files')
def list_files():
    files = []
    try:
        for prefix in ['outbound/', 'inbound/']:
            resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
            for obj in resp.get('Contents', []):
                key = obj['Key']
                if key.endswith('.edi'):
                    name = key.split('/')[-1]
                    edi_type = name.split('_')[0]
                    files.append({
                        'key': key,
                        'name': name,
                        'type': edi_type,
                        'direction': 'outbound' if 'outbound' in key else 'inbound',
                        'time': obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                    })
    except:
        pass
    return jsonify(sorted(files, key=lambda x: x['time'], reverse=True))

@app.route('/api/file')
def get_file():
    key = request.args.get('key')
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
        edi = obj['Body'].read().decode('utf-8')
        
        # 解析
        parsed = {}
        if '945' in key:
            parsed = EDIParser.parse_945(edi)
        elif '944' in key:
            parsed = EDIParser.parse_944(edi)
        else:
            parsed = EDIParser.parse(edi)
            
        return jsonify({'edi': edi, 'parsed': parsed})
    except Exception as e:
        return jsonify({'edi': '', 'parsed': {'error': str(e)}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
