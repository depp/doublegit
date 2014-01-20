import argparse
import subprocess
from . import author
import collections
import xml.etree.ElementTree as etree
import os
import shutil

Commit = collections.namedtuple(
    'Commit', 'parents tree author committer message')

Entry = collections.namedtuple('Entry', 'hash executable')

def git_dir(path):
    out = subprocess.check_output(
        ['git', 'rev-parse', '--git-dir'],
        cwd=path).decode('ASCII').strip()
    return os.path.join(path, out)

class Failure(Exception):
    pass

def author_attrib(author):
    return {
        'name': author.name,
        'email': author.email,
        'date': author.date
    }

class Extract(object):
    __slots__ = ['repo', 'outdir', 'paths_used', 'blobs']

    def __init__(self, args):
        self.repo = git_dir(args.repo)
        self.outdir = args.outdir
        self.paths_used = set()
        self.blobs = {}

    def git(self, *args, encoding='ASCII'):
        cmd = ['git', '--git-dir=' + self.repo]
        cmd.extend(args)
        output = subprocess.check_output(cmd)
        if encoding is not None:
            output = output.decode(encoding)
        return output

    def get_ref(self, ref):
        """Get a ref from the Git repository."""
        try:
            output = self.git('show-ref', '--', ref)
        except subprocess.CalledProcessError as ex:
            raise Failuer('Could not find ref: {!r}'.format(ref))
        return output.split()[0]

    def run(self):
        revs = self.git('rev-list', '--reverse', 'master').splitlines()
        shutil.rmtree(self.outdir, ignore_errors=True)
        for n, rev in enumerate(revs, 1):
            self.extract_rev(n, rev)

    def read_commit(self, rev):
        output = self.git('cat-file', 'commit', rev).splitlines()
        headers = {}
        message = []
        parents = []
        for n, line in enumerate(output):
            if not line:
                message = output[n+1:]
                break
            name, rest = line.split(' ', 1)
            if name == 'parent':
                parents.append(rest)
            else:
                headers[name] = rest
        return Commit(
            tuple(parents),
            headers['tree'],
            author.parse_author(headers['author']),
            author.parse_author(headers['committer']),
            ''.join(line + '\n' for line in message))

    def read_tree(self, tree):
        output = self.git('ls-tree', '-z', '--full-tree', '-r', tree)
        entries = {}
        for entry in output.split('\0'):
            if not entry:
                continue
            i = entry.index('\t')
            mode, etype, sha = entry[:i].split(' ')
            path = entry[i+1:]
            entries[path] = Entry(sha, bool(int(mode, 8) & 0o100))
        return entries

    def read_blob(self, blob):
        return self.git('cat-file', 'blob', blob, encoding=None)

    def diff_file_contents(self, path, entry1, entry2):
        if entry1 == entry2:
            return None
        if entry2 is None:
            return etree.Element('delete')
        data2 = self.read_blob(entry2.hash)
        try:
            text2 = data2.decode('UTF-8')
        except UnicodeDecodeError:
            dpath = self.extract_data(path, entry2.hash, data2)
            return etree.Element(
                'create' if entry1 is None else 'replace',
                {'data': dpath})
        if entry1 is None:
            e = etree.Element('create')
            e.text = '\n' + text2
            return e
        data1 = self.read_blob(entry1.hash)
        try:
            data1.decode('UTF-8')
        except UnicodeDecodeError:
            e = etree.Element('replace')
            e.text = '\n' + text2
            return e
        diff = self.git('diff', entry1.hash, entry2.hash)
        diff = diff.splitlines()
        for i, line in enumerate(diff):
            if line.startswith('+++'):
                diff = diff[i+1:]
                break
        e = etree.Element('patch')
        e.text = '\n' + ''.join(line + '\n' for line in diff)
        return e

    def diff_file(self, path, entry1, entry2):
        e = self.diff_file_contents(path, entry1, entry2)
        if entry2 is not None:
            oldexec = False if entry1 is None else entry1.executable
            if entry2.executable != oldexec:
                e.set('executable', str(entry2.executable).lower())
        return e

    def extract_data(self, path, sha, data):
        try:
            return self.blobs[sha]
        except KeyError:
            pass
        dirpath, filename = os.path.split(path)
        i = filename.find('.')
        if i < 0:
            i = len(filename)
        base = filename[:i]
        ext = filename[i:]
        counter = 1
        while True:
            filename = '{}.v{}{}'.format(base, counter, ext)
            relpath = os.path.join(dirpath, filename)
            if relpath in self.paths_used:
                i += 1
                continue
            break
        self.blobs[sha] = relpath
        fullpath = os.path.join(self.outdir, 'data', relpath)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        with open(fullpath, 'wb') as fp:
            fp.write(data)
        return relpath

    def extract_rev(self, n, rev):
        commit = self.read_commit(rev)

        root = etree.Element('commit')
        root.text = '\n'
        root.tail = '\n'
        e = etree.SubElement(root, 'author', author_attrib(commit.author))
        e.tail = '\n'
        e = etree.SubElement(root, 'committer', author_attrib(commit.committer))
        e.tail = '\n'
        e = etree.SubElement(root, 'message')
        e.text = '\n' + commit.message
        e.tail = '\n'

        tree = self.read_tree(commit.tree)
        if not commit.parents:
            parent_tree = {}
        elif len(commit.parents) == 1:
            parent_tree = self.read_tree(
                self.read_commit(commit.parents[0]).tree)
        else:
            raise Failure('Cannot handle merges.  History must be linear.')
        for path in sorted(set(tree.keys()).union(parent_tree.keys())):
            diff = self.diff_file(path, parent_tree.get(path), tree.get(path))
            if diff is None:
                continue
            diff.set('path', path)
            diff.tail = '\n'
            root.append(diff)

        cdir = os.path.join(self.outdir, 'commit')
        os.makedirs(cdir, exist_ok=True)
        path = os.path.join(cdir, '{}.xml'.format(n))
        tree = etree.ElementTree(root)
        with open(path, 'wb') as fp:
            tree.write(fp, encoding='UTF-8')

    @classmethod
    def main(class_):
        p = argparse.ArgumentParser(
            description='Extract patches from a Git repo.')
        p.add_argument('repo', help='path to repository')
        p.add_argument('outdir', help='output directory')
        args = p.parse_args()
        obj = class_(args)
        obj.run()

if __name__ == '__main__':
    Extract.main()
