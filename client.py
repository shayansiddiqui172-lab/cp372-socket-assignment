import os 
import socket

#Configuration 
HOST = "127.0.0.1"                  #same as server
PORT = 12345                        #same as server
LINE_END = b"\n"
DOWNLOADS = "downloads"             #folder to save recieved files


#Helper fucntions 
def send_line(sock: socket.socket, text: str):                      #send one line of text woth newline terminator 
    sock.sendall(text.encode("utf-8")+ LINE_END)
    

def rec_line(sock: socket.socket):                                  #recieve a line until newline character
    buf = bytearray()
    while True: 
        chunk = sock.recv(1)
        if not chunk:
            return None
        if chunk == LINE_END:
            return buf.decode("utf-8", errors="replace")
        buf.extend(chunk)

def rec_exact(sock: socket.socket, n: int):                         #recieve exactly n bytes for file transfers
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(min(4096, n - len(data)))
        if not chunk: 
            print("Connection closed during file transfer")
        data.extend(chunk)
    return bytes(data)


def main():
    os.makedirs(DOWNLOADS, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((HOST, PORT))
        except Exception as e:
            print(f"Could not connect to server: {e}")
            return

        # Wait for greeting
        line = rec_line(s)
        if line is None:
            print("Server closed the connection.")
            return

        if line.startswith("BUSY"):
            print(line)
            return

        if not line.startswith("YOURNAME "):
            print("Unexpected greeting:", line)
            return

        name = line.split(" ", 1)[1].strip()
        send_line(s, name)

        # Receive hello
        hello = rec_line(s)
        if hello:
            print(hello)

        print("Commands: status | list | <filename> | exit")

        # Main user loop
        while True:
            try:
                cmd = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                cmd = "exit"

            if not cmd:
                continue

            send_line(s, cmd)

            if cmd.lower() == "exit":
                bye = rec_line(s)
                if bye:
                    print(bye)
                break

            if cmd.lower() == "status":
                start = rec_line(s)
                if start != "STATUS-BEGIN":
                    print("Unexpected:", start)
                    continue
                while True:
                    line = rec_line(s)
                    if line == "STATUS-END":
                        break
                    print(line)
                continue

            if cmd.lower() == "list":
                line = rec_line(s)
                print(line)
                continue

            # Otherwise, check for file or echo
            first = rec_line(s)
            if first is None:
                print("Server closed.")
                break

            if first.startswith("FILESIZE "):
                try:
                    size = int(first.split(" ", 1)[1])
                except ValueError:
                    print("Bad FILESIZE header:", first)
                    continue

                payload = rec_exact(s, size)
                done = rec_line(s)
                if done != "FILE-DONE":
                    print("Missing FILE-DONE marker (got:", done, ")")
                    continue

                dest = os.path.join(DOWNLOADS, os.path.basename(cmd))
                with open(dest, "wb") as f:
                    f.write(payload)
                print(f"Saved file to {dest} ({len(payload)} bytes)")
            else:
                print(first)


if __name__ == "__main__":
    main()