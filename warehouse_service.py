"""
海外仓 EDI 业务系统
- 定时拉取库存（每小时）
- 实时查询库存
- 推送订单
- 下载箱单
集成 AWS B2B Data Interchange 服务
"""
import json
import boto3
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from edi_simulator import EDIGenerator, EDIParser, WarehouseEDISimulator
from b2bi_service import parse_edi_with_b2bi, parse_edi_content_with_b2bi

app = Flask(__name__)

# 配置
ACCOUNT_ID = boto3.client('sts').get_caller_identity()['Account']
BUCKET = f"edi-demo-{ACCOUNT_ID}"
DB_PATH = '/home/ec2-user/edi-demo/warehouse.db'

s3 = boto3.client('s3', region_name='us-east-1')
simulator = WarehouseEDISimulator(BUCKET)

# 初始化数据库
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 库存表
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        sku TEXT PRIMARY KEY,
        quantity INTEGER,
        available INTEGER,
        reserved INTEGER DEFAULT 0,
        last_updated TIMESTAMP
    )''')
    
    # 订单表
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        status TEXT,
        ship_to_name TEXT,
        ship_to_address TEXT,
        tracking_number TEXT,
        carrier TEXT,
        created_at TIMESTAMP,
        shipped_at TIMESTAMP
    )''')
    
    # 订单明细
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        sku TEXT,
        quantity INTEGER,
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    )''')
    
    # 箱单表
    c.execute('''CREATE TABLE IF NOT EXISTS packing_lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        box_number INTEGER,
        weight REAL,
        dimensions TEXT,
        items TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    )''')
    
    # 入库单表
    c.execute('''CREATE TABLE IF NOT EXISTS inbound_orders (
        asn_id TEXT PRIMARY KEY,
        status TEXT,
        ship_from TEXT,
        expected_date TEXT,
        received_date TEXT,
        created_at TIMESTAMP
    )''')
    
    # 入库单明细
    c.execute('''CREATE TABLE IF NOT EXISTS inbound_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asn_id TEXT,
        sku TEXT,
        expected_qty INTEGER,
        received_qty INTEGER DEFAULT 0,
        FOREIGN KEY (asn_id) REFERENCES inbound_orders(asn_id)
    )''')
    
    # API调用记录（用于限流统计）
    c.execute('''CREATE TABLE IF NOT EXISTS api_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        api_type TEXT,
        called_at TIMESTAMP
    )''')
    
    # EDI交易日志
    c.execute('''CREATE TABLE IF NOT EXISTS edi_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        edi_type TEXT,
        direction TEXT,
        ref_number TEXT,
        raw_content TEXT,
        parsed_data TEXT,
        created_at TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# API限流检查
def check_rate_limit(api_type, daily_limit):
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    count = conn.execute(
        "SELECT COUNT(*) FROM api_calls WHERE api_type=? AND date(called_at)=?",
        (api_type, today)
    ).fetchone()[0]
    conn.close()
    return count < daily_limit, daily_limit - count

def record_api_call(api_type):
    conn = get_db()
    conn.execute("INSERT INTO api_calls (api_type, called_at) VALUES (?, ?)", 
                 (api_type, datetime.now()))
    conn.commit()
    conn.close()

