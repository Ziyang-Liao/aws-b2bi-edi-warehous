"""
EDI 海外仓对接模拟系统
支持 X12 940/943/944/945/846 等常见交易类型
"""
import json
import boto3
from datetime import datetime
from typing import Dict, List

class EDIGenerator:
    """生成 X12 EDI 报文"""
    
    def __init__(self, sender_id: str = "SELLER", receiver_id: str = "WAREHOUSE"):
        self.sender_id = sender_id.ljust(15)
        self.receiver_id = receiver_id.ljust(15)
        self.control_number = 1
    
    def _isa_header(self) -> str:
        now = datetime.now()
        return (f"ISA*00*          *00*          *ZZ*{self.sender_id}*ZZ*{self.receiver_id}*"
                f"{now.strftime('%y%m%d')}*{now.strftime('%H%M')}*U*00401*{self.control_number:09d}*0*P*>~")
    
    def _gs_header(self, func_id: str, group_control: int = 1) -> str:
        now = datetime.now()
        return (f"GS*{func_id}*{self.sender_id.strip()}*{self.receiver_id.strip()}*"
                f"{now.strftime('%Y%m%d')}*{now.strftime('%H%M')}*{group_control}*X*004010~")
    
    def generate_940(self, order: Dict) -> str:
        """生成 940 出库指令"""
        segments = [
            self._isa_header(),
            self._gs_header("OW"),
            f"ST*940*0001~",
            f"W05*N*{order['order_number']}~",
            f"N1*ST*{order['ship_to']['name']}~",
            f"N3*{order['ship_to']['address']}~",
            f"N4*{order['ship_to']['city']}*{order['ship_to']['state']}*{order['ship_to']['zip']}*US~",
        ]
        
        seg_count = 5
        for item in order['items']:
            segments.append(f"W01*{item['quantity']}*{item.get('uom', 'EA')}*****{item['sku']}~")
            seg_count += 1
        
        segments.extend([
            f"SE*{seg_count + 1}*0001~",
            "GE*1*1~",
            f"IEA*1*{self.control_number:09d}~"
        ])
        
        self.control_number += 1
        return "".join(segments)
    
    def generate_943(self, asn: Dict) -> str:
        """生成 943 入库通知 (ASN)"""
        segments = [
            self._isa_header(),
            self._gs_header("WA"),
            f"ST*943*0001~",
            f"W06*N*{asn['asn_id']}**{asn.get('expected_date', '')}~",
        ]
        
        seg_count = 2  # ST + W06
        
        # 发货方信息（可选）
        if asn.get('ship_from'):
            segments.append(f"N1*SF*{asn['ship_from']}~")
            seg_count += 1
        
        for item in asn['items']:
            segments.append(f"W07*{item['quantity']}*{item.get('uom', 'EA')}*****{item['sku']}~")
            seg_count += 1
        
        segments.extend([
            f"SE*{seg_count + 1}*0001~",  # +1 for SE itself
            "GE*1*1~",
            f"IEA*1*{self.control_number:09d}~"
        ])
        
        self.control_number += 1
        return "".join(segments)
    
    def generate_944(self, asn_id: str, items: List[Dict]) -> str:
        """生成 944 入库确认"""
        now = datetime.now()
        segments = [
            f"ISA*00*          *00*          *ZZ*WAREHOUSE      *ZZ*SELLER         *"
            f"{now.strftime('%y%m%d')}*{now.strftime('%H%M')}*U*00401*000000001*0*P*>~",
            f"GS*RE*WAREHOUSE*SELLER*{now.strftime('%Y%m%d')}*{now.strftime('%H%M')}*1*X*004010~",
            f"ST*944*0001~",
            f"W17*F*{asn_id}*{now.strftime('%Y%m%d')}~",
        ]
        
        for item in items:
            segments.append(f"W07*{item['quantity']}*{item.get('uom', 'EA')}*****{item['sku']}~")
        
        segments.extend([
            f"SE*{3 + len(items)}*0001~",
            "GE*1*1~",
            "IEA*1*000000001~"
        ])
        
        return "".join(segments)
    
    def generate_846(self, inventory: List[Dict]) -> str:
        """生成 846 库存查询/报告"""
        segments = [
            self._isa_header(),
            self._gs_header("IB"),
            f"ST*846*0001~",
            f"BIA*00*00*{datetime.now().strftime('%Y%m%d')}~",
        ]
        
        seg_count = 2
        for item in inventory:
            segments.append(f"LIN**SK*{item['sku']}~")
            segments.append(f"QTY*33*{item['quantity']}~")  # 33 = On Hand
            if item.get('available'):
                segments.append(f"QTY*QA*{item['available']}~")  # QA = Available
            seg_count += 2 + (1 if item.get('available') else 0)
        
        segments.extend([
            f"SE*{seg_count + 1}*0001~",
            "GE*1*1~",
            f"IEA*1*{self.control_number:09d}~"
        ])
        
        self.control_number += 1
        return "".join(segments)


