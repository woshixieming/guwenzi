#!/usr/bin/env python3
"""从现有字库及 Unihan 生成按需加载的部首/笔画/异体关系索引。"""
import argparse
import json
import re
import unicodedata
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SOURCES = {
    1: '主字库繁体对照（官方附表及基础字库）', 2: '《规范字与繁体字、异体字对照表》',
    3: 'OpenCC', 4: '開放詞典繁简索引', 5: 'Unicode kZVariant',
    6: 'Unicode 繁简字段', 7: 'Unicode 语义变体（仅供参考）',
    8: '《汉语拼音辞典》繁体字段', 9: '《汉语拼音辞典》异体字段', 10: 'CC-CEDICT',
}
SEGMENTS = [(6, 1), (29, 2), (60, 3), (91, 4), (119, 5), (146, 6),
            (166, 7), (175, 8), (186, 9), (194, 10), (200, 11), (204, 12),
            (208, 13), (210, 14), (211, 15), (213, 16), (214, 17)]
ALIASES = {9: '亻', 18: '刂', 30: '', 61: '忄⺗', 64: '扌', 85: '氵氺', 86: '灬',
           87: '爫', 93: '牜', 94: '犭', 96: '王', 113: '礻', 118: '⺮',
           120: '糹纟', 122: '罒', 130: '月', 140: '艹', 145: '衤',
           147: '见', 149: '讠', 154: '贝', 157: '足', 159: '车',
           162: '辶', 163: '阝', 167: '钅', 168: '长', 169: '门', 170: '阝',
           181: '页', 182: '风', 184: '饣', 187: '马', 195: '鱼', 196: '鸟',
           197: '卤', 199: '麦', 201: '黄', 205: '黾', 210: '齐', 211: '齿',
           212: '龙', 213: '龟'}


def read_js(name, prefix):
    return json.loads((BASE / name).read_text(encoding='utf-8')[len(prefix):].strip().rstrip(';'))


def build(check=False):
    main = read_js('data.js', 'const HANZI = ')
    ext = read_js('data_ext.js', 'const HANZI_EXT = ')
    standard = {r['c']: r for r in main['chars']}
    readings = {r['c']: r['p'] for r in main['chars'] + ext['chars']}
    entries = {}
    with zipfile.ZipFile(BASE / 'data/Unihan.zip') as archive:
        for line in archive.read('Unihan_IRGSources.txt').decode().splitlines():
            if not line or line.startswith('#'):
                continue
            cp, field, value = line.split('\t', 2)
            char = chr(int(cp[2:], 16))
            if field not in ('kRSUnicode', 'kTotalStrokes'):
                continue
            record = entries.setdefault(char, {'r': [], 's': []})
            if field == 'kRSUnicode':
                # 同一个字可能有多个归部；撇号是简化部首标记，保留部外笔画。
                for radical, remaining in re.findall(r"(\d+)'{0,3}\.(-?\d+)", value):
                    item = [int(radical), int(remaining)]
                    if item not in record['r']:
                        record['r'].append(item)
            else:
                record['s'] = sorted({int(n) for n in value.split() if n.isdecimal()})
        raw_relations = archive.read('Unihan_Variants.txt').decode().splitlines()

    def add(char, target, kind, source):
        if len(char) != 1 or char == target or target not in standard:
            return
        record = entries.setdefault(char, {'r': [], 's': []})
        relation = [target, kind, source]
        matches = record.setdefault('m', [])
        if relation not in matches:
            matches.append(relation)

    for char, links in main['variantIndex'].items():
        for index, kind in links:
            add(char, main['chars'][index]['c'], 'reference' if kind == 7 else 'traditional' if kind in (1, 3, 6, 8, 10) else 'variant', SOURCES[kind])
    for target, record in standard.items():
        for field, kind, source in [('f', 'traditional', SOURCES[1]), ('y', 'variant', SOURCES[2])]:
            for char in record.get(field, []):
                add(char, target, kind, source)
    # 不按是否有读音筛选字形；不将语义关联视为确定转换，也不做传递推断。
    for line in raw_relations:
        if not line or line.startswith('#'):
            continue
        cp, field, value = line.split('\t', 2)
        char = chr(int(cp[2:], 16))
        for codepoint in re.findall(r'U\+([0-9A-Fa-f]+)', value):
            other = chr(int(codepoint, 16))
            if field == 'kSimplifiedVariant':
                add(char, other, 'traditional', 'Unicode kSimplifiedVariant')
            elif field == 'kTraditionalVariant':
                add(other, char, 'traditional', 'Unicode kTraditionalVariant（反向）')
            elif field == 'kZVariant':
                add(char, other, 'variant', 'Unicode kZVariant')
                add(other, char, 'variant', 'Unicode kZVariant（反向）')
            elif field in ('kSemanticVariant', 'kSpecializedSemanticVariant'):
                add(char, other, 'reference', 'Unicode ' + field)
                add(other, char, 'reference', 'Unicode ' + field + '（反向）')
    for char, record in entries.items():
        if char in readings:
            record['p'] = readings[char]
        if char in standard:
            record['std'] = True
        if char in main['chaizi']:
            record['k'] = main['chaizi'][char]
        if 'm' in record:
            record['m'].sort(key=lambda x: (x[1] == 'reference', x[0], x[2]))
    radicals = []
    start = 1
    for end, strokes in SEGMENTS:
        for number in range(start, end + 1):
            symbol = chr(0x2F00 + number - 1)
            radicals.append({'id': number, 'c': unicodedata.normalize('NFKC', symbol),
                             's': strokes, 'a': ALIASES.get(number, '')})
        start = end + 1
    output = {'version': 1, 'radicals': radicals, 'chars': entries}
    path = BASE / 'assets/variant-index.json'
    serialized = json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n'
    if check:
        if not path.is_file() or path.read_text(encoding='utf-8') != serialized:
            raise SystemExit('异体检索索引缺失或已过期，请运行 python3 scripts/build_variant_index.py。')
    else:
        path.write_text(serialized, encoding='utf-8')
    print(f'异体检索索引：{len(entries)} 字，{sum(bool(r.get("m")) for r in entries.values())} 字有对应/参考关系，{path.stat().st_size / 1024**2:.2f} MiB')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只校验索引与现有输入一致，不写文件')
    build(parser.parse_args().check)
