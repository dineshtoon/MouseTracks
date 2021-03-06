"""
This is part of the Mouse Tracks Python application.
Source: https://github.com/Peter92/MouseTracks
"""

from __future__ import absolute_import

from multiprocessing import Queue
from threading import Thread, currentThread
import socket

from core.compatibility import queue
from core.notify import *
from core.sockets import *


POLLING_RATE = 1
    

def client_thread(client_id, sock, q_recv, q_send):
    """Send data to the connected clients."""
    #Connect to client and send feedback
    conn, addr = sock.accept()
    q_send.put(addr)
    
    #Remove items from queue sent before connection
    while not q_recv.empty():
        q_recv.get()
    
    #Send each item to the client
    thread = currentThread()
    while getattr(thread, 'running', True):
        try:
            message = q_recv.get()
        except (IOError, EOFError):
            return
        try:
            send_msg(conn, message)
        except (socket.error, KeyboardInterrupt):
            conn.close()
            return
            
            
def middleman_thread(q_main, q_list, exit_on_disconnect=True):
    """Handle the incoming queue and duplicate for all clients."""
    thread = currentThread()
    while getattr(thread, 'running', True):
        try:
            message = q_main.get(timeout=POLLING_RATE)
        except queue.Empty:
            pass
        except (IOError, EOFError):
            return
        else:
            for q in q_list:
                try:
                    q.put(message)
                except AssertionError:
                    if exit_on_disconnect:
                        return
                except (IOError, EOFError):
                    return
                        

def server_thread(q_main, host='localhost', port=0, close_port=False, q_feedback=None):
    """Run a server to send messages to all the connected clients."""
    
    #Create server socket
    NOTIFY(SERVER_SOCKET_START)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except socket.error as e:
        if e.errno == 10048:
            NOTIFY(SERVER_PORT_TAKEN, port)
            if close_port:
                NOTIFY(SERVER_PORT_CLOSE)
                force_close_port(port)
            else:
                NOTIFY(SERVER_PORT_NEW)
                port = 0
            sock.bind((host, port))
        else:
            raise socket.error('unable to start server')
    sock.listen(5)
    
    NOTIFY(SERVER_SOCKET_PORT, sock.getsockname()[1])
    
    q_conn = Queue()
    threads = []
    queues = []
    client_id = 1
    try:
        while True:
            #Start new client thread
            queues.append(Queue())
            threads.append(Thread(target=client_thread, args=(client_id, sock, queues[-1], q_conn)))
            threads[-1].daemon = True
            threads[-1].start()
            
            #Restart the message intercept thread
            try:
                middleman.running = False
                middleman.join()
            except NameError:
                pass
            middleman = Thread(target=middleman_thread, args=(q_main, tuple(queues)))
            middleman.daemon = True
            middleman.start()
            
            #Check for new connection (the latest thread is idle until then)
            #Loop is needed so that KeyboardInterrupt can be intercepted
            NOTIFY(SERVER_SOCKET_WAIT)
            while True:
                try:
                    addr = q_conn.get(timeout=POLLING_RATE)
                    
                #No connection yet
                except queue.Empty:
                    pass
                    
                #New client connected
                else:
                    NOTIFY(SERVER_SOCKET_CONNECT, addr[0], addr[1])
                    client_id += 1
                    break

            #Delete closed connections
            invalid = []
            for i, thread in enumerate(threads):
                if not thread.isAlive():
                    invalid.append(i)
            for i in invalid[::-1]:
                del threads[i]
                queues[i].close()
                del queues[i]
    
    #Safely shut down threads and queues
    except KeyboardInterrupt:
        for thread in threads:
            thread.running = False
        for q in queues:
            q.close()
        middleman.running = False
        sock.close()
        
    except (IOError, EOFError):
        sock.close()