class EDIParser:
    """解析 X12 EDI 报文"""
    
    @staticmethod
    def parse(edi_content: str) -> Dict:
        """解析 EDI 报文为 JSON"""
        segments = edi_content.replace('\n', '').split('~')
        result = {'segments': [], 'transaction_type': None}
        
        for seg in segments:
            if not seg.strip():
                continue
            elements = seg.split('*')
            seg_id = elements[0]
            
            if seg_id == 'ST':
                result['transaction_type'] = elements[1]
            
            result['segments'].append({
                'id': seg_id,
                'elements': elements[1:]
            })
        
        return result
    
    @staticmethod
    def parse_945(edi_content: str) -> Dict:
        """解析 945 出库确认"""
        parsed = EDIParser.parse(edi_content)
        result = {'items': []}
        
        for seg in parsed['segments']:
            if seg['id'] == 'W06':
                result['shipment_id'] = seg['elements'][1] if len(seg['elements']) > 1 else None
                result['ship_date'] = seg['elements'][3] if len(seg['elements']) > 3 else None
                result['carrier'] = seg['elements'][4] if len(seg['elements']) > 4 else None
                result['tracking'] = seg['elements'][5] if len(seg['elements']) > 5 else None
            elif seg['id'] == 'W12':
                result['items'].append({
                    'sku': seg['elements'][0],
                    'quantity': int(seg['elements'][1]) if len(seg['elements']) > 1 else 0,
                    'uom': seg['elements'][2] if len(seg['elements']) > 2 else 'EA'
                })
        
        return result
    
    @staticmethod
    def parse_944(edi_content: str) -> Dict:
        """解析 944 入库确认"""
        parsed = EDIParser.parse(edi_content)
        result = {'items': []}
        
        for seg in parsed['segments']:
            if seg['id'] == 'W17':
                result['receipt_id'] = seg['elements'][1] if len(seg['elements']) > 1 else None
                result['receipt_date'] = seg['elements'][2] if len(seg['elements']) > 2 else None
            elif seg['id'] == 'W07':
                result['items'].append({
                    'sku': seg['elements'][6] if len(seg['elements']) > 6 else None,
                    'quantity': int(seg['elements'][0]) if seg['elements'][0] else 0,
                    'uom': seg['elements'][1] if len(seg['elements']) > 1 else 'EA'
                })
        
        return result


class WarehouseEDISimulator:
    """海外仓 EDI 模拟器"""
    
    def __init__(self, bucket_name: str, region: str = 'us-east-1'):
        self.s3 = boto3.client('s3', region_name=region)
        self.b2bi = boto3.client('b2bi', region_name=region)
        self.bucket = bucket_name
        self.generator = EDIGenerator()
    
    def send_outbound_order(self, order: Dict) -> str:
        """发送出库指令 (940)"""
        edi = self.generator.generate_940(order)
        key = f"outbound/940_{order['order_number']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.edi"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=edi.encode())
        print(f"已发送 940 出库指令: s3://{self.bucket}/{key}")
        return edi
    
    def send_inbound_asn(self, asn: Dict) -> str:
        """发送入库通知 (943)"""
        edi = self.generator.generate_943(asn)
        key = f"outbound/943_{asn['asn_number']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.edi"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=edi.encode())
        print(f"已发送 943 入库通知: s3://{self.bucket}/{key}")
        return edi
    
    def simulate_945_response(self, order_number: str, tracking: str, items: List[Dict]) -> str:
        """模拟仓库返回 945 出库确认"""
        edi = (f"ISA*00*          *00*          *ZZ*WAREHOUSE      *ZZ*SELLER         *"
               f"{datetime.now().strftime('%y%m%d')}*{datetime.now().strftime('%H%M')}*U*00401*000000001*0*P*>~"
               f"GS*SW*WAREHOUSE*SELLER*{datetime.now().strftime('%Y%m%d')}*{datetime.now().strftime('%H%M')}*1*X*004010~"
               f"ST*945*0001~"
               f"W06*N*{order_number}**{datetime.now().strftime('%Y%m%d')}*FEDEX*{tracking}~")
        
        for item in items:
            edi += f"W12*{item['sku']}*{item['quantity']}*{item.get('uom', 'EA')}~"
        
        # SE段计数: ST + W06 + W12*n + SE = 2 + n + 1 = 3 + n
        edi += f"SE*{3 + len(items)}*0001~GE*1*1~IEA*1*000000001~"
        
        key = f"inbound/945_{order_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}.edi"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=edi.encode())
        print(f"收到 945 出库确认: s3://{self.bucket}/{key}")
        return edi
    
    def simulate_944_response(self, asn_number: str, items: List[Dict]) -> str:
        """模拟仓库返回 944 入库确认"""
        edi = (f"ISA*00*          *00*          *ZZ*WAREHOUSE      *ZZ*SELLER         *"
               f"{datetime.now().strftime('%y%m%d')}*{datetime.now().strftime('%H%M')}*U*00401*000000001*0*P*>~"
               f"GS*RE*WAREHOUSE*SELLER*{datetime.now().strftime('%Y%m%d')}*{datetime.now().strftime('%H%M')}*1*X*004010~"
               f"ST*944*0001~"
               f"W17*F*{asn_number}*{datetime.now().strftime('%Y%m%d')}~")
        
        for item in items:
            edi += f"W07*{item['quantity']}*{item.get('uom', 'EA')}*****{item['sku']}~"
        
        edi += f"SE*{3 + len(items)}*0001~GE*1*1~IEA*1*000000001~"
        
        key = f"inbound/944_{asn_number}_{datetime.now().strftime('%Y%m%d%H%M%S')}.edi"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=edi.encode())
        print(f"收到 944 入库确认: s3://{self.bucket}/{key}")
        return edi
    
    def get_inventory(self) -> str:
        """请求库存报告 (846)"""
        # 模拟仓库返回的库存
        inventory = [
            {'sku': 'SKU001', 'quantity': 100, 'available': 95},
            {'sku': 'SKU002', 'quantity': 50, 'available': 50},
            {'sku': 'SKU003', 'quantity': 200, 'available': 180},
        ]
        edi = self.generator.generate_846(inventory)
        key = f"inbound/846_{datetime.now().strftime('%Y%m%d%H%M%S')}.edi"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=edi.encode())
        print(f"收到 846 库存报告: s3://{self.bucket}/{key}")
        return edi


