import json
import requests
from flask import Flask, request, jsonify
import threading
import logging
from collections import defaultdict
from datetime import datetime
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 加载配置文件
def load_config():
    """
    加载配置文件,如果不存在则使用默认配置
    """
    config_path = 'config.json'
    default_config = {
        "bot_wxid": "",  # 新增:机器人wxid配置
        "dify": {
            "default": {
                "api_url": "http://192.168.1.25:54321/v1/chat-messages",
                "api_key": "app-ilRkWu2ERmqJmB1EQDkwLuyM",
                "timeout": 60,
                "description": "默认Dify应用(用于未配置的群聊和所有私聊)"
            },
            "group_mapping": {}
        },
        "weixin": {
            "api_url": "http://127.0.0.1:7777/qianxun/httpapi"
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "debug": False
        },
        "trigger_keywords": [
            "@AI小朋",
            "@叶若涵"
        ],
        "messages": {
            "empty_message_reply": "您好!我收到了您的@消息,请告诉我您想咨询什么内容。",
            "default_reply": "抱歉,我没有理解您的意思。",
            "service_unavailable": "抱歉,服务暂时不可用:"
        },
        "scheduled_tasks": []
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"Configuration loaded from {config_path}")
                return config
        else:
            # 创建默认配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            logger.info(f"Default configuration file created at {config_path}")
            return default_config
    except Exception as e:
        logger.error(f"Failed to load config file: {str(e)}, using default config")
        return default_config

# 加载配置
config = load_config()

# 从配置文件读取变量
WEIXIN_API_URL = config['weixin']['api_url']
TRIGGER_KEYWORDS = config['trigger_keywords']
MESSAGES = config['messages']
BOT_WXID = config.get('bot_wxid', '')  # 新增:从配置读取bot_wxid

# 存储会话ID的字典,格式: {from_wxid: conversation_id}
conversations = {}
# 存储锁,防止多线程同时修改同一会话
session_locks = defaultdict(threading.Lock)

def get_dify_config(wxid):
    """
    根据wxid获取对应的Dify配置
    如果是群聊且有专门配置,返回群聊配置;否则返回默认配置
    """
    # 检查是否为群聊,且在group_mapping中有配置
    if '@chatroom' in wxid and wxid in config['dify'].get('group_mapping', {}):
        dify_config = config['dify']['group_mapping'][wxid]
        logger.info(f"Using specific Dify config for group: {wxid}")
    else:
        dify_config = config['dify']['default']
        logger.info(f"Using default Dify config for: {wxid}")
    
    return dify_config

