#!/usr/bin/env python3
"""
扩展字库生成：把 8105 规范字表之外的 CJK 汉字纳入可查范围
数据源: data/Unihan.zip (Unicode 官方)
        kMandarin     普通话读音(带调) —— 覆盖基本区、扩展A/B/C…共 4.4 万字
        kHanyuPinyin  《汉语大字典》读音，作为多音补充
        kRSUnicode    康熙部首编号（用于生僻字显示部首）
        Unihan_Variants 繁简/异体对应
输出:   data_ext.js —— 独立文件，前端按需加载，不拖慢首屏
"""
import json, os, re, zipfile

BASE = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(BASE, 'data')

# ---------- 1. 主库已收录字（避免重复） ----------
main = json.loads(open(os.path.join(BASE, 'data.js'), encoding='utf-8').read()[len('const HANZI = '):-1])
std = {r['c'] for r in main['chars']}
vi = main['variantIndex']                       # 表外字 -> [[主库下标, 类型]]
print(f'主库: {len(std)} 字; 反查索引: {len(vi)} 字')

# 康熙编号 -> 部首字符（复用主库已有的 kn/r 对应关系，避免重复造映射）
num2rad = {}
for r in main['chars']:
    n = r.get('kn')
    if n and r['r'] and n not in num2rad:
        num2rad[n] = r['r']
print(f'康熙编号→部首字符: {len(num2rad)} 个')

# ---------- 2. 读音 ----------
# 声调剥离：u 行与 ü 行必须分开，否则 nú→nü、lù→lü 会使 lu/nu 音节索引失效
TONE_MAP = str.maketrans(dict(
    [ord(a), ord(b)] for src, dst in
    [('āáǎà', 'aaaa'), ('ēéěè', 'eeee'), ('īíǐì', 'iiii'), ('ōóǒò', 'oooo'),
     ('ūúǔù', 'uuuu'), ('ǖǘǚǜ', 'vvvv'), ('ü', 'v'), ('ńňǹ', 'nnn'), ('ḿ', 'm')]
    for a, b in zip(src, dst)))
PY_OK = re.compile(r'^[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüǹńňḿ]+\d?$')

# CJK 区（含扩展 B 及以后，这些字在 JS 里由代理对表示）
CJK_ZONES = [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
             (0x20000, 0x2A6DF), (0x2A700, 0x2B739), (0x2B740, 0x2B81D),
             (0x2B820, 0x2CEA1), (0x2CEB0, 0x2EBE0), (0x2EBF0, 0x2EE5D),
             (0x30000, 0x3134A), (0x31350, 0x323AF)]
def in_cjk(cp):
    return any(a <= cp <= b for a, b in CJK_ZONES)

z = zipfile.ZipFile(os.path.join(DATA, 'Unihan.zip'))
py, extra_py = {}, {}
for line in z.read('Unihan_Readings.txt').decode('utf-8').splitlines():
    if not line or line.startswith('#'):
        continue
    p = line.split('\t')
    if len(p) < 3:
        continue
    cp = int(p[0][2:], 16)
    if not in_cjk(cp):
        continue
    if p[1] == 'kMandarin':
        reads = [x for x in p[2].split() if PY_OK.match(x)]
        if reads:
            py[chr(cp)] = reads
    elif p[1] == 'kHanyuPinyin':
        # 形如 "10011.010:hē,qiě" —— 取 ":" 后的读音
        reads = []
        for chunk in p[2].split(','):
            if ':' in chunk:
                x = chunk.split(':', 1)[1].strip()
                if PY_OK.match(x) and x not in reads:
                    reads.append(x)
        if reads:
            extra_py[chr(cp)] = reads
n_extra = 0
for w, reads in extra_py.items():               # 只作补充：kMandarin 缺失或多音时
    if w not in py:
        py[w] = reads; n_extra += 1
    else:
        for x in reads:
            if x not in py[w]:
                py[w].append(x)
print(f'读音: kMandarin {len(py)} 字 (其中 {n_extra} 字仅《汉语大字典》有读音)')

# ---------- 3. 康熙部首 ----------
kr = {}
for line in z.read('Unihan_IRGSources.txt').decode('utf-8').splitlines():
    if not line or line.startswith('#'):
        continue
    p = line.split('\t')
    if len(p) >= 3 and p[1] == 'kRSUnicode':
        try:
            cp = int(p[0][2:], 16)
        except ValueError:
            continue
        if not in_cjk(cp):
            continue
        mo = re.match(r'\s*(\d+)', p[2])
        if mo:
            rd = num2rad.get(int(mo.group(1)))
            if rd:
                kr[chr(cp)] = rd
print(f'康熙部首: {len(kr)} 字')

# ---------- 4. 繁简异体对应 ----------
VARIANT_FIELDS = {'kTraditionalVariant', 'kSimplifiedVariant', 'kZVariant',
                  'kSemanticVariant', 'kSpecializedSemanticVariant'}
rel = {}
for line in z.read('Unihan_Variants.txt').decode('utf-8').splitlines():
    if not line or line.startswith('#'):
        continue
    p = line.split('\t')
    if len(p) < 3 or p[1] not in VARIANT_FIELDS:
        continue
    try:
        src = chr(int(p[0][2:], 16))
    except ValueError:
        continue
    tgt = rel.setdefault(src, set())
    for m in re.findall(r'U\+([0-9A-Fa-f]+)', p[2]):
        v = chr(int(m, 16))
        if len(v) == 1 and v != src:
            tgt.add(v)

# ---------- 5. 生成扩展记录 ----------
std_idx = {r['c']: i for i, r in enumerate(main['chars'])}
ext, idx_of, py_index = [], {}, {}
for w, reads in py.items():
    if w in std:                                # 主库已有完整数据
        continue
    v = -1
    if w in vi:                                 # 优先官方反查索引
        v = vi[w][0][0]
    else:
        for x in rel.get(w, ()):
            if x in std_idx:
                v = std_idx[x]
                break
    rec = {'c': w, 'p': reads}
    if v >= 0:
        rec['v'] = v
    if w in kr:
        rec['r'] = kr[w]                        # 生僻字也标出部首
    i = len(ext)
    idx_of[w] = i
    ext.append(rec)
    for rd in reads:
        k = re.sub(r'[^a-zv]', '', rd.translate(TONE_MAP).lower())
        if k:
            py_index.setdefault(k, []).append(i)
print(f'扩展字库: {len(ext)} 字 (有对应正字 {sum(1 for r in ext if "v" in r)}; 有部首 {sum(1 for r in ext if "r" in r)})')

out = {'chars': ext, 'idx': idx_of, 'py': py_index}
js = 'const HANZI_EXT = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';'
with open(os.path.join(BASE, 'data_ext.js'), 'w', encoding='utf-8') as f:
    f.write(js)
size = os.path.getsize(os.path.join(BASE, 'data_ext.js'))
print(f'data_ext.js: {size/1024:.0f} KB')
print(f'扩展拼音音节: {len(py_index)}')
for probe in ['勸', '喆', '龘', '淸', '堃', '𠀀', '𪜀', '𬺰']:
    i = idx_of.get(probe)
    if i is None:
        print(f'  {probe}: (不在扩展库)')
    else:
        e = ext[i]
        tgt = f" → 正字 {main['chars'][e['v']]['c']}" if 'v' in e else ''
        print(f"  {probe}: {'/'.join(e['p'])} 部首 {e.get('r','-')}{tgt}")
