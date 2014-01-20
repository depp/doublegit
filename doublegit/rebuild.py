import argparse
import subprocess
import os
import xml.etree.ElementTree as etree
import shutil
from . import author

class Failure(Exception):
    pass

def parse_author(elem):
    attr = 'name', 'email', 'date'
    val = []
    for a in attr:
        v = elem.get(a)
        assert v is not None
        val.append(v)
    return author.Author(*val)

class Rebuild(object):
    __slots__ = ['repo', 'indir', 'devnull']

    def __init__(self, args):
        self.repo = args.repo
        self.indir = args.indir
        self.devnull = open('/dev/null', 'wb')

    def git(self, *args, encoding='ASCII'):
        cmd = ['git', '-C', self.repo]
        cmd.extend(args)
        output = subprocess.check_output(cmd)
        if encoding is not None:
            output = output.decode(encoding)
        return output

    def run(self):
        shutil.rmtree(self.repo, ignore_errors=True)
        os.makedirs(self.repo, exist_ok=True)
        self.git('init')
        current = None
        for patch in self.get_patches():
            current = self.apply_patch(patch, current)
            assert current is not None
            print('Commit:', current)
        if current is None:
            raise Failure('No commits.')
        self.git('update-ref', 'refs/heads/master', current)

    def get_patches(self):
        patches = []
        cdir = os.path.join(self.indir, 'commit')
        for filename in os.listdir(cdir):
            i = filename.find('.')
            if i < 0:
                continue
            if filename[i:] != '.xml':
                continue
            try:
                n = int(filename[:i])
            except ValueError:
                continue
            if str(n) != filename[:i]:
                continue
            patches.append((n, filename))
        patches.sort()
        return [patch[1] for patch in patches]

    def apply_patch(self, patch, parent):
        with open(os.path.join(self.indir, 'commit', patch), 'rb') as fp:
            tree = etree.parse(fp)
        root = tree.getroot()
        if root.tag != 'commit':
            raise Failure('Unexpected tag.')

        cauthor = None
        ccommitter = None
        message = None
        for elem in root:
            tag = elem.tag
            if tag in ('create', 'delete', 'replace', 'patch'):
                path = elem.get('path')
                assert path is not None
                fullpath = os.path.join(self.repo, path)
                if tag == 'delete':
                    os.unlink(fullpath)
                    self.git('update-index', '--remove', '--', path)
                else:
                    contents = elem.text
                    if contents is not None:
                        contents = contents[1:]
                    datapath = elem.get('data')
                    if datapath is not None:
                        datapath = os.path.join(self.indir, 'data', datapath)
                    assert (datapath is None) + (contents is None) == 1
                    if tag == 'create':
                        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
                    if tag == 'create' or tag == 'replace':
                        if datapath is None:
                            with open(fullpath, 'w') as fp:
                                fp.write(contents)
                        else:
                            shutil.copyfile(datapath, fullpath)
                    elif tag == 'patch':
                        assert datapath is None
                        proc = subprocess.Popen(
                            ['patch', os.path.abspath(fullpath)],
                            stdin=subprocess.PIPE,
                            stdout=self.devnull)
                        proc.communicate(
                            ('--- old\n+++ new\n' + contents).encode('UTF-8'))
                        if proc.returncode:
                            raise Failure('Patch failed.')
                    else:
                        assert False
                    self.git('update-index', '--add', '--', path)
            elif tag == 'author':
                assert cauthor is None
                cauthor = parse_author(elem)
            elif tag == 'committer':
                assert ccommitter is None
                ccommitter = parse_author(elem)
            elif tag == 'message':
                assert message is None
                message = elem.text
                assert message
                message = message[1:]

        assert cauthor is not None
        if ccommitter is None:
            ccommitter = cauthor
        assert message is not None

        tree = self.git('write-tree').strip()

        cmd = ['git', '-C', self.repo, 'commit-tree', tree]
        if parent is not None:
            cmd.extend(('-p', parent))
        env = dict(os.environ)
        env.update({
            'GIT_AUTHOR_NAME': cauthor.name,
            'GIT_AUTHOR_EMAIL': cauthor.email,
            'GIT_AUTHOR_DATE': cauthor.date,
            'GIT_COMMITTER_NAME': ccommitter.name,
            'GIT_COMMITTER_EMAIL': ccommitter.email,
            'GIT_COMMITTER_DATE': ccommitter.date,
        })
        proc = subprocess.Popen(
            cmd, env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)
        output, error = proc.communicate(message.encode('UTF-8'))
        if proc.returncode:
            raise Failure('Failed to commit.')
        return output.decode('ASCII').strip()

    @classmethod
    def main(class_):
        p = argparse.ArgumentParser(
            description='Rebuilds a Git repo from patches.')
        p.add_argument('indir', help='path to patches')
        p.add_argument('repo', help='path to repository')
        args = p.parse_args()
        obj = class_(args)
        obj.run()

if __name__ == '__main__':
    Rebuild.main()