# 1. 全量库存拉取（定时任务）
def sync_full_inventory():
    """每小时执行一次，拉取全量库存 - 使用B2BI解析"""
    print(f"[{datetime.now()}] 开始同步全量库存...")
    
    # 模拟仓库返回846库存报告
    inventory_data = [
        {'sku': 'SKU001', 'quantity': 500, 'available': 480},
        {'sku': 'SKU002', 'quantity': 300, 'available': 290},
        {'sku': 'SKU003', 'quantity': 150, 'available': 150},
        {'sku': 'SKU004', 'quantity': 800, 'available': 750},
        {'sku': 'SKU005', 'quantity': 200, 'available': 180},
    ]
    
    # 生成846 EDI
    edi_content = simulator.generator.generate_846(inventory_data)
    s3_key = f"inbound/846_INV{datetime.now().strftime('%Y%m%d%H%M%S')}.edi"
    s3.put_object(Bucket=BUCKET, Key=s3_key, Body=edi_content.encode())
    
    # 使用 B2BI 解析
    b2bi_result = parse_edi_with_b2bi('846', s3_key)
    
    conn = get_db()
    for item in inventory_data:
        conn.execute('''INSERT OR REPLACE INTO inventory 
                       (sku, quantity, available, last_updated) 
                       VALUES (?, ?, ?, ?)''',
                    (item['sku'], item['quantity'], item['available'], datetime.now()))
    conn.commit()
    
    # 记录EDI日志，包含B2BI解析结果
    conn.execute('''INSERT INTO edi_logs (edi_type, direction, ref_number, raw_content, parsed_data, b2bi_parsed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('846', 'inbound', f"INV{datetime.now().strftime('%Y%m%d%H')}", 
                 edi_content, json.dumps(inventory_data), 
                 json.dumps(b2bi_result.get('parsed', {})), datetime.now()))
    conn.commit()
    conn.close()
    
    print(f"[{datetime.now()}] 库存同步完成，B2BI解析: {'成功' if b2bi_result.get('success') else '失败'}")

# 2. 实时查询库存
def query_inventory_realtime(sku):
    """实时查询单个SKU库存"""
    allowed, remaining = check_rate_limit('inventory_query', 300)  # 100单*3次
    if not allowed:
        return None, "今日查询次数已用完"
    
    record_api_call('inventory_query')
    
    # 模拟实时查询返回
    conn = get_db()
    row = conn.execute("SELECT * FROM inventory WHERE sku=?", (sku,)).fetchone()
    conn.close()
    
    if row:
        return dict(row), None
    return None, "SKU不存在"

# 3. 推送订单
def push_order(order_data):
    """推送出库订单到仓库 - 使用B2BI验证"""
    allowed, remaining = check_rate_limit('push_order', 300)  # 100单*3次
    if not allowed:
        return None, "今日推单次数已用完"
    
    record_api_call('push_order')
    
    order_id = order_data['order_id']
    conn = get_db()
    
    # 保存订单
    conn.execute('''INSERT INTO orders (order_id, status, ship_to_name, ship_to_address, created_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (order_id, 'pending', order_data['ship_to_name'], 
                 order_data['ship_to_address'], datetime.now()))
    
    # 保存订单明细
    for item in order_data['items']:
        conn.execute("INSERT INTO order_items (order_id, sku, quantity) VALUES (?, ?, ?)",
                    (order_id, item['sku'], item['quantity']))
    
    # 生成940 EDI
    edi_940 = simulator.send_outbound_order({
        'order_number': order_id,
        'ship_to': {
            'name': order_data['ship_to_name'],
            'address': order_data['ship_to_address'],
            'city': order_data.get('city', 'Los Angeles'),
            'state': order_data.get('state', 'CA'),
            'zip': order_data.get('zip', '90001')
        },
        'items': order_data['items']
    })
    
    # 使用 B2BI 解析验证940
    s3_key = f"outbound/940_{order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.edi"
    b2bi_result = parse_edi_content_with_b2bi('940', edi_940)
    
    # 记录EDI日志，包含B2BI解析结果
    conn.execute('''INSERT INTO edi_logs (edi_type, direction, ref_number, raw_content, parsed_data, b2bi_parsed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('940', 'outbound', order_id, edi_940, json.dumps(order_data),
                 json.dumps(b2bi_result.get('parsed', {})), datetime.now()))
    
    conn.commit()
    conn.close()
    
    return order_id, None

# 4. 下载箱单
def get_packing_list(order_id):
    """获取订单箱单"""
    allowed, remaining = check_rate_limit('packing_list', 300)  # 100单*3次
    if not allowed:
        return None, "今日下载次数已用完"
    
    record_api_call('packing_list')
    
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
    
    if not order:
        conn.close()
        return None, "订单不存在"
    
    # 获取或生成箱单
    packing = conn.execute("SELECT * FROM packing_lists WHERE order_id=?", (order_id,)).fetchall()
    
    if not packing:
        # 模拟生成箱单
        items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
        packing_data = {
            'order_id': order_id,
            'box_number': 1,
            'weight': 2.5,
            'dimensions': '30x20x15cm',
            'items': [{'sku': i['sku'], 'quantity': i['quantity']} for i in items]
        }
        conn.execute('''INSERT INTO packing_lists (order_id, box_number, weight, dimensions, items, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (order_id, 1, 2.5, '30x20x15cm', json.dumps(packing_data['items']), datetime.now()))
        conn.commit()
        packing = [packing_data]
    else:
        packing = [dict(p) for p in packing]
    
    conn.close()
    return packing, None

# 模拟仓库返回945确认
def simulate_shipment_confirm(order_id, tracking, carrier='FEDEX'):
    """模拟仓库返回945 - 使用B2BI解析"""
    conn = get_db()
    items = conn.execute("SELECT sku, quantity FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    items_list = [{'sku': i['sku'], 'quantity': i['quantity']} for i in items]
    
    edi_945 = simulator.simulate_945_response(order_id, tracking, items_list)
    
    # 使用 B2BI 解析945
    b2bi_result = parse_edi_content_with_b2bi('945', edi_945)
    
    conn.execute("UPDATE orders SET status='shipped', tracking_number=?, carrier=?, shipped_at=? WHERE order_id=?",
                (tracking, carrier, datetime.now(), order_id))
    
    conn.execute('''INSERT INTO edi_logs (edi_type, direction, ref_number, raw_content, parsed_data, b2bi_parsed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('945', 'inbound', order_id, edi_945, 
                 json.dumps({'tracking': tracking, 'carrier': carrier}),
                 json.dumps(b2bi_result.get('parsed', {})), datetime.now()))
    
    conn.commit()
    conn.close()
    return edi_945, b2bi_result

# 5. 创建入库单（发送943 ASN）
def create_inbound_order(asn_data):
    """创建入库单，发送943 ASN到仓库"""
    allowed, remaining = check_rate_limit('inbound_order', 300)
    if not allowed:
        return None, "今日入库次数已用完"
    
    record_api_call('inbound_order')
    
    asn_id = asn_data['asn_id']
    conn = get_db()
    
    # 保存入库单
    conn.execute('''INSERT INTO inbound_orders (asn_id, status, ship_from, expected_date, created_at)
                   VALUES (?, ?, ?, ?, ?)''',
                (asn_id, 'pending', asn_data.get('ship_from', ''), 
                 asn_data.get('expected_date', ''), datetime.now()))
    
    # 保存明细
    for item in asn_data['items']:
        conn.execute("INSERT INTO inbound_items (asn_id, sku, expected_qty) VALUES (?, ?, ?)",
                    (asn_id, item['sku'], item['quantity']))
    
    # 生成943 EDI
    edi_943 = simulator.generator.generate_943(asn_data)
    
    # B2BI解析验证
    b2bi_result = parse_edi_content_with_b2bi('943', edi_943)
    
    conn.execute('''INSERT INTO edi_logs (edi_type, direction, ref_number, raw_content, parsed_data, b2bi_parsed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('943', 'outbound', asn_id, edi_943, json.dumps(asn_data),
                 json.dumps(b2bi_result.get('parsed', {})), datetime.now()))
    
    conn.commit()
    conn.close()
    return asn_id, None

# 6. 模拟仓库返回944入库确认
def simulate_inbound_confirm(asn_id):
    """模拟仓库返回944入库确认"""
    conn = get_db()
    items = conn.execute("SELECT sku, expected_qty FROM inbound_items WHERE asn_id=?", (asn_id,)).fetchall()
    items_list = [{'sku': i['sku'], 'quantity': i['expected_qty']} for i in items]
    
    edi_944 = simulator.generator.generate_944(asn_id, items_list)
    
    # B2BI解析
    b2bi_result = parse_edi_content_with_b2bi('944', edi_944)
    
    # 更新入库单状态
    conn.execute("UPDATE inbound_orders SET status='received', received_date=? WHERE asn_id=?",
                (datetime.now().strftime('%Y-%m-%d'), asn_id))
    
    # 更新收货数量
    for item in items_list:
        conn.execute("UPDATE inbound_items SET received_qty=? WHERE asn_id=? AND sku=?",
                    (item['quantity'], asn_id, item['sku']))
    
    # 更新库存
    for item in items_list:
        conn.execute('''INSERT INTO inventory (sku, quantity, available, last_updated)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(sku) DO UPDATE SET 
                       quantity = quantity + ?, available = available + ?, last_updated = ?''',
                    (item['sku'], item['quantity'], item['quantity'], datetime.now(),
                     item['quantity'], item['quantity'], datetime.now()))
    
    conn.execute('''INSERT INTO edi_logs (edi_type, direction, ref_number, raw_content, parsed_data, b2bi_parsed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                ('944', 'inbound', asn_id, edi_944, json.dumps({'items': items_list}),
                 json.dumps(b2bi_result.get('parsed', {})), datetime.now()))
    
    conn.commit()
    conn.close()
    return edi_944, b2bi_result

init_db()
