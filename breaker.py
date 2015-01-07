import time
import os
#import glob
import subprocess
from tempfile import NamedTemporaryFile

from lxml import html
from urlparse import urljoin
import requests


CHALLENGE = 'http://www.sedar.com/GetFile.do?lang=EN&docClass=13&issuerNo=00020297&fileName=/foo'
RESPONSE = 'http://www.sedar.com/CheckCode.do'


def improve_image(image):
    null = os.open('/dev/null', os.O_APPEND)
    tmp = NamedTemporaryFile().name + '.jpg'
    args = ['/usr/local/bin/gm', 'convert']
    #args.extend(['-contrast', '-modulate', '110', '-sharpen', '0x1.0'])
    args.extend(['-contrast', '-contrast', '-contrast', '-contrast', '-contrast',
                 '-modulate', '110',
                 '-antialias', '-despeckle', '-despeckle', '-despeckle',
                 '-despeckle'])
    args.extend([image, tmp])
    p = subprocess.Popen(args, stdout=null, stderr=null)
    p.wait()
    #print tmp
    return tmp
        

def run_ocr(image):
    null = os.open('/dev/null', os.O_APPEND)
    tmp = NamedTemporaryFile()
    #print tmp.name
    args = ['/usr/local/bin/tesseract', image, tmp.name, '-l', 'eng', '-psm', '8']
    p = subprocess.Popen(args, stdout=null, stderr=null)
    p.wait()
    with open(tmp.name + '.txt', 'rb') as fh:
        return fh.read().strip()


def break_captcha(srcs):
    code = []
    
    for src in srcs:
        res = requests.get(src)
        tmp = NamedTemporaryFile().name + '.jpg'
        with open(tmp, 'wb') as fh:
            fh.write(res.content)

        #print "TMP", tmp
        clean = improve_image(tmp)
        char = run_ocr(clean)

        code.append(char)

    return ''.join(code)

#for image in glob.glob('captcha/*.jpg'):
#    cleaned = improve_image(image)
#    print [run_ocr(cleaned)], image


def make_cracked_session():
    failed = True
    print "Trying to break captcha...."
    while failed:
        try:
            sess = requests.Session()
            res = sess.get(CHALLENGE)
            doc = html.fromstring(res.content)
            srcs = [urljoin(CHALLENGE, i.get('src')) for i in doc.findall('.//img')]
            code = break_captcha(srcs)
            if len(code) != len(srcs):
                print "Wrong length guess", code
                continue
            resp_url = urljoin(CHALLENGE, doc.find('.//form').get('action'))
            print "Guessed captcha", code
            res = sess.post(resp_url, data={'code': code})
            failed = 'did not match' in res.content
            #print res.content
            print "Did it blend?", not failed
        except Exception, e:
            print e
            time.sleep(15)
    return sess

