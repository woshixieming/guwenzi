#!/usr/bin/env python3
"""下载固定版本的字体和笔顺资源，或用 --check 离线校验已有资源。"""
import argparse
import base64
import hashlib
import json
import posixpath
import re
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

BASE = Path(__file__).resolve().parent.parent
MANIFEST = BASE / 'assets' / 'offline-manifest.json'
PACKAGES = [
    ('kai', 'cn-fontsource-lxgw-wen-kai-screen', '1.0.6'),
    ('song', 'cn-fontsource-source-han-serif-sc-vf-regular', '1.0.1'),
    ('mao', '@fontsource/ma-shan-zheng', '5.3.1'),
    ('xing', '@fontsource/zhi-mang-xing', '5.3.0'),
    ('cao', '@fontsource/liu-jian-mao-cao', '5.3.0'),
    ('writer', 'hanzi-writer', '3.7.0'),
    ('strokes', 'hanzi-writer-data', '2.0.1'),
]
EXTRA_LICENSES = {
    'kai': 'https://raw.githubusercontent.com/lxgw/LxgwWenKai-Screen/main/OFL.txt',
    'song': 'https://raw.githubusercontent.com/adobe-fonts/source-han-serif/release/LICENSE.txt',
}
URL = re.compile(r'url\(\s*[\'"]?([^\)\'\"]+)[\'"]?\s*\)')


def read_url(url):
    with urlopen(url, timeout=45) as response:
        return response.read()


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError(f'不安全的资源路径：{name}')
    return path


def download_package(item, cache):
    key, name, version = item
    metadata = json.loads(read_url(f'https://registry.npmjs.org/{name}/{version}'))
    target = cache / (name.replace('/', '-').replace('@', '') + '-' + version + '.tgz')
    if not target.exists():
        target.write_bytes(read_url(metadata['dist']['tarball']))
    algorithm, expected = metadata['dist']['integrity'].split('-', 1)
    actual = base64.b64encode(hashlib.new(algorithm, target.read_bytes()).digest()).decode()
    if actual != expected:
        raise ValueError(f'下载包校验失败：{name}@{version}')
    extra_license = None
    if key in EXTRA_LICENSES:
        license_path = cache / f'{key}-OFL.txt'
        if not license_path.exists():
            license_path.write_bytes(read_url(EXTRA_LICENSES[key]))
        extra_license = license_path.read_bytes()
    return key, metadata, target, extra_license


def export_package(package, files):
    key, metadata, archive_path, extra_license = package
    is_font = key not in ('writer', 'strokes')
    destination = f'fonts/web/{key}' if is_font else f'assets/{metadata["name"]}'

    def write(name, content):
        relative = f'{destination}/{safe_path(name)}'
        target = BASE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        files[relative] = {'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}

    with tarfile.open(archive_path, 'r:gz') as archive:
        members = {}
        for member in archive.getmembers():
            if member.isfile() and member.name.startswith('package/'):
                name = member.name[len('package/'):]
                safe_path(name)
                members[name] = member

        def read(name):
            return archive.extractfile(members[name]).read()

        for name in members:
            filename = PurePosixPath(name).name.lower()
            if filename == 'readme.md' or any(s in filename for s in ('license', 'ofl', 'copying', 'arphic')):
                write(name, read(name))
        if extra_license:
            write('OFL.txt', extra_license)

        if is_font:
            entry = 'font.css' if 'font.css' in members else 'index.css'
            css = read(entry).decode('utf-8')

            def local_sources(match):
                # 保留页面已有的 WOFF2 字形与 unicode-range，不重复打包 WOFF。
                sources = []
                for reference in URL.findall(match[1]):
                    reference = reference.strip()
                    parsed = urlsplit(reference)
                    if not parsed.path.lower().endswith('.woff2'):
                        continue
                    if parsed.scheme or parsed.netloc:
                        raise ValueError(f'字体 CSS 含外部字体地址：{reference}')
                    name = posixpath.normpath(unquote(parsed.path))
                    safe_path(name)
                    write(name, read(name))
                    sources.append(f"url('{reference}') format('woff2')")
                if not sources:
                    raise ValueError(f'缺少 WOFF2 源：{metadata["name"]}')
                return 'src: ' + ', '.join(sources) + ';'

            css = re.sub(r'src\s*:\s*([^;]+);', local_sources, css)
            write('font.css', css.encode('utf-8'))
        elif key == 'writer':
            for name in ('dist/hanzi-writer.min.js', 'dist/hanzi-writer.min.js.map'):
                if name in members:
                    write(PurePosixPath(name).name, read(name))
        else:
            for name in members:
                path = PurePosixPath(name)
                if len(path.parts) == 1 and path.suffix == '.json' and len(path.stem) == 1:
                    write(name, read(name))

    result = {
        'name': metadata['name'], 'version': metadata['version'],
        'tarball': metadata['dist']['tarball'], 'integrity': metadata['dist']['integrity'],
        'directory': destination, 'license': metadata.get('license'),
    }
    if key in EXTRA_LICENSES:
        result['licenseSource'] = EXTRA_LICENSES[key]
    return result


def check_assets():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    strokes = 0
    for name, expected in manifest['files'].items():
        content = (BASE / safe_path(name)).read_bytes()
        if len(content) != expected['size'] or hashlib.sha256(content).hexdigest() != expected['sha256']:
            raise ValueError(f'本地资源不完整或已改变：{name}')
        if name.endswith('/font.css'):
            for reference in URL.findall(content.decode('utf-8')):
                parsed = urlsplit(reference.strip())
                if parsed.scheme or parsed.netloc:
                    raise ValueError(f'仍存在外部字体请求：{name}')
                target = (PurePosixPath(name).parent / unquote(parsed.path)).as_posix()
                if target not in manifest['files']:
                    raise ValueError(f'字体文件缺失：{target}')
        if name.startswith('assets/hanzi-writer-data/') and name.endswith('.json'):
            record = json.loads(content)
            if not record.get('strokes') or len(record['strokes']) != len(record.get('medians', [])):
                raise ValueError(f'笔顺数据无效：{name}')
            strokes += 1
    total = sum(f['size'] for f in manifest['files'].values())
    print(f'校验通过：{len(manifest["files"])} 个文件，{strokes} 字笔顺，{total / 1024**2:.1f} MiB')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只检查本地文件，不访问网络')
    parser.add_argument('--cache-dir', type=Path, help='复用已下载的 npm 压缩包')
    args = parser.parse_args()
    if args.check:
        check_assets()
        return
    files, packages = {}, []
    with tempfile.TemporaryDirectory(prefix='guwenzi-assets-') as temporary:
        cache = args.cache_dir or Path(temporary)
        cache.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=4) as executor:
            for package in executor.map(lambda item: download_package(item, cache), PACKAGES):
                packages.append(export_package(package, files))
                print(f'已保存 {package[1]["name"]}@{package[1]["version"]}', flush=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({'packages': packages, 'files': dict(sorted(files.items()))},
                                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    check_assets()


if __name__ == '__main__':
    main()
