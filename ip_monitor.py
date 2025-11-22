import requests
import time
import os
import json
from datetime import datetime

# 配置参数
IP_CHECK_URL = "https://60s.3-uni.net/v2/ip?encoding=text"
WECHAT_API_URL = "http://127.0.0.1:7777/qianxun/httpapi"
WXID = "wxid_alwc6m6hw4rs22"
TARGET_WXID = "19986814732@chatroom"
IP_FILE = "current_ip.txt"
CHECK_INTERVAL = 60  # 10分钟 = 600秒

def get_current_ip():
    """获取当前IP地址"""
    try:
        response = requests.get(IP_CHECK_URL, timeout=10)
        response.raise_for_status()
        ip = response.text.strip()
        return ip
    except Exception as e:
        print(f"[{datetime.now()}] 获取IP地址失败: {e}")
        return None

def read_stored_ip():
    """读取存储的IP地址"""
    if os.path.exists(IP_FILE):
        try:
            with open(IP_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"[{datetime.now()}] 读取IP文件失败: {e}")
            return None
    return None

def save_ip(ip):
    """保存IP地址到文件"""
    try:
        with open(IP_FILE, 'w', encoding='utf-8') as f:
            f.write(ip)
        print(f"[{datetime.now()}] IP地址已保存到文件: {ip}")
        return True
    except Exception as e:
        print(f"[{datetime.now()}] 保存IP文件失败: {e}")
        return False

def send_wechat_message(new_ip):
    """发送微信消息"""
    try:
        # 构建请求URL
        url = f"{WECHAT_API_URL}?wxid={WXID}"
        
        # 构建请求体
        payload = {
            "type": "sendText2",
            "data": {
                "wxid": TARGET_WXID,
                "msg": f"健翔山庄IP地址刚刚发生变化，新IP为{new_ip}"
            }
        }
        
        # 发送POST请求
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('code') == 200:
            print(f"[{datetime.now()}] 微信消息发送成功: {new_ip}")
            return True
        else:
            print(f"[{datetime.now()}] 微信消息发送失败: {result.get('msg')}")
            return False
    except Exception as e:
        print(f"[{datetime.now()}] 发送微信消息异常: {e}")
        return False

def main():
    """主函数"""
    print(f"[{datetime.now()}] IP地址监控程序启动")
    print(f"检查间隔: {CHECK_INTERVAL}秒 ({CHECK_INTERVAL//60}分钟)")
    print("-" * 60)
    
    # 首次运行：获取并保存IP
    stored_ip = read_stored_ip()
    if stored_ip is None:
        print(f"[{datetime.now()}] 首次运行，获取初始IP地址...")
        current_ip = get_current_ip()
        if current_ip:
            save_ip(current_ip)
            print(f"[{datetime.now()}] 初始IP地址: {current_ip}")
        else:
            print(f"[{datetime.now()}] 无法获取初始IP地址，程序退出")
            return
    else:
        print(f"[{datetime.now()}] 当前存储的IP地址: {stored_ip}")
    
    # 循环检查IP变化
    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            
            print(f"[{datetime.now()}] 开始检查IP地址...")
            current_ip = get_current_ip()
            
            if current_ip is None:
                print(f"[{datetime.now()}] 跳过本次检查")
                continue
            
            stored_ip = read_stored_ip()
            
            if current_ip != stored_ip:
                print(f"[{datetime.now()}] IP地址发生变化!")
                print(f"  旧IP: {stored_ip}")
                print(f"  新IP: {current_ip}")
                
                # 保存新IP
                if save_ip(current_ip):
                    # 发送微信通知
                    send_wechat_message(current_ip)
            else:
                print(f"[{datetime.now()}] IP地址未变化: {current_ip}")
        
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 程序被用户中断")
            break
        except Exception as e:
            print(f"[{datetime.now()}] 发生异常: {e}")
            continue

if __name__ == "__main__":
    main()