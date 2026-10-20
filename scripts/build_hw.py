#!/usr/bin/env python3
"""
笔顺字表生成：从本地 hanzi-writer-data 文件提取实际收录的字。
用途：前端据此判断某字有无笔顺数据，避免对未收录的字发起必然 404 的请求。
输入: assets/hanzi-writer-data/；兼容旧的 data/hwfiles.json 文件清单
输出: hwset.js —— const HW_SET = '<所有收录字连成的字符串>'
"""
import json, os

BASE = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(BASE, 'data')
LOCAL = os.path.join(BASE, 'assets', 'hanzi-writer-data')
src = os.path.join(DATA, 'hwfiles.json')
if os.path.isdir(LOCAL):
    files = [{'name': '/' + n} for n in os.listdir(LOCAL)]
elif os.path.exists(src):
    files = json.load(open(src, encoding='utf-8')).get('files', [])
else:
    raise FileNotFoundError('缺少本地笔顺数据，请先运行 python3 scripts/sync_offline_assets.py')

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
