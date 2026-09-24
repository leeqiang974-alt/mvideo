# -*- coding: utf-8 -*-
import sys, io, json, httpx, oss2
from PIL import Image
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
lines=Path(r"D:\Desktop\api\阿里云的key和secret.txt").read_text(encoding="utf-8").splitlines()
AKID=lines[1].strip(); SECRET=lines[4].strip()
auth=oss2.Auth(AKID,SECRET)
bucket=oss2.Bucket(auth,"https://oss-cn-shanghai.aliyuncs.com","ozonshanghai",connect_timeout=20)
# download one image from ir.ozone.ru, pad to 3:4, upload
u="https://ir.ozone.ru/s3/multimedia-1-h/14334251669.jpg"
b=httpx.get(u,timeout=30,follow_redirects=True).content
print("downloaded",len(b))
im=Image.open(io.BytesIO(b)).convert("RGB"); print("orig size",im.size)
w,h=im.size; t=3/4; cur=w/h
if cur<t:
    nw=int(h*t); c=Image.new("RGB",(nw,h),"white"); c.paste(im,((nw-w)//2,0)); im=c
elif cur>t:
    nh=int(w/t); c=Image.new("RGB",(w,nh),"white"); c.paste(im,(0,(nh-h)//2)); im=c
im=im.resize((900,1200),Image.LANCZOS)
buf=io.BytesIO(); im.save(buf,"JPEG",quality=92); data=buf.getvalue()
print("padded",len(data),im.size)
key="mvideo-test/ru_test_1.jpg"
r=bucket.put_object(key,data)
print("oss put status",r.status)
url=f"https://ozonshanghai.oss-cn-shanghai.aliyuncs.com/{key}"
# verify public read
rb=httpx.get(url,timeout=30)
print("public url",rb.status_code,rb.headers.get("Content-Type"),len(rb.content))
print(url)
