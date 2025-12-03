from flask import Flask, request, jsonify
import requests
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置常量
WECHAT_API_URL = "http://127.0.0.1:7777/qianxun/httpapi"
ROBOT_WXID = "wxid_alwc6m6hw4rs22"
TARGET_WXID = "48138693151@chatroom"


def send_wechat_message(message):
    """
    发送消息到微信API
    
    Args:
        message: 要发送的消息内容
        
    Returns:
        dict: API响应结果
    """
    try:
        # 构造请求URL
        url = f"{WECHAT_API_URL}?wxid={ROBOT_WXID}"
        
        # 构造请求体
        payload = {
            "type": "sendText2",
            "data": {
                "wxid": TARGET_WXID,
                "msg": message
            }
        }
        
        # 发送POST请求
        logger.info(f"发送消息到微信API: {message[:50]}...")
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"消息发送成功，响应: {result}")
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"发送消息失败: {str(e)}")
        return {"error": str(e)}


@app.route('/webhook', methods=['POST'])
def webhook_listener():
    """
    Webhook监听端点
    接收POST请求，提取消息内容并转发
    """
    try:
        # 获取请求数据
        data = request.get_json()
        logger.info(f"收到webhook消息: {data}")
        
        # 提取消息内容（根据实际webhook格式调整）
        # 这里假设消息在 data['message'] 或 data['msg'] 字段
        message = data.get('message') or data.get('msg') or data.get('content')
        
        if not message:
            # 如果没有找到消息字段，尝试将整个数据转为字符串
            message = str(data)
        
        # 转发消息到微信
        result = send_wechat_message(message)
        
        # 返回响应
        return jsonify({
            "status": "success",
            "message": "消息已转发",
            "wechat_response": result
        }), 200
        
    except Exception as e:
        logger.error(f"处理webhook请求失败: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route('/test', methods=['POST'])
def test_send():
    """
    测试端点，用于手动测试消息发送
    POST数据格式: {"message": "测试消息"}
    """
    try:
        data = request.get_json()
        message = data.get('message', '这是一条测试消息')
        result = send_wechat_message(message)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info("启动Webhook监听服务...")
    logger.info(f"监听地址: http://0.0.0.0:5001/webhook")
    logger.info(f"健康检查: http://0.0.0.0:5001/health")
    logger.info(f"测试接口: http://0.0.0.0:5001/test")
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5001, debug=False)