#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import requests
import json
import re
from datetime import datetime

# ===== 全局配置 =====
# 关键字配置（可以根据需要修改）
KEYWORDS = ["error", "failed", "异常"]  # 支持多个关键字

# 黑名单关键字配置（匹配到关键字的行中如果包含黑名单关键字，则不发送该行）
BLACKLIST_KEYWORDS = ["timeout", "测试", "已忽略", "test"]  # 支持多个黑名单关键字

# 日志文件路径
LOG_FILE_PATH = "/root/one-api/oneapi.log"

# 微信接口配置
WECHAT_API_URL = "http://office.3-uni.net:7777/qianxun/httpapi"
WECHAT_WXID = "wxid_alwc6m6hw4rs22"
WECHAT_CHATROOM = "34412824967@chatroom"

# 31位ID的正则表达式（匹配连续31个数字）
ID_PATTERN = re.compile(r'\b\d{31}\b')


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
        
        print(f"[{datetime.now()}] 读取日志文件,共 {len(lines)} 行")
        
        # 步骤1: 查找所有匹配KEYWORDS的行
        keyword_matched_lines = []
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # 检查是否匹配任何关键字
            for keyword in KEYWORDS:
                if keyword.lower() in line_stripped.lower():
                    keyword_matched_lines.append(line_stripped)
                    print(f"[{datetime.now()}] 匹配到关键字 '{keyword}': {line_stripped[:100]}...")
                    break
        
        print(f"[{datetime.now()}] 共找到 {len(keyword_matched_lines)} 行匹配关键字")
        
        # 步骤2: 从匹配的行中提取31位ID，并重新筛选包含这些ID的所有行
        extracted_ids = set()
        for line in keyword_matched_lines:
            # 查找31位ID
            match = ID_PATTERN.search(line)
            if match:
                id_value = match.group()
                extracted_ids.add(id_value)
                print(f"[{datetime.now()}] 提取到ID: {id_value}")
            else:
                print(f"[{datetime.now()}] 未找到31位ID，忽略: {line[:100]}...")
        
        print(f"[{datetime.now()}] 共提取到 {len(extracted_ids)} 个唯一ID")
        
        # 如果没有提取到任何ID，直接返回
        if not extracted_ids:
            print(f"[{datetime.now()}] 没有提取到任何ID，无内容发送")
            return
        
        # 从整个日志文件中筛选包含这些ID的所有行
        id_related_lines = []
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # 检查该行是否包含任何提取到的ID
            for id_value in extracted_ids:
                if id_value in line_stripped:
                    id_related_lines.append(line_stripped)
                    break
        
        print(f"[{datetime.now()}] 共找到 {len(id_related_lines)} 行包含提取的ID")
        
        # 步骤3: 过滤掉包含黑名单关键字的行
        final_lines = []
        for line in id_related_lines:
            # 检查是否包含黑名单关键字
            is_blacklisted = False
            for bl_keyword in BLACKLIST_KEYWORDS:
                if bl_keyword.lower() in line.lower():
                    is_blacklisted = True
                    print(f"[{datetime.now()}] 包含黑名单关键字 '{bl_keyword}'，跳过: {line[:100]}...")
                    break
            
            if not is_blacklisted:
                final_lines.append(line)
        
        print(f"[{datetime.now()}] 过滤黑名单后剩余 {len(final_lines)} 行")
        
        # 发送最终结果
        if final_lines:
            message = '\n'.join(final_lines)
            print(f"[{datetime.now()}] 准备发送 {len(final_lines)} 行内容")
            send_wechat_message(message)
        else:
            print(f"[{datetime.now()}] 没有符合条件的内容需要发送")
            
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
    print(f"黑名单关键字: {BLACKLIST_KEYWORDS}")
    print(f"微信机器人: {WECHAT_WXID}")
    print(f"目标群组: {WECHAT_CHATROOM}")
    print("=" * 60)
    
    # 执行一次检查
    check_log_file()
    
    print(f"[{datetime.now()}] 检查完成，程序退出")
    print("=" * 60)


if __name__ == "__main__":
    main()