def send_to_dify(query_text, from_wxid):
    """
    发送消息到Dify并获取回复
    遇到404错误时会自动去掉conversation_id重试一次
    根据from_wxid自动选择对应的Dify配置
    """
    # 获取该wxid对应的Dify配置
    dify_config = get_dify_config(from_wxid)
    dify_api_url = dify_config['api_url']
    dify_api_key = dify_config['api_key']
    dify_timeout = dify_config['timeout']
    
    headers = {
        'Authorization': f'Bearer {dify_api_key}',
        'Content-Type': 'application/json'
    }
    
    # 获取该用户的会话ID
    with session_locks[from_wxid]:
        conversation_id = conversations.get(from_wxid, "")
        
        data = {
            "inputs": {},
            "query": query_text,
            "response_mode": "blocking",
            "conversation_id": conversation_id,
            "user": from_wxid
        }
        
        try:
            logger.info(f"Sending to Dify: user={from_wxid}, conversation_id={conversation_id}, api={dify_api_url}")
            response = requests.post(dify_api_url, headers=headers, json=data, timeout=dify_timeout)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Dify response received for user {from_wxid}")
            
            # 更新会话ID
            if 'conversation_id' in result and result['conversation_id']:
                conversations[from_wxid] = result['conversation_id']
                logger.info(f"Updated conversation_id for {from_wxid}: {result['conversation_id']}")
            
            return result.get('answer', MESSAGES['default_reply'])
            
        except requests.exceptions.HTTPError as e:
            # 检查是否是404错误
            if e.response.status_code == 404 and conversation_id:
                logger.warning(f"Received 404 error with conversation_id={conversation_id}, retrying without conversation_id")
                
                # 清除该用户的会话ID
                if from_wxid in conversations:
                    del conversations[from_wxid]
                    logger.info(f"Cleared conversation_id for {from_wxid}")
                
                # 重试:不带conversation_id
                retry_data = {
                    "inputs": {},
                    "query": query_text,
                    "response_mode": "blocking",
                    "conversation_id": "",  # 空字符串
                    "user": from_wxid
                }
                
                try:
                    logger.info(f"Retrying Dify request without conversation_id for user={from_wxid}")
                    retry_response = requests.post(dify_api_url, headers=headers, json=retry_data, timeout=dify_timeout)
                    retry_response.raise_for_status()
                    
                    retry_result = retry_response.json()
                    logger.info(f"Dify retry successful for user {from_wxid}")
                    
                    # 更新新的会话ID
                    if 'conversation_id' in retry_result and retry_result['conversation_id']:
                        conversations[from_wxid] = retry_result['conversation_id']
                        logger.info(f"Updated new conversation_id for {from_wxid}: {retry_result['conversation_id']}")
                    
                    return retry_result.get('answer', MESSAGES['default_reply'])
                    
                except requests.exceptions.RequestException as retry_error:
                    logger.error(f"Dify API retry failed: {str(retry_error)}")
                    return f"{MESSAGES['service_unavailable']}{str(retry_error)}"
            else:
                # 其他HTTP错误
                logger.error(f"Dify API request failed: {str(e)}")
                return f"{MESSAGES['service_unavailable']}{str(e)}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Dify API request failed: {str(e)}")
            return f"{MESSAGES['service_unavailable']}{str(e)}"

