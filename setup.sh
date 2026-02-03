#!/bin/bash
# EDI Demo 环境搭建脚本

set -e

REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="edi-demo-${ACCOUNT_ID}"
PROFILE_NAME="overseas-warehouse"

echo "=== 创建 S3 存储桶 ==="
aws s3 mb s3://${BUCKET_NAME} --region ${REGION} 2>/dev/null || echo "桶已存在"

# 创建目录结构
aws s3api put-object --bucket ${BUCKET_NAME} --key inbound/
aws s3api put-object --bucket ${BUCKET_NAME} --key outbound/
aws s3api put-object --bucket ${BUCKET_NAME} --key processed/

echo "=== 创建 B2BI Profile ==="
PROFILE_ID=$(aws b2bi create-profile \
    --name "${PROFILE_NAME}" \
    --phone "1234567890" \
    --business-name "Demo Overseas Warehouse" \
    --logging ENABLED \
    --region ${REGION} \
    --query 'profileId' --output text 2>/dev/null || \
    aws b2bi list-profiles --region ${REGION} --query "profiles[?name=='${PROFILE_NAME}'].profileId" --output text)

echo "Profile ID: ${PROFILE_ID}"

echo "=== 创建 X12 945 Transformer (出库确认) ==="
TRANSFORMER_945=$(aws b2bi create-transformer \
    --name "X12-945-Outbound" \
    --file-format '{"x12":{"transactionSet":"X12_945","version":"VERSION_4010"}}' \
    --mapping-template "$(cat <<'MAPPING'
{
  "warehouseShipmentId": "$.ST.02",
  "orderNumber": "$.W06.02",
  "shipDate": "$.W06.04",
  "carrier": "$.W06.05",
  "trackingNumber": "$.W06.06",
  "items": {
    "$forEach": "$.W12",
    "sku": "$.01",
    "quantity": "$.02",
    "uom": "$.03"
  }
}
MAPPING
)" \
    --edi-type '{"x12Details":{"transactionSet":"X12_945","version":"VERSION_4010"}}' \
    --sample-document "ISA*00*          *00*          *ZZ*WAREHOUSE      *ZZ*SELLER         *231015*1200*U*00401*000000001*0*P*>~GS*SW*WAREHOUSE*SELLER*20231015*1200*1*X*004010~ST*945*0001~W06*N*PO123456**20231015*FEDEX*1Z999AA10123456784~W12*SKU001*10*EA~W12*SKU002*5*EA~SE*5*0001~GE*1*1~IEA*1*000000001~" \
    --region ${REGION} \
    --query 'transformerId' --output text 2>/dev/null) || echo "Transformer 可能已存在"

echo "=== 创建 X12 940 Transformer (出库指令) ==="
TRANSFORMER_940=$(aws b2bi create-transformer \
    --name "X12-940-Inbound" \
    --file-format '{"x12":{"transactionSet":"X12_940","version":"VERSION_4010"}}' \
    --mapping-template "$(cat <<'MAPPING'
{
  "orderNumber": "$.W05.01",
  "shipToName": "$.N1[?(@.01=='ST')].02",
  "shipToAddress": "$.N3.01",
  "shipToCity": "$.N4.01",
  "shipToState": "$.N4.02",
  "shipToZip": "$.N4.03",
  "items": {
    "$forEach": "$.W01",
    "sku": "$.07",
    "quantity": "$.01",
    "uom": "$.02"
  }
}
MAPPING
)" \
    --edi-type '{"x12Details":{"transactionSet":"X12_940","version":"VERSION_4010"}}' \
    --region ${REGION} \
    --query 'transformerId' --output text 2>/dev/null) || echo "Transformer 可能已存在"

echo "=== 设置完成 ==="
echo "S3 Bucket: ${BUCKET_NAME}"
echo "Profile ID: ${PROFILE_ID}"
