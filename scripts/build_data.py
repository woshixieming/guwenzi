#!/usr/bin/env python3
"""
古文字研究网站 - 数据生成脚本
输入: data/level-*.txt (规范汉字表8105), data/gsc_pinyin.csv (拼音/部首/笔画/繁体), data/zhuan_coverage.txt (篆书覆盖)
      data/guifanyi.txt (规范字与繁体字异体字对照表), data/fanjian_suoyin.txt (繁简索引)
      data/opencc_ts.txt (OpenCC 繁->简), data/chaizi-jt.txt / chaizi-ft.txt (拆字)
输出: data.js (前端数据文件)
"""
import csv, json, os, re

BASE = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(BASE, 'data')

# ---------- 1. 规范汉字表 (8105) ----------
levels = {}
for lv, fn in [(1, 'level-1.txt'), (2, 'level-2.txt'), (3, 'level-3.txt')]:
    with open(os.path.join(DATA, fn), encoding='utf-8') as f:
        for line in f:
            ch = line.strip()
            if len(ch) == 1:
                levels[ch] = lv
print(f'规范汉字表: {len(levels)} 字')

# ---------- 2. 拼音/部首/笔画/繁体 ----------
rows = list(csv.DictReader(open(os.path.join(DATA, 'gsc_pinyin.csv'), encoding='utf-8')))
print(f'CSV: {len(rows)} 行')

# ---------- 3. 声调剥离 ----------
# 声调剥离：u 行与 ü 行必须分开 —— 否则 shū→shü 使「shu/lu/nu」等音节索引整体失效
TONE_MAP = str.maketrans(dict(
    [ord(a), ord(b)] for src, dst in
    [('āáǎà', 'aaaa'), ('ēéěè', 'eeee'), ('īíǐì', 'iiii'), ('ōóǒò', 'oooo'),
     ('ūúǔù', 'uuuu'), ('ǖǘǚǜ', 'vvvv'), ('ü', 'v'), ('ńňǹ', 'nnn'), ('ḿ', 'm')]
    for a, b in zip(src, dst)))
def strip_tone(p):
    return p.translate(TONE_MAP).replace('ü', 'v').replace('v', 'v')

# ---------- 4. 各书体字形覆盖 ----------
# 缺失位掩码: kai=1 song=2 mao=4 xing=8 cao=16 zhuan=32 orac(甲骨)=64 seal(说文小篆)=128
# 前五体为本地网页书法字库，篆书与古文字字体亦从本地加载
COV_BITS = [('kai',1),('song',2),('mao',4),('xing',8),('cao',16)]
LOCAL_BITS = [('zhuan',32),('orac',64),('seal',128)]   # 本地字体：峄山碑 / 甲骨文 / 说文小篆
cov_sets = {}
for k,b in COV_BITS + LOCAL_BITS:
    p = os.path.join(DATA, f'coverage_{k}.txt')
    cov_sets[k] = set(open(p, encoding='utf-8').read()) if os.path.exists(p) else set()
    print(f'  {k}: {len(cov_sets[k] & set(levels))}/{len(levels)} (共 {len(cov_sets[k])} 字含表外)')

# ---------- 4b. 规范字与繁体字、异体字对照表 (官方附表1) ----------
# 格式: 序号 \t 规范字 \t 繁体(圆括号) \t 异体(方括号)；序号列 "〃" 表示承接上一规范字
gy_fan, gy_yi = {}, {}          # 规范字 -> [繁体...] / [异体...]
_cur = None
for line in open(os.path.join(DATA, 'guifanyi.txt'), encoding='utf-8'):
    if not line.strip():
        continue
    cols = line.split('\t')
    head = cols[0].strip()
    if re.match(r'^\d+$', head):
        _cur = cols[1].strip()
        gy_fan.setdefault(_cur, []); gy_yi.setdefault(_cur, [])
    elif head != '〃' or _cur is None:
        continue
    rest = '\t'.join(cols[2:])
    for x in re.findall(r'[(（]([^)）]+)[)）]', rest):
        if x != '～':
            gy_fan[_cur].append(x)
    for grp in re.findall(r'\[([^\]]+)\]', rest):
        for x in grp:
            if x.strip():
                gy_yi[_cur].append(x)
