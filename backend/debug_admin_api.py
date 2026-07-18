import ssl
import urllib.request
import urllib.error

ctx = ssl._create_unverified_context()
urls = [
    'https://127.0.0.1:8443/api/admin/dashboard/',
    'https://127.0.0.1:8443/api/admin/reports/',
]
for url in urls:
    print('URL', url)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            print('STATUS', r.status)
            print('CONTENT-TYPE', r.getheader('Content-Type'))
            body = r.read(4096)
            print('BODY', body.decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        print('HTTP_ERROR', e.code)
        print(e.read(4096).decode('utf-8', 'replace'))
    except Exception as e:
        print('EXCEPTION', type(e).__name__, e)
