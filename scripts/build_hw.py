#!/usr/bin/env python3
"""
笔顺字表生成：从 jsDelivr 的包文件清单提取 hanzi-writer-data 实际收录的字。
用途：前端据此判断某字有无笔顺数据，避免对未收录的字发起必然 404 的请求。
输入: data/hwfiles.json（jsDelivr package 文件清单，缺失时自动下载）
输出: hwset.js —— const HW_SET = '<所有收录字连成的字符串>'
"""
import json, os, urllib.request

BASE = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(BASE, 'data')
API = 'https://data.jsdelivr.com/v1/packages/npm/hanzi-writer-data@2.0.1?structure=flat'

src = os.path.join(DATA, 'hwfiles.json')
if not os.path.exists(src):
    print('下载文件清单…')
    with urllib.request.urlopen(API, timeout=90) as r:
        with open(src, 'wb') as f:
            f.write(r.read())
files = json.load(open(src, encoding='utf-8')).get('files', [])

def is_han(w):
    return len(w) == 1 and ('\u3400' <= w <= '\u9fff' or '\uf900' <= w <= '\ufaff')

chars = set()
for f in files:
    n = f['name']
    if n.startswith('/') and n.count('/') == 1 and n.endswith('.json'):
        w = n[1:-5]
        if is_han(w):
            chars.add(w)
chars = sorted(chars)
print(f'笔顺库收录: {len(chars)} 字')

main = json.loads(open(os.path.join(BASE, 'data.js'), encoding='utf-8').read()[len('const HANZI = '):-1])
std = {r['c'] for r in main['chars']}
vr = set(main['variantIndex'])
print(f'  覆盖规范字表: {len(std & set(chars))}/{len(std)}')
print(f'  覆盖反查异体字: {len(vr & set(chars))}/{len(vr)}')

out = os.path.join(BASE, 'hwset.js')
with open(out, 'w', encoding='utf-8') as f:
    f.write('const HW_SET = ' + json.dumps(''.join(chars), ensure_ascii=False) + ';')
print(f'hwset.js: {os.path.getsize(out)/1024:.0f} KB')
for probe in ['书', '書', '讃', '龘', '淸', '一', 'biang']:
    print(f'  {probe}: {"有" if probe in chars else "无"}笔顺')
