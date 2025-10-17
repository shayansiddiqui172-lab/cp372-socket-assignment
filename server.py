#!/usr/bin/env python3
"""
CP372 Socket Programming — Server (TCP)
"""

import os
import socket
import threading
from datetime import datetime

# Configuring
HOST = "0.0.0.0"       
PORT = 12345           # Port number to match with client server's
MAX_CLIENTS = 3        # Setting limit to # of clients
REPO_DIR = "repo"      
LINE_END = b"\n"       

# Shared state
lock = threading.Lock()
client_counter = 0                     # Assign Client numbers based on Clients
active = {} 
cache = {}                            

# Needed helper functions

# Format time stamps 
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def send_line(conn: socket.socket, text: str):
    # Application Layer sending - encoding strings to utf-8 and then sending all to bytes to TCP buffer
    conn.sendall(text.encode("utf-8") + LINE_END)

def recv_line(conn: socket.socket):
    # Application Layer recieving - decodes bytes; reading bytes one by one until connection is closed when recv() runs empty
    buf = bytearray()
    while True:
        chunk = conn.recv(1)          
        if not chunk:
            return None               # connection closed
        if chunk == LINE_END:
            return buf.decode("utf-8", errors="replace")
        buf.extend(chunk)

# list files in the repository folder
def list_repo_files():
    if not os.path.isdir(REPO_DIR):
        return []
    return sorted(
        f for f in os.listdir(REPO_DIR)
        if os.path.isfile(os.path.join(REPO_DIR, f))
    )


# Client thread

#Entry point of the thread
def handle_client(conn: socket.socket, addr):
    global client_counter
    # TCP 3-way handshake has already been completed
    with lock:
        client_counter += 1
        name = f"Client{client_counter:02d}"
        active[name] = (conn, addr)
        cache[name] = {
            "addr": f"{addr[0]}:{addr[1]}",
            "connected": now(),
            "disconnected": None,
        }
    #Records client name, connection, timestamp    

    try:
        # Naming still in the application layer
        send_line(conn, f"YOURNAME {name}")
        confirm = recv_line(conn)
        if confirm is None or confirm.strip() != name:
            send_line(conn, "ERR expected your name; closing")
            return

        send_line(conn, f"HELLO {name}. Commands: status | list | <filename> | exit")

        # Main request/response loop - this all runs once per client
        while True:
            line = recv_line(conn)
            if line is None:
                break
            cmd = line.strip().lower()
            #reads line or disconnects
            if cmd == "exit":
                send_line(conn, "BYE")
                break
            

            elif cmd == "status":
                # Show current and past connections
                send_line(conn, "STATUS-BEGIN")
                with lock:
                    for n, info in cache.items():
                        send_line(
                            conn,
                            f"{n} | {info['addr']} | connected={info['connected']} | "
                            f"disconnected={info['disconnected']}"
                        )
                send_line(conn, "STATUS-END")


            #list repo file
            elif cmd == "list":
                files = list_repo_files()
                send_line(conn, "FILES " + (",".join(files) if files else "(empty)"))

            else:
                # If file exists, send data; or else echo with ACK
                path = os.path.join(REPO_DIR, cmd)
                if os.path.isfile(path):
                    size = os.path.getsize(path)
                    send_line(conn, f"FILESIZE {size}")
                    # stream exact bytes (part of the 'data' mentioned earlier)
                    with open(path, "rb") as f:
                        while True:
                            chunk = f.read(4096)
                            if not chunk:
                                break
                            conn.sendall(chunk)
                    # marker to return to line mode when file name found
                    send_line(conn, "FILE-DONE")
                else:
                    # simple positive ACK at application layer
                    send_line(conn, f"{cmd} ACK")

    finally:
        # disconnect and log the disconnection
        with lock:
            active.pop(name, None)
            if name in cache:
                cache[name]["disconnected"] = now()
        try:
            conn.close()
        except Exception:
            pass
        print(f"[SERVER] {name} disconnected")

# accept loop and create the TCP per client
def main():
    os.makedirs(REPO_DIR, exist_ok=True)
    print(f"[SERVER] Listening on {HOST}:{PORT}  (repo='{REPO_DIR}', max={MAX_CLIENTS})")
    # make sure repo folder exists 
    # TCP socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Make restartings easier during testing
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()  

        while True:
            conn, addr = s.accept()  # active open from client completed handshake
            with lock:
                if len(active) >= MAX_CLIENTS:
                    # Application layer block new clients if max # of clients reached
                    try:
                        send_line(conn, "BUSY server at capacity; try later")
                    finally:
                        conn.close()
                    continue

            print(f"[SERVER] Connection from {addr}")
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
