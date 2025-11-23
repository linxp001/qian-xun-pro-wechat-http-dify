#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import requests
import json
from datetime import datetime

# ===== 全局配置 =====
# 关键字配置（可以根据需要修改）
KEYWORDS = ["error", "failed", "异常", "ERROR"]  # 支持多个关键字

# 日志文件路径
LOG_FILE_PATH = "/root/one-api/oneapi.log"

# 微信接口配置
WECHAT_API_URL = "http://office.3-uni.net:7777/qianxun/httpapi"
WECHAT_WXID = "wxid_alwc6m6hw4rs22"
WECHAT_CHATROOM = "48138693151@chatroom"


def send_wechat_message(message):
    """
    发送微信消息
    :param message: 要发送的消息内容
    :return: 是否发送成功
    """
    try:
        # 构造请求URL
        url = f"{WECHAT_API_URL}?wxid={WECHAT_WXID}"
        
        # 构造请求Body
        payload = {
            "type": "sendText2",
            "data": {
                "wxid": WECHAT_CHATROOM,
                "msg": message
            }
        }
        
        # 发送POST请求
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # 检查响应
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                print(f"[{datetime.now()}] 消息发送成功: {result.get('result', {}).get('sendId')}")
                return True
            else:
                print(f"[{datetime.now()}] 消息发送失败: {result.get('msg')}")
                return False
        else:
            print(f"[{datetime.now()}] HTTP请求失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[{datetime.now()}] 发送消息异常: {str(e)}")
        return False


def check_log_file():
    """
    检查日志文件中的内容
    """
    try:
        with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        print(f"[{datetime.now()}] 读取日志文件，共 {len(lines)} 行")
        
        # 检查是否有匹配关键字的行
        found_keyword = False
        matched_keyword = ""
        matched_line = ""
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # 检查是否匹配任何关键字
            for keyword in KEYWORDS:
                if keyword.lower() in line_stripped.lower():
                    found_keyword = True
                    matched_keyword = keyword
                    matched_line = line_stripped
                    print(f"[{datetime.now()}] 匹配到关键字 '{keyword}': {line_stripped[:100]}...")
                    break
            
            if found_keyword:
                break
        
        # 如果发现匹配的关键字，发送整个日志文件内容
        if found_keyword:
            full_content = ''.join(lines)
            print(f"[{datetime.now()}] 准备发送完整日志内容，共 {len(lines)} 行")
            send_wechat_message(full_content)
        else:
            print(f"[{datetime.now()}] 未发现匹配关键字的内容")
            
    except FileNotFoundError:
        print(f"[{datetime.now()}] 日志文件不存在: {LOG_FILE_PATH}")
    except Exception as e:
        print(f"[{datetime.now()}] 读取日志文件异常: {str(e)}")


def main():
    """
    主函数
    """
    print("=" * 60)
    print("日志监控微信通知程序")
    print("=" * 60)
    print(f"监控文件: {LOG_FILE_PATH}")
    print(f"关键字: {KEYWORDS}")
    print(f"微信机器人: {WECHAT_WXID}")
    print(f"目标群组: {WECHAT_CHATROOM}")
    print("=" * 60)
    
    # 执行一次检查
    check_log_file()
    
    print(f"[{datetime.now()}] 检查完成，程序退出")
    print("=" * 60)


if __name__ == "__main__":
    main()
