"""
B2BI 服务集成模块
"""
import boto3
import json

b2bi = boto3.client('b2bi', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
sts = boto3.client('sts', region_name='us-east-1')
ACCOUNT_ID = sts.get_caller_identity()['Account']
BUCKET = f'edi-demo-{ACCOUNT_ID}'

def parse_edi_with_b2bi(edi_type: str, s3_key: str) -> dict:
    """使用 B2BI 解析 EDI 文件"""
    ts_map = {'940': 'X12_940', '943': 'X12_943', '944': 'X12_944', '945': 'X12_945', '846': 'X12_846'}
    ts = ts_map.get(edi_type)
    if not ts:
        return {'error': f'不支持: {edi_type}'}
    
    try:
        resp = b2bi.test_parsing(
            ediType={'x12Details': {'transactionSet': ts, 'version': 'VERSION_4010'}},
            fileFormat='JSON',
            inputFile={'bucketName': BUCKET, 'key': s3_key}
        )
        return {'success': True, 'parsed': json.loads(resp['parsedFileContent']), 'service': 'AWS B2BI'}
    except Exception as e:
        return {'error': str(e)}

def parse_edi_content_with_b2bi(edi_type: str, content: str) -> dict:
    """直接解析 EDI 内容"""
    ts_map = {'940': 'X12_940', '943': 'X12_943', '944': 'X12_944', '945': 'X12_945', '846': 'X12_846'}
    ts = ts_map.get(edi_type)
    if not ts:
        return {'error': f'不支持: {edi_type}'}
    
    # 先存到S3临时文件
    tmp_key = f'tmp/test_{edi_type}.edi'
    s3.put_object(Bucket=BUCKET, Key=tmp_key, Body=content.encode())
    
    try:
        resp = b2bi.test_parsing(
            ediType={'x12Details': {'transactionSet': ts, 'version': 'VERSION_4010'}},
            fileFormat='JSON',
            inputFile={'bucketName': BUCKET, 'key': tmp_key}
        )
        return {'success': True, 'parsed': json.loads(resp['parsedFileContent']), 'service': 'AWS B2BI'}
    except Exception as e:
        return {'error': str(e)}