print(f'官方对照表: {len(gy_fan)} 规范字, 繁体 {sum(len(v) for v in gy_fan.values())} 项, '
      f'异体 {sum(len(v) for v in gy_yi.values())} 项')

# ---------- 4c. 繁简索引 + OpenCC 兜底 (表外俗字/旧字形) ----------
fj = {}                          # 繁/异体字 -> 规范字(首个)
for line in open(os.path.join(DATA, 'fanjian_suoyin.txt'), encoding='utf-8'):
    p = line.rstrip('\n').split('\t')
    if len(p) >= 2 and len(p[0]) == 1:
        tgt = next((x for x in p[1:] if len(x) == 1), None)
        if tgt:
            fj.setdefault(p[0], tgt)
oc = {}
for line in open(os.path.join(DATA, 'opencc_ts.txt'), encoding='utf-8'):
    if line.startswith('#'):
        continue
    p = line.rstrip('\n').split('\t')
    if len(p) >= 2 and len(p[0]) == 1:
        for x in p[1].split():
            if len(x) == 1:
                oc.setdefault(p[0], x)
                break
print(f'繁简索引: {len(fj)} 条; OpenCC: {len(oc)} 条')

# ---------- 4d. 拆字 (部件) ----------
def load_chaizi(fn):
    d = {}
    with open(os.path.join(DATA, fn), encoding='utf-8') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if not p or len(p[0]) != 1:
                continue
            schemes = [[c for c in s.split() if c] for s in p[1:] if s.strip()]
            if schemes:
                d[p[0]] = schemes
    return d
chaizi = load_chaizi('chaizi-jt.txt')
chaizi_ft = load_chaizi('chaizi-ft.txt')
print(f'拆字: 简体 {len(chaizi)} 字, 繁体 {len(chaizi_ft)} 字')

# ---------- 4e. Unicode 官方异体字库 (Unihan Variants) ----------
# 产出: [(源字, 变体字)], 由调用方按规范字表定向；类型 5=异体 6=繁简 7=通假
def load_unihan_variants():
    zp = os.path.join(DATA, 'Unihan.zip')
    if not os.path.exists(zp):
        print('  (未找到 Unihan.zip，跳过)')
        return []
    import zipfile
    with zipfile.ZipFile(zp) as z:
        txt = z.read('Unihan_Variants.txt').decode('utf-8')
    kind = {'kZVariant': 5, 'kTraditionalVariant': 6, 'kSimplifiedVariant': 6,
            'kSemanticVariant': 7, 'kSpecializedSemanticVariant': 7}
    out = []
    for line in txt.splitlines():
        if not line or line.startswith('#'):
            continue
        p = line.split('\t')
        if len(p) < 3 or p[1] not in kind:
            continue
        try:
            src = chr(int(p[0][2:], 16))
        except ValueError:
            continue
        for m in re.findall(r'U\+([0-9A-Fa-f]+)', p[2]):
            v = chr(int(m, 16))
            if len(v) == 1 and v != src:
                out.append((src, v, kind[p[1]]))
    return out
unihan = load_unihan_variants()
if unihan:
    print(f'Unihan 变体关系: {len(unihan)} 组')

