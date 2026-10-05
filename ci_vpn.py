"""Prepare a temporary Surfshark connection for a GitHub-hosted Linux runner."""
import io
import json
from firebase_admin import credentials
import os
import socket
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
import requests
import updater

root = Path(os.environ['RUNNER_TEMP']) / 'trustpositif'
root.mkdir(mode=0o700, exist_ok=True)
for name in ('FIREBASE_SERVICE_ACCOUNT', 'SURFSHARK_USERNAME', 'SURFSHARK_PASSWORD'):
    if not os.environ.get(name):
        raise RuntimeError(f'GitHub Secret {name} belum tersedia')
try:
    credentials.Certificate(json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT']))
except (ValueError, TypeError, KeyError) as exc:
    raise RuntimeError('JSON Firebase atau private_key tidak valid; gunakan file asli tanpa mengubah isinya') from None
for filename, value in (
    ('firebase.json', os.environ['FIREBASE_SERVICE_ACCOUNT']),
    ('vpn-auth.txt', os.environ['SURFSHARK_USERNAME'].strip()+'\n'+os.environ['SURFSHARK_PASSWORD'].strip()+'\n'),
):
    path = root / filename
    path.touch(mode=0o600)
    path.chmod(0o600)
    path.write_text(value)
r=requests.get('https://my.surfshark.com/vpn/api/v1/server/configurations', timeout=(15,90))
r.raise_for_status()
with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
    candidates=[n for n in archive.namelist() if n.endswith('id-jak.prod.surfshark.com_tcp.ovpn')]
    if len(candidates)!=1:
        raise RuntimeError('Konfigurasi Jakarta TCP tidak ditemukan')
    config=archive.read(candidates[0]).decode()
config='\n'.join(line for line in config.splitlines() if line.strip() not in ('auth-user-pass','fast-io','cipher AES-256-CBC'))
ips=sorted({r[4][0] for r in socket.getaddrinfo(urlsplit(updater.SOURCE_URL).hostname,443,family=socket.AF_INET)})
config+='\nauth-user-pass '+str(root/'vpn-auth.txt')+'\nauth-nocache\nroute-nopull\ndata-ciphers AES-256-GCM:AES-128-GCM:AES-256-CBC\nconnect-timeout 15\nconnect-retry-max 3\n'
config+=''.join('route '+ip+' 255.255.255.255\n' for ip in ips)
path=root/'vpn.ovpn';path.write_text(config);path.chmod(0o600)
print('Konfigurasi Surfshark Jakarta siap; rute hanya ke TrustPositif.')
