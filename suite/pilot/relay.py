"""In-sandbox TCP-to-unix-socket relay for the agent's egress proxy (stdlib only).

Runs as the first process inside the agent's bubblewrap sandbox, which has its own network
namespace (loopback only). It listens on 127.0.0.1:PORT, forks a relay child that forwards
each TCP connection to the host-side allowlisting CONNECT proxy through a bind-mounted unix
socket, and then execs the agent command in the parent (so the agent keeps this PID and its
stdin/stdout). When the agent exits, bubblewrap's PID-namespace init exits and the relay dies.

    python3 -I -S relay.py SOCKET PORT -- AGENT_ARGV...
"""
import os
import socket
import sys
import threading


def _pump(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _serve(listener, sock_path):
    while True:
        try:
            client, _ = listener.accept()
        except OSError:
            return
        try:
            upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            upstream.connect(sock_path)
        except OSError:
            client.close()
            continue
        threading.Thread(target=_pump, args=(client, upstream), daemon=True).start()
        threading.Thread(target=_pump, args=(upstream, client), daemon=True).start()


def main(argv):
    sock_path, port = argv[0], int(argv[1])
    if argv[2] != '--' or len(argv) < 4:
        raise SystemExit('usage: relay.py SOCKET PORT -- AGENT_ARGV...')
    command = argv[3:]
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', port))
    listener.listen(64)
    if os.fork() == 0:                      # relay child: detach from the agent's stdio
        null = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(null, fd)
        _serve(listener, sock_path)
        os._exit(0)
    listener.close()
    os.execv(command[0], command)


if __name__ == '__main__':
    main(sys.argv[1:])
