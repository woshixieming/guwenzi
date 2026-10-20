#!/usr/bin/env python3
"""
词语库生成：解析 CC-CEDICT（中文词 → 拼音、简繁对照）
  - 数字调号转带调拼音（Zhong1 guo2 → Zhōng guó）
  - 同一简体词的多个读音合并；繁体不同形时才额外存繁体
  - 按首字码位 % 64 分片，前端按需加载对应片
输出: words/w00.js … w63.js —— const WORD_<n> = {词: [拼音, 繁体?], ...}
"""
import gzip, json, os, re

BASE = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(BASE, 'data')
SRC = os.path.join(DATA, 'cedict.txt.gz')
SHARDS = 64

MARK = {'a': 'āáǎà', 'o': 'ōóǒò', 'e': 'ēéěè', 'i': 'īíǐì', 'u': 'ūúǔù', 'v': 'ǖǘǚǜ'}

def to_marked(syl):
    """pin1 → pīn；轻声(5/缺省)不标调；ü 写作 u: 或 v"""
    m = re.match(r'^([A-Za-zü:]+)([0-5])?$', syl)
    if not m:
        return syl
    base, tone = m.group(1).replace('u:', 'ü').replace('v', 'ü'), int(m.group(2) or 5)
    low = base.lower()
    if tone in (0, 5):
        return base
    if 'a' in low:
        pos = low.index('a')
    elif 'o' in low:
        pos = low.index('o')
    elif 'e' in low:
        pos = low.index('e')
    else:
        idxs = [i for i, c in enumerate(low) if c in 'iüu']
        if not idxs:
            return base
        pos = idxs[-1] if len(idxs) >= 2 else idxs[0]
    ch = low[pos]
    key = 'v' if ch == 'ü' else ch
    return base[:pos] + MARK[key][tone - 1] + base[pos + 1:]

def parse_pinyin(raw):
    out = []
    for s in raw.split():
        if s:
            out.append(to_marked(s))
    return ' '.join(out)

# CC-CEDICT 行: 繁体 简体 [pin1 yin1] /释义/释义/
LINE = re.compile(r'^(\S+)\s+(\S+)\s+\[([^\]]*)\]\s')
shards = {}
n_line = n_skip = 0
seen = {}
with gzip.open(SRC, 'rt', encoding='utf-8') as f:
    for line in f:
        if not line or line.startswith('#'):
            continue
        n_line += 1
        m = LINE.match(line)
        if not m:
            n_skip += 1
            continue
        trad, simp, py = m.group(1), m.group(2), m.group(3).strip()
        if not py:
            n_skip += 1
            continue
        pys = parse_pinyin(py)
        # 只收 1–6 字的词语，滤掉过长的短语与句子
        if not (1 <= len(simp) <= 6) or not (1 <= len(trad) <= 6):
            n_skip += 1
            continue
        seen.setdefault(simp, ([], set()))
        if pys and pys not in seen[simp][0]:
            seen[simp][0].append(pys)
        if trad != simp:
            seen[simp][1].add(trad)
print(f'词条: 解析 {n_line} 行, 收录 {len(seen)} 词, 跳过 {n_skip} 行')

# 合并读音，按首字分片；繁体另立条目指向同一记录（供以繁体词检索）
total_bytes = 0
for simp, (pys, trads) in seen.items():
    rec = [' / '.join(pys)]
    if trads:
        rec.append(' / '.join(sorted(trads)))
    k = ord(simp[0]) % SHARDS
    shards.setdefault(k, {})[simp] = rec
    for t in trads:
        k2 = ord(t[0]) % SHARDS
        shards.setdefault(k2, {}).setdefault(t, [rec[0], simp])

os.makedirs(os.path.join(BASE, 'words'), exist_ok=True)
for k in range(SHARDS):
    obj = shards.get(k, {})
    # 必须用 var：const 声明不会挂到 window，而前端是按动态名字 window['WORD_n'] 取用的
    js = f'var WORD_{k} = ' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + ';'
    p = os.path.join(BASE, 'words', 'w' + str(k).zfill(2) + '.js')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(js)
    total_bytes += os.path.getsize(p)
print(f'词语分片: {SHARDS} 片, 共 {total_bytes/1024/1024:.2f} MB, '
      f'单片均 {total_bytes/SHARDS/1024:.0f} KB')
n_trad = sum(1 for v in seen.values() if len(v[1]))
print(f'含繁体对照的词: {n_trad}')
for probe in ['中国', '家谱', '书籍', '祖宗', '祠堂']:
    k = ord(probe[0]) % SHARDS
    hit = shards.get(k, {}).get(probe)
    print(f'  {probe}: {hit or "(未收录)"}')