# ---------- 4e2. char_base(开源《汉字字典》) 繁体/异体字段 ----------
# JSON Lines 格式，每行一条：{"char":"厂","traditional":"廠","variant":"廼迺", ...}
# traditional 为繁体、variant 为异体(可多字)。属二手整理数据，优先级低于官方对照表
# 与 Unicode 官方库，仅用于补足前几源未覆盖的字（类型 8=繁体 / 9=异体）。
cb_rel = []                                   # [(正字, 变体字, 类型)]
cb_st, cb_fq = {}, {}                         # 字 -> 字形结构码 / 字 -> 使用频度分级
_cb_path = os.path.join(DATA, 'char_base.json')
if os.path.exists(_cb_path):
    with open(_cb_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip().rstrip(',')
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            w = o.get('char')
            if not w or len(w) != 1:
                continue
            for fld, t in (('traditional', 8), ('variant', 9)):
                for x in (o.get(fld) or ''):
                    if len(x) == 1 and x != w:
                        cb_rel.append((w, x, t))
            # 字形结构（D0 独体 / H2 左窄右宽 等 26 种）与使用频度（0 最常用 → 5 表外生僻）
            st = o.get('structure')
            if st:
                cb_st[w] = st
            fq = o.get('frequency')
            if isinstance(fq, int):
                cb_fq[w] = fq
    print(f'char_base 繁体/异体关系: {len(cb_rel)} 对; 结构 {len(cb_st)} 字; 频度 {len(cb_fq)} 字')
else:
    print('  (未找到 char_base.json，跳过)')

# ---------- 4e3. CC-CEDICT 字级繁简 ----------
# 词条格式: 繁体 简体 [pin1 yin1] /释义/释义/ —— 仅取「单字词条」且繁简不同形者，
# 作为 OpenCC / 繁简索引之外的第二繁简兜底源（类型 10）。
cedict_rel = []
_cc_path = next((os.path.join(DATA, fn) for fn in
                 ('cedict_ts.u8', 'cedict.txt.gz', 'cedict.txt')
                 if os.path.exists(os.path.join(DATA, fn))), None)
if _cc_path:
    import gzip
    _opener = gzip.open if _cc_path.endswith('.gz') else open
    try:
        with _opener(_cc_path, 'rt', encoding='utf-8') as f:
            for line in f:
                if not line or line.startswith('#'):
                    continue
                sp = line.find(' [')
                if sp < 0:
                    continue
                pair = line[:sp].split()
                if len(pair) == 2 and len(pair[0]) == 1 and len(pair[1]) == 1 and pair[0] != pair[1]:
                    cedict_rel.append((pair[0], pair[1]))
        cedict_rel = list(dict.fromkeys(cedict_rel))
        print(f'CC-CEDICT 字级繁简: {len(cedict_rel)} 对')
    except Exception as e:
        print('  (CC-CEDICT 解析失败:', e, ')')
else:
    print('  (未找到 CC-CEDICT，跳过)')

# ---------- 4f. 传统部首(康熙) ----------
# 现代规范归部与《康熙字典》归部常不一致（如「劝」现代归又部、康熙归力部），
# 家谱/古籍查字习惯用传统归部，故两套部首并存。
krs = {}                          # 码位 -> 康熙部首编号
try:
    import zipfile
    _zp = os.path.join(DATA, 'Unihan.zip')
    with zipfile.ZipFile(_zp) as z:
        _txt = z.read('Unihan_IRGSources.txt').decode('utf-8')
    for line in _txt.splitlines():
        if not line or line.startswith('#'):
            continue
        p = line.split('\t')
        if len(p) >= 3 and p[1] == 'kRSUnicode':
            try:
                cp = int(p[0][2:], 16)
            except ValueError:
                continue
            mo = re.match(r"\s*(\d+)", p[2])
            if mo:
                krs[cp] = int(mo.group(1))
except Exception as e:
    print('  (康熙部首数据不可用:', e, ')')
print(f'康熙部首编号: {len(krs)} 字')

# 康熙 214 部笔画数（按原书编次分段：一画 1-6、二画 7-29 … 十八画 214）
# 用于传统归部栏按《康熙字典》原书顺序（笔画→编号）排布，符合古籍查字习惯
KX_SEG = [(6, 1), (29, 2), (60, 3), (91, 4), (119, 5), (146, 6), (166, 7), (175, 8),
          (186, 9), (194, 10), (200, 11), (204, 12), (206, 13), (208, 14), (210, 15),
          (211, 16), (213, 17), (214, 18)]
kx_stroke, _s = {}, 1
for _end, _st in KX_SEG:
    for _n in range(_s, _end + 1):
        kx_stroke[_n] = _st
    _s = _end + 1

# ---------- 5. 生成记录 ----------
records = []
missing = []
for r in rows:
    w = r['word'].strip()
    if w not in levels:
        continue
    # 多音字: 空格分隔; 过滤掉非拼音杂质(如注音符号)
    pys = [p for p in re.split(r'[\s,]+', r['pinyin'].strip()) if re.match(r'^[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹḿm̀]+$', p)]
    trad = r['traditional'].strip()
    # 繁体与简体同形则置空
    if trad == w:
        trad = ''
    # 书体缺失位掩码（六体书法字库 + 篆书 + 甲骨 + 说文小篆）
    m = 0
    for k, b in COV_BITS + LOCAL_BITS:
        if w not in cov_sets[k]: m |= b
    # 官方对照表的繁体/异体；CSV 自带繁体并入繁体列(去重保序)
    fan = list(dict.fromkeys([x for x in gy_fan.get(w, []) if x != w]))
    if trad and trad not in fan:
        fan.append(trad)
    yi = list(dict.fromkeys([x for x in gy_yi.get(w, []) if x != w]))
    # 部首: CSV 可能给多个（如「又、鸟」）或带说明（如「一字头」），拆成集合
    rads = []
    for part in re.split(r'[、,，/;；]', r['radical'].strip()):
        part = re.sub(r'(字头|字旁|旁|部|底|头)$', '', part.strip())
        if len(part) == 1:
            rads.append(part)
    rads = list(dict.fromkeys(rads))
    if not rads:
        missing.append(w)
    rec = {
        'c': w,                      # 字
        'p': pys,                    # 带调拼音
        'r': rads[0] if rads else '',  # 现代部首(主)
        'ra': rads[1:] if len(rads) > 1 else [],   # 其余可检部首
        'kr': '',                    # 传统(康熙)部首，稍后回填
        'kn': 0,                     # 康熙部首编号
        's': int(r['stroke_count']), # 笔画
        't': trad,                   # 繁体(同形则空)
        'lv': levels[w],             # 1/2/3 级
        'm': m,                      # 书体缺失位掩码(0=六体齐全)
        'f': fan,                    # 繁体字形列表
        'y': yi,                     # 异体字形列表
        'k': chaizi.get(w) or chaizi_ft.get(w) or [],  # 拆字方案
    }
    # 字形结构与使用频度（char_base 提供；缺省不写字段，避免无谓增大体积）
    if w in cb_st: rec['st'] = cb_st[w]
    if w in cb_fq: rec['fq'] = cb_fq[w]
    records.append(rec)

records.sort(key=lambda x: levels.get(x['c'], 9))  # 按级别排序
print(f'有效记录: {len(records)}; 8105 表内但 CSV 缺失: {len(set(levels) - {r["c"] for r in records})}')
if missing:
    print('缺失:', missing[:20])

# ---------- 6. 索引 ----------
# 拼音索引: 无调音节 -> [记录下标]
pinyin_index = {}
for i, rec in enumerate(records):
    for p in rec['p']:
        key = strip_tone(p)
        pinyin_index.setdefault(key, [])
        if i not in pinyin_index[key]:
            pinyin_index[key].append(i)

# 笔画索引: 总笔画数 -> [记录下标]，records 已按级别排序，故同笔画内常用字在前
stroke_index = {}
for i, rec in enumerate(records):
    if rec['s']:
        stroke_index.setdefault(rec['s'], []).append(i)

# 部首索引(现代规范): 部首 -> [记录下标], 部首按字数降序
radical_index = {}
for i, rec in enumerate(records):
    for rd in [rec['r']] + rec['ra']:
        if rd:
            radical_index.setdefault(rd, []).append(i)
radical_order = sorted(radical_index.keys(), key=lambda k: -len(radical_index[k]))

# 康熙部首索引: 编号 -> 现代部首字符（收字多的优先，保证「氵」优先于「水」这类变形）
num2rad = {}
for rd in radical_order:
    n = krs.get(ord(rd)) if len(rd) == 1 else None
    if n and n not in num2rad:
        num2rad[n] = rd
print(f'康熙编号→部首字符映射: {len(num2rad)} 个编号')
# 回填每字的传统部首；现代部首缺失的生僻字用康熙归部兜底，避免它们无法按部首检索
radical_index_k = {}
radical_k_num = {}                # 部首字符 -> 康熙编号（用于按原书笔画序排布）
n_kr_diff = n_kr_fill = 0
for i, rec in enumerate(records):
    n = krs.get(ord(rec['c']))
    if n:
        rd = num2rad.get(n) or chr(0x2F00 + n - 1)   # 无对应现代部首时用康熙部首字符
        rec['kn'] = n
        if not rec['r']:
            rec['r'] = rd
            n_kr_fill += 1
        elif rd != rec['r']:
            rec['kr'] = rd
            n_kr_diff += 1
    kr = rec['kr'] or rec['r']                        # 传统归部与现代相同则沿用
    if kr:
        radical_index_k.setdefault(kr, []).append(i)
        if n and kr not in radical_k_num:
            radical_k_num[kr] = n
# 传统部首按《康熙字典》原书顺序：先笔画数、再部首编号（同部收字多寡不再影响次序）
radical_order_k = sorted(
    radical_index_k.keys(),
    key=lambda k: (kx_stroke.get(radical_k_num.get(k, 0), 99), radical_k_num.get(k, 999)))
radicals_k_stroke = [kx_stroke.get(radical_k_num.get(k, 0), 0) for k in radical_order_k]
n_kx_nan = sum(1 for s in radicals_k_stroke if not s)
print(f'传统(康熙)部首: {len(radical_order_k)} 部; 与现代归部不同: {n_kr_diff} 字; '
      f'现代部首缺失由康熙归部补齐: {n_kr_fill} 字; 未能定笔画: {n_kx_nan} 部')

# ---------- 6b. 繁/异体字反向索引 (表外字 -> 规范字) ----------
# 类型: 1=官方繁体 2=官方异体 3=通用繁体(OpenCC) 4=异体/俗字(繁简索引)
char_of = {r['c']: i for i, r in enumerate(records)}
variant_index = {}
def push(v, idx, t):
    if len(v) != 1 or v in char_of:      # 规范字本身直接可查，不进反查表
        return
    lst = variant_index.setdefault(v, [])
    if not any(x[0] == idx for x in lst):
        lst.append([idx, t])
for w, xs in gy_fan.items():
    if w in char_of:
        for x in xs:
            push(x, char_of[w], 1)
for w, xs in gy_yi.items():
    if w in char_of:
        for x in xs:
            push(x, char_of[w], 2)
for v, w in oc.items():
    if w in char_of:
        if v not in variant_index:
            push(v, char_of[w], 3)
for v, w in fj.items():
    if w in char_of:
        if v not in variant_index:
            push(v, char_of[w], 4)
# Unicode 异体字库兜底（最低优先级，双向定向到规范字）
n_uni = 0
for src, var, t in unihan:
    if src not in char_of and var in char_of and src not in variant_index:
        push(src, char_of[var], t); n_uni += 1
    elif var not in char_of and src in char_of and var not in variant_index:
        push(var, char_of[src], t); n_uni += 1
print(f'  Unihan 补充反查: {n_uni} 字')
# char_base(开源《汉字字典》) 补充（二手数据，类型 8/9，优先级最低；双向定向）
n_cb = 0
for w, x, t in cb_rel:
    if x not in char_of and w in char_of and x not in variant_index:
        push(x, char_of[w], t); n_cb += 1
    elif w not in char_of and x in char_of and w not in variant_index:
        push(w, char_of[x], t); n_cb += 1
print(f'  char_base 补充反查: {n_cb} 字')
# CC-CEDICT 字级繁简补充（类型 10，仅在前面所有来源都未收录时生效）
n_cc = 0
for ft, jt in cedict_rel:
    if ft not in char_of and jt in char_of and ft not in variant_index:
        push(ft, char_of[jt], 10); n_cc += 1
    elif jt not in char_of and ft in char_of and jt not in variant_index:
        push(jt, char_of[ft], 10); n_cc += 1
if cedict_rel:
    print(f'  CC-CEDICT 补充反查: {n_cc} 字')
# 已由官方收录的，去掉更低优先级的重复项
for v, lst in variant_index.items():
    best = min(t for _, t in lst)
    variant_index[v] = [[i, t] for i, t in lst if t == best] or lst
n_by_t = {}
for lst in variant_index.values():
    n_by_t[lst[0][1]] = n_by_t.get(lst[0][1], 0) + 1
print(f'反查索引: {len(variant_index)} 字 ' +
      ' '.join(f'T{t}={n_by_t[t]}' for t in sorted(n_by_t)))

# ---------- 6c. 拆字表 (仅保留规范字与异体字库所需) ----------
need = set(char_of) | set(variant_index)
chaizi_out = {}
for w in need:
    s = chaizi.get(w) or chaizi_ft.get(w)
    if s:
        chaizi_out[w] = s
print(f'拆字表输出: {len(chaizi_out)} 字')

# ---------- 7. 输出 ----------
out = {
    'chars': records,
    'pinyinIndex': pinyin_index,
    'radicalIndex': radical_index,
    'radicals': radical_order,
    'radicalIndexK': radical_index_k,   # 传统(康熙)部首 -> [下标]
    'radicalsK': radical_order_k,
    'radicalsKS': radicals_k_stroke,    # 与 radicalsK 平行：各部首笔画数
    'strokeIndex': stroke_index,        # 总笔画数 -> [下标]（笔画检字）
    'variantIndex': variant_index,   # 表外繁/异体字 -> [[规范字下标, 类型]]
    'chaizi': chaizi_out,            # 字 -> [[部件...], ...] 拆字方案
}
js = 'const HANZI = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';'
with open(os.path.join(BASE, 'data.js'), 'w', encoding='utf-8') as f:
    f.write(js)
size = os.path.getsize(os.path.join(BASE, 'data.js'))
print(f'data.js: {size/1024:.0f} KB')
print(f'拼音音节数: {len(pinyin_index)}, 现代部首 {len(radical_index)} 部, 传统部首 {len(radical_index_k)} 部')
print(f'八体齐全: {sum(1 for r in records if r["m"]==0)}; 缺书体: {sum(1 for r in records if r["m"]>0)}')
for k, b in COV_BITS + LOCAL_BITS:
    print(f'  缺{k}: {sum(1 for r in records if r["m"] & b)}')
print(f'繁体不同形: {sum(1 for r in records if r["t"])}')
print(f'有官方繁体: {sum(1 for r in records if r["f"])}, 有官方异体: {sum(1 for r in records if r["y"])}')
print(f'有拆字: {sum(1 for r in records if r["k"])}')
print(f'有结构: {sum(1 for r in records if "st" in r)}, 有频度: {sum(1 for r in records if "fq" in r)}')
_s = sorted(stroke_index)
print(f'笔画检字: {len(_s)} 档 ({_s[0]}–{_s[-1]} 画), 最密 {max(_s, key=lambda k: len(stroke_index[k]))} 画 '
      f'{len(stroke_index[max(_s, key=lambda k: len(stroke_index[k]))])} 字')
# 家谱高频场景抽样自检
for probe in ['喆', '淸', '堃', '峯', '敎', '書']:
    hit = variant_index.get(probe)
    tgt = ', '.join(f'{records[i]["c"]}(类型{t})' for i, t in hit) if hit else '(无)'
    print(f'  反查 {probe} → {tgt}')
print('样例:', json.dumps(records[0], ensure_ascii=False))