def send_weixin_reply(target_wxid, message_content, msg_id, bot_wxid):
    """
    发送微信引用回复
    """
    data = {
        "type": "sendReferText",
        "data": {
            "msgId": str(msg_id),
            "wxid": target_wxid,
            "msg": message_content
        }
    }
    
    params = {
        "wxid": bot_wxid
    }
    
    try:
        logger.info(f"Sending WeChat reply to {target_wxid}")
        response = requests.post(WEIXIN_API_URL, json=data, params=params)
        response.raise_for_status()
        
        result = response.json()
        if result.get('code') == 200:
            logger.info("WeChat reply sent successfully")
            return True
        else:
            logger.error(f"WeChat reply failed: {result.get('msg')}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"WeChat API request failed: {str(e)}")
        return False

def send_weixin_text(target_wxid, message_content, bot_wxid):
    """
    发送微信普通文本消息(用于定时任务)
    """
    data = {
        "type": "sendText",
        "data": {
            "wxid": target_wxid,
            "msg": message_content
        }
    }
    
    params = {
        "wxid": bot_wxid
    }
    
    try:
        logger.info(f"Sending scheduled message to {target_wxid}")
        response = requests.post(WEIXIN_API_URL, json=data, params=params)
        response.raise_for_status()
        
        result = response.json()
        if result.get('code') == 200:
            logger.info("Scheduled message sent successfully")
            return True
        else:
            logger.error(f"Scheduled message failed: {result.get('msg')}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"WeChat API request failed: {str(e)}")
        return False

def parse_refer_message(msg):
    """
    解析XML格式的引用消息,提取title和refermsg中的content
    返回: 拼接后的文本,如果不是XML格式则返回None
    """
    import xml.etree.ElementTree as ET
    
    try:
        # 尝试解析XML
        root = ET.fromstring(msg)
        
        # 提取title内容
        title_elem = root.find('.//title')
        title_text = title_elem.text if title_elem is not None and title_elem.text else ""
        
        # 提取refermsg中的content
        refer_content_elem = root.find('.//refermsg/content')
        refer_content = refer_content_elem.text if refer_content_elem is not None and refer_content_elem.text else ""
        
        # 如果都为空,返回None
        if not title_text and not refer_content:
            return None
        
        # 拼接内容: "被引用的内容\n当前消息内容"
        if refer_content and title_text:
            combined_text = f"{refer_content}\n{title_text}"
        elif refer_content:
            combined_text = refer_content
        else:
            combined_text = title_text
        
        logger.info(f"Parsed refer message - Title: '{title_text}', Refer: '{refer_content}'")
        return combined_text
        
    except ET.ParseError:
        # 不是有效的XML,返回None
        return None
    except Exception as e:
        logger.warning(f"Error parsing XML message: {str(e)}")
        return None

def process_group_message(message_data, bot_wxid):
    """
    处理群聊消息(@机器人 或 包含关键词触发)
    返回: (query_text, direct_reply)
    - query_text: 需要发送给Dify的内容,None表示忽略消息
    - direct_reply: 直接回复的内容,不需要经过Dify
    """
    import re
    data_info = message_data['data']['data']
    msg = data_info['msg']
    
    # 1. 检查是否@机器人 或 消息包含关键词
    is_mentioned = bot_wxid in data_info.get('atWxidList', [])
    has_keyword = any(keyword in msg for keyword in TRIGGER_KEYWORDS)
    
    if not is_mentioned and not has_keyword:
        return None, None  # 既没@也没关键词,忽略
    
    # 2. 尝试解析XML格式的引用消息
    parsed_refer = parse_refer_message(msg)
    if parsed_refer is not None:
        # 如果是XML引用消息,使用解析后的内容
        processed_msg = parsed_refer
        logger.info(f"Using parsed refer message content: {processed_msg[:100]}...")
    else:
        # 3. 移除消息中的@提及(如"@机器人 你好"→"你好")
        # 匹配@后的用户名(支持中文/英文/数字),并替换为空
        processed_msg = re.sub(r'@[\u4e00-\u9fa5A-Za-z0-9_. ]+\s*', '', msg).strip()
    
    # 4. 如果是空消息(如仅@机器人但无内容),直接回复
    if not processed_msg:
        return None, MESSAGES['empty_message_reply']
    
    return processed_msg, None

def process_private_message(message_data):
    """
    处理私聊消息(直接保留文本)
    """
    data_info = message_data['data']['data']
    return data_info['msg'].strip()

def execute_scheduled_task(task):
    """
    执行定时任务
    支持两种类型:
    - type: "text" - 直接发送固定文本
    - type: "dify" - 发送prompt到Dify获取回复后发送
    """
    task_name = task.get('name', 'Unnamed Task')
    task_type = task.get('type', 'dify')  # 默认为dify类型
    target_groups = task.get('target_groups', [])
    
    logger.info(f"Executing scheduled task: {task_name} (type: {task_type})")
    
    if not target_groups:
        logger.error(f"Task '{task_name}' has no target groups, skipping")
        return
    
    # 使用配置中的bot_wxid
    if not BOT_WXID:
        logger.error("Bot wxid not configured in config.json, cannot send scheduled message")
        return
    
    # 根据任务类型处理
    if task_type == 'text':
        # 固定文本类型
        message = task.get('message', '')
        if not message:
            logger.error(f"Task '{task_name}' (type: text) has no message, skipping")
            return
        
        # 直接发送固定文本到所有目标群聊
        for group_wxid in target_groups:
            try:
                logger.info(f"Sending fixed text for task '{task_name}' to group {group_wxid}")
                success = send_weixin_text(group_wxid, message, BOT_WXID)
                
                if success:
                    logger.info(f"Task '{task_name}' executed successfully for group {group_wxid}")
                else:
                    logger.error(f"Task '{task_name}' failed to send message to group {group_wxid}")
                    
            except Exception as e:
                logger.error(f"Error executing task '{task_name}' for group {group_wxid}: {str(e)}", exc_info=True)
    
    elif task_type == 'dify':
        # Dify类型
        prompt = task.get('prompt', '')
        if not prompt:
            logger.error(f"Task '{task_name}' (type: dify) has no prompt, skipping")
            return
        
        # 发送prompt到Dify获取回复,然后发送到所有目标群聊
        for group_wxid in target_groups:
            try:
                logger.info(f"Processing Dify task '{task_name}' for group {group_wxid}")
                
                # 发送prompt到Dify获取回复
                dify_reply = send_to_dify(prompt, group_wxid)
                
                # 发送消息到群聊
                success = send_weixin_text(group_wxid, dify_reply, BOT_WXID)
                
                if success:
                    logger.info(f"Task '{task_name}' executed successfully for group {group_wxid}")
                else:
                    logger.error(f"Task '{task_name}' failed to send message to group {group_wxid}")
                    
            except Exception as e:
                logger.error(f"Error executing task '{task_name}' for group {group_wxid}: {str(e)}", exc_info=True)
    
    else:
        logger.error(f"Task '{task_name}' has unknown type: {task_type}, skipping")

def init_scheduler():
    """
    初始化定时任务调度器
    """
    scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
    scheduled_tasks = config.get('scheduled_tasks', [])
    
    if not scheduled_tasks:
        logger.info("No scheduled tasks configured")
        return scheduler
    
    enabled_count = 0
    for task in scheduled_tasks:
        task_name = task.get('name', 'Unnamed Task')
        task_type = task.get('type', 'dify')
        cron_expr = task.get('cron', '')
        enabled = task.get('enabled', True)
        description = task.get('description', 'No description')
        
        if not enabled:
            logger.info(f"Scheduled task '{task_name}' is disabled, skipping")
            continue
        
        if not cron_expr:
            logger.error(f"Scheduled task '{task_name}' has no cron expression, skipping")
            continue
        
        try:
            # 解析cron表达式 (分 时 日 月 周)
            parts = cron_expr.split()
            if len(parts) != 5:
                logger.error(f"Invalid cron expression for task '{task_name}': {cron_expr}")
                continue
            
            minute, hour, day, month, day_of_week = parts
            
            # 创建触发器
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone='Asia/Shanghai'
            )
            
            # 添加任务
            scheduler.add_job(
                execute_scheduled_task,
                trigger=trigger,
                args=[task],
                id=task_name,
                name=task_name,
                replace_existing=True
            )
            
            enabled_count += 1
            logger.info(f"Scheduled task added: '{task_name}' (type: {task_type}) - {description}")
            logger.info(f"  Cron: {cron_expr}")
            logger.info(f"  Target groups: {', '.join(task.get('target_groups', []))}")
            
        except Exception as e:
            logger.error(f"Failed to add scheduled task '{task_name}': {str(e)}")
    
    if enabled_count > 0:
        scheduler.start()
        logger.info(f"Scheduler started with {enabled_count} active task(s)")
    else:
        logger.info("No enabled scheduled tasks to start")
    
    return scheduler

@app.route('/wechat/callback', methods=['GET', 'POST'])
def wechat_callback():
    """
    微信消息回调入口(处理群聊/私聊文本消息)
    """
    # 1. 验证回调(GET请求,用于框架确认URL有效性)
    if request.method == 'GET':
        logger.info("Received verification request (GET)")
        return jsonify({"status": "success"})
    
    # 2. 处理消息(POST请求,框架推送的消息)
    elif request.method == 'POST':
        try:
            message_data = request.json
            logger.info(f"Received WeChat message: {json.dumps(message_data, ensure_ascii=False)[:500]}...")
            
            # 提取基础信息
            event_type = message_data.get('event')  # 10008=群聊,10009=私聊
            bot_wxid = message_data.get('wxid')     # 机器人自身的wxid
            data_info = message_data['data']['data']
            
            # 优先使用配置中的bot_wxid,如果配置为空则使用回调中的wxid
            effective_bot_wxid = BOT_WXID if BOT_WXID else bot_wxid
            
            # 3. 检查是否是XML引用消息(包含<title>和<refermsg><content>标签)
            msg_content = data_info.get('msg', '')
            is_refer_message = '<title>' in msg_content and '<refermsg>' in msg_content and '<content>' in msg_content
            
            # 4. 过滤非文本消息(仅处理msgType=1,但XML引用消息除外)
            if data_info.get('msgType') != 1 and not is_refer_message:
                logger.info(f"Ignoring non-text message (msgType={data_info.get('msgType')})")
                return jsonify({"status": "ignored"})
            
            # 5. 过滤自己发送的消息(msgSource=1是机器人自己发的)
            if data_info.get('msgSource') == 1:
                logger.info("Ignoring self-sent message (msgSource=1)")
                return jsonify({"status": "ignored"})
            
            # 5. 处理群聊/私聊消息
            query_text = ""
            target_wxid = ""  # 回复的目标(群ID/好友wxid)
            direct_reply = None  # 直接回复内容(不经过Dify)
            
            # 5.1 群聊消息(event=10008)
            if event_type == 10008:
                logger.info("Processing group message (event=10008)")
                query_text, direct_reply = process_group_message(message_data, effective_bot_wxid)
                if query_text is None and direct_reply is None:  # 未触发,忽略
                    logger.info("Ignoring group message (not triggered)")
                    return jsonify({"status": "ignored"})
                target_wxid = data_info['fromWxid']  # 群ID(回复到群里)
            
            # 5.2 私聊消息(event=10009)
            elif event_type == 10009:
                logger.info("Processing private message (event=10009)")
                query_text = process_private_message(message_data)
                target_wxid = data_info['fromWxid']  # 好友wxid(回复到私聊)
            
            # 6. 判断是直接回复还是通过Dify回复
            if direct_reply:
                # 直接回复(不经过Dify)
                logger.info("Sending direct reply without Dify")
                dify_reply = direct_reply
            elif query_text:
                # 7. 发送到Dify获取回复
                dify_reply = send_to_dify(query_text, target_wxid)
            else:
                logger.warning("Empty query text after processing")
                return jsonify({"status": "error", "message": "Empty query text"})
            
            # 8. 发送微信引用回复(引用原消息)
            msg_id = data_info['msgId']  # 原消息ID(用于引用回复)
            success = send_weixin_reply(target_wxid, dify_reply, msg_id, effective_bot_wxid)
            
            # 9. 返回处理结果
            if success:
                return jsonify({"status": "processed"})
            else:
                return jsonify({"status": "error", "message": "Failed to send WeChat reply"})

        # 处理全局异常
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500  # 500=服务器内部错误

@app.route('/', methods=['GET'])
def health_check():
    """
    健康检查端点(用于确认服务是否运行)
    """
    return jsonify({
        "status": "running",
        "service": "wechat-dify-bridge",
        "timestamp": datetime.now().isoformat(),
        "config_loaded": True,
        "bot_wxid_configured": bool(BOT_WXID)
    })

if __name__ == '__main__':
    # 从配置文件读取服务器设置
    host = config['server']['host']
    port = config['server']['port']
    debug = config['server']['debug']
    
    logger.info(f"Starting WeChat-Dify bridge server on http://{host}:{port}")
    logger.info(f"Callback URL (for 千寻框架): http://127.0.0.1:{port}/wechat/callback")
    logger.info(f"Trigger keywords: {', '.join(TRIGGER_KEYWORDS)}")
    
    # 显示bot_wxid配置状态
    if BOT_WXID:
        logger.info(f"Bot wxid configured: {BOT_WXID}")
    else:
        logger.warning("Bot wxid not configured in config.json, will use wxid from callback messages")
    
    # 显示群聊映射配置
    group_mapping = config['dify'].get('group_mapping', {})
    if group_mapping:
        logger.info(f"Group mappings configured: {len(group_mapping)} group(s)")
        for group_id, group_config in group_mapping.items():
            desc = group_config.get('description', 'No description')
            logger.info(f"  - {group_id}: {desc}")
    else:
        logger.info("No group mappings configured, all groups will use default Dify config")
    
    # 初始化定时任务调度器
    scheduler = init_scheduler()
    
    try:
        app.run(host=host, port=port, debug=debug)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler...")
        if scheduler:
            scheduler.shutdown()
        logger.info("Server stopped")