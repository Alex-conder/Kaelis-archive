#!/usr/bin/env python3
"""
模拟 Neo4j Bolt 服务器 - 用于测试连接逻辑

这个脚本创建一个简单的 TCP 服务器，模拟 Neo4j 的握手过程，
用于验证 KgFlywheel 的 Neo4j 连接切换逻辑。
"""
import socket
import threading
import sys


def handle_client(conn, addr):
    """处理客户端连接"""
    print(f"[MockNeo4j] Connection from {addr}")
    try:
        # 读取客户端发来的 Bolt 握手
        data = conn.recv(1024)
        if data:
            print(f"[MockNeo4j] Received handshake: {data[:20]}...")
            
            # 发送 Bolt 协议响应 (版本 5.4)
            response = b'\x00\x00\x00\x05'  # 协议版本 5.x
            conn.sendall(response)
            print("[MockNeo4j] Sent version response")
            
            # 保持连接，等待更多数据
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                # 简单响应 SUCCESS
                success_msg = b'\xb1\x70\xa1\x84\x00\x00\x00\x00'  # SUCCESS 消息
                conn.sendall(success_msg)
    except Exception as e:
        print(f"[MockNeo4j] Error: {e}")
    finally:
        conn.close()
        print(f"[MockNeo4j] Connection closed: {addr}")


def start_mock_server(host='localhost', port=7687):
    """启动模拟 Neo4j 服务器"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind((host, port))
        sock.listen(5)
        print(f"[MockNeo4j] Server started on {host}:{port}")
        print("[MockNeo4j] Press Ctrl+C to stop")
        
        while True:
            conn, addr = sock.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        print("\n[MockNeo4j] Server stopped")
    except Exception as e:
        print(f"[MockNeo4j] Server error: {e}")
    finally:
        sock.close()


if __name__ == "__main__":
    start_mock_server()
