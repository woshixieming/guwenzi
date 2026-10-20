#!/usr/bin/env python3
"""
字义数据生成：把《汉语拼音辞典》的汉字详解做成按需加载的分片文件
输入: data/char_detail.json (21041 字详解, 含古籍书证)  data/char_base.json (结构码/使用频率)
输出: defs/dNN.js  (32 片，前端点击某字时只加载该字所在分片)
      data.js 内联 st(字形结构) / fq(使用频率) 两字段

体积控制策略：每字保留前 3 条释义(各截 80 字) + 1 条古籍书证(截 40 字)，
按码位取模分 32 片，单片约 300KB，首次查看某字时异步载入，之后走缓存。
"""
import json, os, re

BASE = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(BASE, 'data')
DEFS = os.path.join(BASE, 'defs')
SHARDS = 32
MAX_EXPL = 3          # 每读音保留释义条数
MAX_EXPL_LEN = 80     # 单条释义截断长度
MAX_QUOTE_LEN = 40    # 书证引文截断长度
MAX_SW = 3            # 《说文》类书证单独保留条数（字源区块）
MAX_SW_LEN = 110      # 《说文》引文截断长度（分析字形构造，需比一般书证长）
SW_KEY = ('说文', '説文')   # 《说文》《说文解字》《说文解字注》《说文新附》等

# ---------- 1. 结构码 / 使用频率 ----------
# 结构码见项目 README《汉字结构表》: D0 独体 D1 镶嵌 A0 品字 B0-B4 上下 E0-E2 上中下
# H0-H3 左右 M0-M2 左中右 Q0 全包围 R0-R6 半包围
base = {}
for line in open(os.path.join(DATA, 'char_base.json'), encoding='utf-8'):
    line = line.strip().rstrip(',')
    if not line:
        continue
    try:
        r = json.loads(line)
    except json.JSONDecodeError:
        continue
    base[r['char']] = r
print(f'char_base: {len(base)} 字')

# ---------- 2. 详解解析 ----------
def clean(s):
    s = re.sub(r'\s+', '', (s or '').strip())
    return s

def ref_desc(e):
    """异体条目：explanations 里没有 content，只有 simplified/same/variant 指向正字
    （如 戶 -> same:户、弔 -> simplified:吊）。家谱查字场景价值很高，转成中文描述"""
    parts = []
    if e.get('simplified'):
        parts.append(f"简体作「{clean(e['simplified'])}」")
    if e.get('same'):
        parts.append(f"同「{clean(e['same'])}」")
    if e.get('variant'):
        parts.append(f"异体作「{clean(e['variant'])}」")
    if e.get('modern'):
        parts.append(f"今通行作「{clean(e['modern'])}」")
    return '，'.join(parts)

def pack(char, r):
    """字 -> ([[拼音, [释义...], [书证...]], ...], [[书名, 《说文》引文], ...])
    《说文》类书证单独成组（字源区块），其余古籍书证并入释义"""
    out, sw = [], []
    for p in (r.get('pronunciations') or [])[:2]:          # 最多两个读音
        py = clean(p.get('pinyin'))
        exps, quotes = [], []
        for e in (p.get('explanations') or []):
            c = clean(e.get('content'))
            if not c:
                c = ref_desc(e)                            # 异体条目 → 关系描述
            if not c or c in exps:
                continue
            if len(c) > MAX_EXPL_LEN:
                c = c[:MAX_EXPL_LEN]
            exps.append(c)
            for d in (e.get('detail') or []):
                t = clean(d.get('text')).lstrip('。，、；：.')   # 部分引文以标点开头
                bk = clean(d.get('book'))
                if not t:
                    continue
                if any(k in bk for k in SW_KEY):           # 《说文》→ 字源
                    if len(sw) < MAX_SW and not any(x[1] == t for x in sw):
                        sw.append([bk, t[:MAX_SW_LEN]])
                elif len(quotes) < 1:                      # 其余古籍 → 书证
                    quotes.append((bk + t)[:MAX_QUOTE_LEN])
            if len(exps) >= MAX_EXPL:
                break
        if exps or quotes:
            out.append([py, exps, quotes])       # [读音, [释义...], [古籍书证...]]
    return out, sw

shard_data = [{} for _ in range(SHARDS)]
n_ok = n_quote = n_sw = 0
for line in open(os.path.join(DATA, 'char_detail.json'), encoding='utf-8'):
    line = line.strip().rstrip(',')
    if not line:
        continue
    try:
        r = json.loads(line)
    except json.JSONDecodeError:
        continue
    w = r.get('char')
    if not w or len(w) > 2:                    # 跳过非单字条目（含代理对的扩展字长度为 2）
        continue
    packed, sw = pack(w, r)
    if not packed and not sw:
        continue
    # 结构 / 频率 另行输出（不塞进分片）
    b = base.get(w)
    if b:
        packed_meta = {'st': b.get('structure', ''), 'fq': b.get('frequency', -1)}
    else:
        packed_meta = None
    entry = {'d': packed}
    if sw:
        entry['sw'] = sw                      # 《说文》字源材料
    if packed_meta:
        entry.update(packed_meta)
    shard_data[ord(w) % SHARDS][w] = entry
    n_ok += 1
    if any(e[2] for e in packed):
        n_quote += 1
    if sw:
        n_sw += 1
print(f'释义条目: {n_ok} 字 (含古籍书证 {n_quote} 字; 含《说文》字源 {n_sw} 字)')

# ---------- 3. 分片输出 ----------
os.makedirs(DEFS, exist_ok=True)
total = 0
for i, sd in enumerate(shard_data):
    body = json.dumps(sd, ensure_ascii=False, separators=(',', ':'))
    js = f'var DEF_{i} = {body};'
    fp = os.path.join(DEFS, f'd{i:02d}.js')
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(js)
    sz = os.path.getsize(fp)
    total += sz
    if i < 3 or sz > 500 * 1024:
        print(f'  d{i:02d}.js {len(sd):5d} 字 {sz/1024:6.0f} KB')
print(f'defs 总分片: {SHARDS} 片, 合计 {total/1024/1024:.1f} MB, 单片均 {total/SHARDS/1024:.0f} KB')

# ---------- 4. 结构/频率并入主库 ----------
mp = os.path.join(BASE, 'data.js')
main = json.loads(open(mp, encoding='utf-8').read()[len('const HANZI = '):-1])
n_st = 0
for rec in main['chars']:
    # 注：build_data.py 才是 st/fq 的主来源（直接读 char_base，覆盖更全 8005 字）；
    # 这里只补主库漏掉的字，绝不覆盖已有值，否则两个脚本的执行顺序会影响数据量
    e = shard_data[ord(rec['c']) % SHARDS].get(rec['c'])
    if e and e.get('st') and e.get('fq', -1) >= 0 and rec.get('st') is None:
        rec['st'] = e['st']
        rec['fq'] = e['fq']
        n_st += 1
open(mp, 'w', encoding='utf-8').write(
    'const HANZI = ' + json.dumps(main, ensure_ascii=False, separators=(',', ':')) + ';')
print(f'主库并入结构/频率: {n_st}/{len(main["chars"])} 字; data.js {os.path.getsize(mp)/1024:.0f} KB')

# ---------- 5. 自检 ----------
for probe in ['劝', '书', '永', '喆']:
    e = shard_data[ord(probe) % SHARDS].get(probe)
    print(f'  {probe}(片{ord(probe)%SHARDS:02d}): ' + (json.dumps(e, ensure_ascii=False)[:120] if e else '(无)'))