def demo():
    """演示 EDI 交互流程"""
    import os
    
    account_id = boto3.client('sts').get_caller_identity()['Account']
    bucket = f"edi-demo-{account_id}"
    
    # 创建 S3 桶
    s3 = boto3.client('s3', region_name='us-east-1')
    try:
        s3.create_bucket(Bucket=bucket)
    except:
        pass
    
    simulator = WarehouseEDISimulator(bucket)
    
    print("\n" + "="*60)
    print("EDI 海外仓对接演示")
    print("="*60)
    
    # 1. 发送出库指令
    print("\n[1] 发送出库指令 (940)")
    order = {
        'order_number': 'PO20260203001',
        'ship_to': {
            'name': 'John Doe',
            'address': '123 Main St',
            'city': 'Los Angeles',
            'state': 'CA',
            'zip': '90001'
        },
        'items': [
            {'sku': 'SKU001', 'quantity': 2},
            {'sku': 'SKU002', 'quantity': 1}
        ]
    }
    edi_940 = simulator.send_outbound_order(order)
    print(f"EDI 内容:\n{edi_940[:200]}...")
    
    # 2. 模拟仓库返回出库确认
    print("\n[2] 仓库返回出库确认 (945)")
    edi_945 = simulator.simulate_945_response(
        'PO20260203001', 
        '1Z999AA10123456784',
        order['items']
    )
    parsed_945 = EDIParser.parse_945(edi_945)
    print(f"解析结果: {json.dumps(parsed_945, indent=2)}")
    
    # 3. 发送入库通知
    print("\n[3] 发送入库通知 (943)")
    asn = {
        'asn_number': 'ASN20260203001',
        'expected_date': '20260210',
        'ship_from': {
            'name': 'China Supplier',
            'address': '456 Factory Rd',
            'city': 'Shenzhen',
            'state': 'GD',
            'zip': '518000',
            'country': 'CN'
        },
        'items': [
            {'sku': 'SKU001', 'quantity': 100},
            {'sku': 'SKU003', 'quantity': 50}
        ]
    }
    simulator.send_inbound_asn(asn)
    
    # 4. 模拟仓库返回入库确认
    print("\n[4] 仓库返回入库确认 (944)")
    edi_944 = simulator.simulate_944_response('ASN20260203001', asn['items'])
    parsed_944 = EDIParser.parse_944(edi_944)
    print(f"解析结果: {json.dumps(parsed_944, indent=2)}")
    
    # 5. 获取库存报告
    print("\n[5] 获取库存报告 (846)")
    simulator.get_inventory()
    
    print("\n" + "="*60)
    print("演示完成！所有 EDI 文件已保存到 S3")
    print(f"S3 路径: s3://{bucket}/")
    print("="*60)


if __name__ == '__main__':
    demo()
