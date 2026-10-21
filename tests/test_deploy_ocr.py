"""用真实本地 OCR 进程模拟远端，systemd/账号/权限命令全部隔离替换。"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent


class DeployOCRTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='guwenzi-ocr-deploy-')
        self.base = Path(self.temporary.name)
        self.bin = self.base / 'bin'; self.bin.mkdir()
        self.units = self.base / 'units'; self.units.mkdir()
        self.code = self.base / 'backend'
        self.config = self.base / 'private/ocr.json'
        self.web = self.base / 'website'
        self.pidfile = self.base / 'service.pid'
        self.log = self.base / 'commands.log'
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); self.port = listener.getsockname()[1]
        mock = self.bin / 'mock.py'
        mock.write_text(f'''#!{sys.executable}
import json, os, pathlib, shlex, signal, subprocess, sys, time
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
base = pathlib.Path(os.environ['MOCK_DEPLOY_ROOT'])
with (base/'commands.log').open('a') as log:
    log.write(name+' '+str(args)+'\\n')
if name == 'id':
    print('staff' if '-gn' in args else '1001' if 'guwenzi-ocr' in args and '-u' in args else '0')
elif name == 'chown':
    pass
elif name == 'install':
    cleaned=[]; i=0
    while i<len(args):
        if args[i] in ('-o','-g'): i+=2
        else: cleaned.append(args[i]); i+=1
    sys.exit(subprocess.run(['/usr/bin/install',*cleaned]).returncode)
elif name == 'sudo':
    sys.exit(subprocess.run(args[1:] if args and args[0]=='-n' else args).returncode)
elif name == 'ssh':
    i=args.index('deployer@198.51.100.10')
    assert args[args.index('-p')+1]=='2222'
    sys.exit(subprocess.run(['bash','-c',' '.join(args[i+1:])],stdin=sys.stdin).returncode)
elif name == 'scp':
    import shutil
    assert args[args.index('-P')+1]=='2222'
    shutil.copyfile(args[-2],args[-1].split(':',1)[1])
elif name == 'systemctl':
    pidfile=base/'service.pid'
    def active():
        if not pidfile.exists(): return False
        try:
            os.kill(int(pidfile.read_text()),0)
            state=subprocess.check_output(['ps','-p',pidfile.read_text(),'-o','stat='],text=True).strip()
            return bool(state) and not state.startswith('Z')
        except (OSError,subprocess.CalledProcessError): return False
    def stop():
        if active():
            try: os.kill(int(pidfile.read_text()),signal.SIGTERM)
            except ProcessLookupError: pass
            for _ in range(40):
                if not active(): break
                time.sleep(.025)
        pidfile.unlink(missing_ok=True)
    command=args[0]
    if command=='is-active': sys.exit(0 if active() else 3)
    if command in ('stop','disable'): stop()
    elif command=='restart':
        stop()
        unit=(base/'units'/('guwenzi-ocr.service')).read_text()
        start=next(line[len('ExecStart='):] for line in unit.splitlines() if line.startswith('ExecStart='))
        invocation=shlex.split(start)
        if 'bad-release' in str(pathlib.Path(invocation[1]).resolve()): sys.exit(1)
        process=subprocess.Popen(invocation,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        pidfile.write_text(str(process.pid))
else:
    raise RuntimeError('unexpected command '+name)
''')
        mock.chmod(0o755)
        for name in ('id', 'chown', 'install', 'sudo', 'ssh', 'scp', 'systemctl'):
            (self.bin / name).symlink_to(mock)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        MOCK_DEPLOY_ROOT=str(self.base), OCR_SYSTEMD_DIR=str(self.units))

    def tearDown(self):
        subprocess.run(['systemctl','stop','guwenzi-ocr'],env=self.env,capture_output=True)
        self.temporary.cleanup()

    def artifact(self, name):
        target = self.base / (name + '.tar.gz')
        with tarfile.open(target,'w:gz',format=tarfile.USTAR_FORMAT) as archive:
            for filename in ('ocr_server.py', 'ocr-config.example.json'):
                archive.add(ROOT / 'server' / filename, arcname='server/' + filename)
        return target

    def remote(self, mode, release='release-1', artifact=None, success=True):
        package = artifact or self.base / 'not-uploaded.tar.gz'
        result = subprocess.run(['bash', str(ROOT / 'scripts/deploy-ocr-remote.sh'), mode,
                                 str(self.web), str(self.code), str(self.config), 'guwenzi-ocr',
                                 str(self.port), release, str(package)], env=self.env,
                                capture_output=True,text=True,timeout=30)
        if success:
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return result

    def status(self):
        for attempt in range(30):
            try:
                with urlopen(f'http://127.0.0.1:{self.port}/api/ocr/status',timeout=3) as response:
                    return json.load(response)
            except URLError:
                if attempt == 29: raise
                time.sleep(.05)

    def test_first_deploy_config_retained_and_failed_restart_rolls_back(self):
        package=self.artifact('first')
        self.remote('install',artifact=package)
        self.assertFalse(package.exists())
        self.assertEqual(self.status(),{'configured':False})
        self.assertFalse(self.web.exists())
        unit=(self.units/'guwenzi-ocr.service').read_text()
        self.assertIn('User=guwenzi-ocr',unit)
        self.assertIn('--bind 127.0.0.1',unit)
        values=json.loads(self.config.read_text())
        values.update(enabled=True,api_key='private-fixture-only',model='vision-fixture')
        self.config.write_text(json.dumps(values))
        expected=self.config.read_bytes()
        self.remote('install','release-2',self.artifact('second'))
        self.assertEqual(self.config.read_bytes(),expected)
        self.assertEqual(self.status(),{'configured':True})
        previous=(self.code/'current').resolve()
        old_unit=(self.units/'guwenzi-ocr.service').read_bytes()
        failed=self.remote('install','bad-release',self.artifact('bad'),success=False)
        self.assertNotEqual(failed.returncode,0)
        self.assertEqual((self.code/'current').resolve(),previous)
        self.assertEqual((self.units/'guwenzi-ocr.service').read_bytes(),old_unit)
        self.assertEqual(self.status(),{'configured':True})
        self.assertEqual(self.config.read_bytes(),expected)
        self.assertNotIn('private-fixture-only',failed.stdout+failed.stderr)

    def test_preview_is_read_only_and_unmanaged_unit_is_protected(self):
        self.remote('preview')
        self.assertFalse(self.code.exists()); self.assertFalse(self.config.exists())
        self.assertFalse(self.pidfile.exists())
        unit=self.units/'guwenzi-ocr.service';unit.write_text('not managed\n')
        result=self.remote('check',success=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(unit.read_text(),'not managed\n')

    def test_reject_public_or_symlinked_config_and_unexpected_archive(self):
        self.config=self.web/'private/ocr.json'
        self.assertNotEqual(self.remote('check',success=False).returncode,0)
        self.config=self.base/'private/ocr.json';self.config.parent.mkdir()
        target=self.base/'other.json';target.write_text('{}')
        self.config.symlink_to(target)
        self.assertNotEqual(self.remote('check',success=False).returncode,0)
        self.config.unlink()
        package=self.base/'unexpected.tar.gz'
        with tarfile.open(package,'w:gz') as archive:
            archive.add(target,arcname='unexpected.json')
        self.assertNotEqual(self.remote('install',artifact=package,success=False).returncode,0)
        self.assertFalse(package.exists())
        self.assertFalse(self.code.exists())

    def test_invalid_config_does_not_replace_existing_release(self):
        self.remote('install',artifact=self.artifact('first'))
        previous=(self.code/'current').resolve()
        self.config.write_text('{invalid private configuration')
        failed=self.remote('install','next',self.artifact('next'),success=False)
        self.assertNotEqual(failed.returncode,0)
        self.assertEqual((self.code/'current').resolve(),previous)
        self.assertNotIn('invalid private configuration',failed.stdout+failed.stderr)

    def test_unhealthy_release_restores_running_previous_version(self):
        self.remote('install',artifact=self.artifact('first'))
        previous=(self.code/'current').resolve()
        broken=self.base/'unhealthy.py'
        broken.write_text((ROOT/'server/ocr_server.py').read_text().replace(
            "{'configured': bool(self.server.configured)}", "{'configured': 'invalid-status'}"))
        package=self.base/'unhealthy.tar.gz'
        with tarfile.open(package,'w:gz') as archive:
            archive.add(broken,arcname='server/ocr_server.py')
            archive.add(ROOT/'server/ocr-config.example.json',arcname='server/ocr-config.example.json')
        result=self.remote('install','unhealthy-release',package,success=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((self.code/'current').resolve(),previous)
        self.assertEqual(self.status(),{'configured':False})
        self.assertFalse(package.exists())

    def test_first_failed_install_removes_new_unit(self):
        result=self.remote('install','bad-release',self.artifact('bad'),success=False)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.units/'guwenzi-ocr.service').exists())
        self.assertFalse((self.code/'current').exists())
        self.assertFalse(self.pidfile.exists())

    def interactive(self, script, arguments, env, capture_stdout=False):
        # 在独立、无后台线程的进程里创建控制终端，避免 macOS 多线程 forkpty。
        driver = r'''import json, os, pty, select, signal, sys, time
script, arguments = sys.argv[1], json.loads(sys.argv[2])
pid, master = pty.fork()
if pid == 0:
    os.chdir('/tmp')
    if sys.argv[3]:
        fd = os.open(sys.argv[3], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.dup2(fd, 1)
        os.close(fd)
    os.execvp('bash', ['bash', script, *arguments])
output = b''
sent = 0
prompts = ['服务器 IP 或域名：', 'SSH 端口：', 'SSH 用户名：']
inputs = ['198.51.100.10', '2222', 'deployer']
reaped = False
try:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if not select.select([master], [], [], .1)[0]:
            continue
        try:
            chunk = os.read(master, 65536)
        except OSError:
            break
        if not chunk:
            break
        output += chunk
        if sent < len(prompts) and prompts[sent].encode() in output:
            os.write(master, (inputs[sent] + '\n').encode())
            sent += 1
    else:
        raise TimeoutError('interactive deploy timeout')
    _, status = os.waitpid(pid, 0)
    reaped = True
    print(json.dumps([os.waitstatus_to_exitcode(status), output.decode(errors='replace')]))
finally:
    if not reaped:
        os.killpg(pid, signal.SIGTERM)
        os.waitpid(pid, 0)
    os.close(master)
'''
        capture=self.base/'captured-stdout.txt' if capture_stdout else None
        result=subprocess.run([sys.executable,'-c',driver,str(script),json.dumps(arguments),str(capture) if capture else ''],
                              env=env,capture_output=True,text=True,timeout=35)
        self.assertEqual(result.returncode,0,result.stderr)
        code,output=json.loads(result.stdout)
        return code,output+(capture.read_text() if capture else '')

    def test_main_ocr_only_upload_and_offline_checks(self):
        project=self.base/'project'
        (project/'scripts').mkdir(parents=True);(project/'server').mkdir()
        for name in ('deploy-artifact.sh','deploy-ocr-remote.sh'):
            shutil.copy2(ROOT/'scripts'/name,project/'scripts'/name)
        for name in ('ocr_server.py','ocr-config.example.json'):
            shutil.copy2(ROOT/'server'/name,project/'server'/name)
        env=dict(self.env,DEPLOY_PATH=str(self.web),OCR_DEPLOY_PATH=str(self.code),
                 OCR_CONFIG_PATH=str(self.config),OCR_PORT=str(self.port),RUN_CHECK='0')
        script=project/'scripts/deploy-artifact.sh'
        result=subprocess.run(['bash',str(script),'--ocr-only','--dry-run'],env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse(self.log.exists())
        code,output=self.interactive(script,['--ocr-only','--preview'],env)
        self.assertEqual(code,0,output);self.assertFalse(self.code.exists())
        code,output=self.interactive(script,['--ocr-only'],env,capture_stdout=True)
        self.assertEqual(code,0,output)
        self.assertEqual(self.status(),{'configured':False})
        self.assertFalse(self.web.exists())
        self.assertNotIn('rsync',self.log.read_text())

    def test_combined_incremental_and_full_website_deployment(self):
        project=self.base/'project'
        (project/'scripts').mkdir(parents=True);(project/'server').mkdir()
        for name in ('deploy-artifact.sh','deploy-ocr-remote.sh'):
            shutil.copy2(ROOT/'scripts'/name,project/'scripts'/name)
        for name in ('ocr_server.py','ocr-config.example.json'):
            shutil.copy2(ROOT/'server'/name,project/'server'/name)
        for name in ('index.html','data.js','data_ext.js','hwset.js'):
            (project/name).write_text('website fixture')
        for name in ('assets','fonts','defs','words'):
            (project/name).mkdir();(project/name/'fixture.txt').write_text('resource fixture')
        env=dict(self.env,DEPLOY_PATH=str(self.web),OCR_DEPLOY_PATH=str(self.code),
                 OCR_CONFIG_PATH=str(self.config),OCR_PORT=str(self.port),RUN_CHECK='0')
        script=project/'scripts/deploy-artifact.sh'
        code,output=self.interactive(script,['--with-ocr','--preview'],env)
        self.assertEqual(code,0,output)
        self.assertFalse(self.web.exists());self.assertFalse(self.code.exists())
        code,output=self.interactive(script,['--with-ocr'],env)
        self.assertEqual(code,0,output)
        self.assertEqual((self.web/'index.html').read_text(),'website fixture')
        self.assertFalse((self.web/'server').exists())
        self.assertEqual(self.status(),{'configured':False})
        (project/'index.html').write_text('full fixture')
        code,output=self.interactive(script,['--full','--with-ocr'],env)
        self.assertEqual(code,0,output)
        self.assertEqual((self.web/'index.html').read_text(),'full fixture')
        self.assertEqual(self.status(),{'configured':False})


if __name__=='__main__':unittest.main()
