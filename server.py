#!/usr/bin/env python3
"""
简单的HTTP服务器 - 接收请求时执行shell脚本
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import json
from datetime import datetime

# 配置项
PORT = 18080
SHELL_SCRIPT = "./deploy.sh"  # 修改为你的脚本路径


class ScriptHandler(BaseHTTPRequestHandler):
    """处理HTTP请求的处理器"""
    
    def do_GET(self):
        """处理GET请求"""
        self.execute_script()
    
    def do_POST(self):
        """处理POST请求"""
        self.execute_script()
    
    def execute_script(self):
        """执行shell脚本"""
        try:
            # 记录请求信息
            print(f"[{datetime.now()}] 收到请求: {self.command} {self.path}")
            print(f"客户端: {self.client_address[0]}:{self.client_address[1]}")
            
            # 执行shell脚本
            result = subprocess.run(
                [SHELL_SCRIPT],
                capture_output=True,
                text=True,
                timeout=30  # 30秒超时
            )
            
            # 准备响应
            response = {
                "status": "success" if result.returncode == 0 else "error",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.now().isoformat()
            }
            
            # 发送响应
            self.send_response(200 if result.returncode == 0 else 500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode('utf-8'))
            
            print(f"重启脚本执行完成，返回码: {result.returncode}")
            
        except subprocess.TimeoutExpired:
            self.send_error(504, "脚本执行超时")
            print("错误: 脚本执行超时")
            
        except FileNotFoundError:
            self.send_error(500, f"脚本文件不存在: {SHELL_SCRIPT}")
            print(f"错误: 找不到脚本文件 {SHELL_SCRIPT}")
            
        except Exception as e:
            self.send_error(500, f"执行错误: {str(e)}")
            print(f"错误: {str(e)}")
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        pass  # 我们使用自己的日志，禁用默认日志


def main():
    """启动HTTP服务器"""
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, ScriptHandler)
    
    print("=" * 60)
    print(f"HTTP服务器启动成功!")
    print(f"监听端口: {PORT}")
    print(f"执行脚本: {SHELL_SCRIPT}")
    print(f"测试命令: curl http://localhost:{PORT}")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
        httpd.server_close()


if __name__ == "__main__":
    main()
