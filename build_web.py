'''
    build_web.py
    8 Nov 2026

    Builds web/data.js for the database viewer (web/index.html) from database.md and the logs it lists.
    database.md stays the only source of truth, this just parses it:

      - Each "# 0xNNN - Name" heading (and "## 0xNNN - Name" under the 2018+ digital heading) is an ID entry.
      - Tables with a Byte / Bytes / Bits column (or "Byte N" columns) tag each row with the byte(s) it describes,
        prose that says "byte 3" / "bytes 4 - 5" / "b2" gets tagged too. The viewer colors notes by those bytes.
      - The Sources table's Vehicle column labels the sample rows. Every source whose path exists on disk is read
        and the first frame of each ID from that vehicle becomes one sample row.

    Standard library only. Usage:
        python build_web.py            then open web/index.html
'''

import base64
import csv
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_MD = os.path.join(ROOT, 'database.md')
OUT = os.path.join(ROOT, 'web', 'data.js')

SAMPLES_PER_VEHICLE = 1     # distinct payloads kept per ID per vehicle, first ones seen

HEX_ID = re.compile(r'0x(?:[0-9A-Fa-f]{1,3}|5xx)\b')
HEX_FRAME = re.compile(r'^(?:[0-9A-Fa-f]{2} ){0,7}[0-9A-Fa-f]{2}$')
TABLE_SEP = re.compile(r'^\|[\s:|-]+\|$')


def norm_id(s):
    s = s.strip().strip('`')
    if s.lower() == '0x5xx':
        return '0x5xx'
    return '0x%X' % int(s, 16)


def find_ids(text):
    out = []
    for m in HEX_ID.finditer(text):
        i = norm_id(m.group(0))
        if i not in out:
            out.append(i)
    return out


# ---------------------------------------------------------------- byte tagging

def bytes_from_cell(cell):
    '''"0", "0 - 1", "0, 4, 5", "0, bits 7 - 4", "byte 0 bit 7", "1 / `0x02`", "b0[7:4]" -> list of byte numbers'''
    s = cell.replace('`', '').strip().lower()
    m = re.match(r'b(\d)\b', s)
    if m:
        return [int(m.group(1))]
    s = re.sub(r'^bytes?\s*', '', s)
    s = re.split(r'bit|\(|/', s)[0]
    out = []
    for a, b in re.findall(r'(\d)(?:\s*-\s*(\d))?', s):
        rng = range(int(a), int(b) + 1) if b else [int(a)]
        out += [n for n in rng if n <= 7 and n not in out]
    return out


MENTION = re.compile(r'\b[Bb]ytes?\s+(\d(?:\s*(?:-|&|,|and|to)\s*\d)*)|(?<![\w.])b(\d)(?=[\s\[.,)]|$)')


def bytes_from_prose(text):
    text = re.sub(r'`0x[0-9A-Fa-f]+`|0x[0-9A-Fa-f]+', '', text)
    out = []
    for group, short in MENTION.findall(text):
        if short:
            nums = [int(short)]
        else:
            nums = []
            for a, b in re.findall(r'(\d)(?:\s*(?:-|to)\s*(\d))?', group):
                nums += range(int(a), int(b) + 1) if b else [int(a)]
        out += [n for n in nums if n <= 7 and n not in out]
    return out


def split_row(line):
    cells = line.strip().strip('|').split('|')
    return [c.strip() for c in cells]


def byte_columns(head):
    '''-> ('col', index) for a Byte / Bytes / Bits column, ('fixed', [n, ...]) for "Byte N" columns, or None'''
    for i, h in enumerate(head):
        if re.fullmatch(r'(?i)bytes?|bits|byte\s*/\s*bit', h.strip()):
            return ('col', i)
    fixed = [int(m.group(1)) for h in head for m in [re.fullmatch(r'(?i)byte (\d)', h.strip())] if m]
    return ('fixed', fixed) if fixed else None


# ---------------------------------------------------------------- markdown parsing

def parse_blocks(lines, start_line):
    '''Body lines of one section -> list of blocks. Line numbers are 1-based for links back to database.md.'''
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s or s == '---':
            i += 1
            continue

        if s.startswith('```'):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith('```'):
                j += 1
            blocks.append({'t': 'code', 'text': '\n'.join(lines[i + 1:j])})
            i = j + 1
            continue

        if s.startswith('>'):
            body = []
            while i < len(lines) and lines[i].strip().startswith('>'):
                body.append(lines[i].strip()[1:].strip())
                i += 1
            kind = 'note'
            m = re.match(r'\[!?(\w+)\]$', body[0]) if body else None
            if m:
                kind = m.group(1).lower()
                body = body[1:]
            md = ' '.join(body)
            blocks.append({'t': 'callout', 'kind': kind, 'md': md, 'bytes': bytes_from_prose(md)})
            continue

        if s.startswith('|') and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1].strip()):
            head = split_row(s)
            cols = byte_columns(head)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = split_row(lines[i])
                if cols and cols[0] == 'col':
                    b, explicit = bytes_from_cell(cells[cols[1]]) if cols[1] < len(cells) else [], True
                elif cols:
                    b, explicit = list(cols[1]), True
                else:
                    b, explicit = bytes_from_prose(' '.join(cells)), False
                rows.append({'cells': cells, 'bytes': b, 'explicit': explicit})
                i += 1
            blocks.append({'t': 'table', 'head': head,
                           'byteCol': cols[1] if cols and cols[0] == 'col' else -1, 'rows': rows})
            continue

        if re.match(r'[-*] ', s):
            items = []
            while i < len(lines) and lines[i].strip():
                l = lines[i]
                if re.match(r'\s*[-*] ', l):
                    items.append({'md': re.sub(r'^\s*[-*] ', '', l).strip(),
                                  'depth': (len(l) - len(l.lstrip())) // 2})
                elif items:
                    items[-1]['md'] += ' ' + l.strip()
                i += 1
            for it in items:
                it['bytes'] = bytes_from_prose(it['md'])
            blocks.append({'t': 'ul', 'items': items})
            continue

        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r'\s*(\||>|```|[-*] )', lines[i]):
            para.append(lines[i].strip())
            i += 1
        md = ' '.join(para)
        if re.match(r'\*\*(Sample|Status|Rate):\*\*', md):
            blocks.append(parse_meta(md))
        else:
            blocks.append({'t': 'p', 'md': md, 'bytes': bytes_from_prose(md)})
    return blocks


def parse_meta(md):
    '''**Sample:** `..` (label) · **Rate:** .. · **Status:** .. · extra'''
    meta = {'t': 'meta', 'fields': {}, 'extra': [], 'samples': []}
    for part in re.split(r' · | - (?=\*\*\w+:\*\*)', md):
        m = re.match(r'\*\*(\w+):\*\*\s*(.*)', part.strip())
        if m:
            meta['fields'][m.group(1).lower()] = m.group(2).strip()
        else:
            meta['extra'].append(part.strip())
    for d, label in re.findall(r'`([0-9A-Fa-f ]+)`(?:\s*\(([^)]*)\))?', meta['fields'].get('sample', '')):
        if HEX_FRAME.match(d.strip()):
            meta['samples'].append({'d': d.strip().upper(), 'label': label})
    return meta


def code_samples(blocks):
    '''Labeled frames in code blocks ("Hazards on   44 8A C6 0C 18 00 C0 82") become extra sample rows.'''
    out = []
    for b in blocks:
        if b['t'] != 'code':
            continue
        for line in b['text'].split('\n'):
            m = re.match(r'(.*?\S)\s{2,}((?:[0-9A-Fa-f]{2} ){7}[0-9A-Fa-f]{2})\s*$', line)
            if m:
                out.append({'d': m.group(2).upper(), 'label': m.group(1)})
    return out


def parse_database(path):
    lines = open(path, encoding='utf-8').read().split('\n')

    # split into sections on # / ## headings, outside code fences
    sections = []
    cur = None
    h1 = ''
    fence = False
    for n, line in enumerate(lines, 1):
        if line.strip().startswith('```'):
            fence = not fence
        m = None if fence else re.match(r'(#{1,2}) (.+)', line)
        if m:
            if len(m.group(1)) == 1:
                h1 = m.group(2).strip()
            cur = {'level': len(m.group(1)), 'title': m.group(2).strip(), 'h1': h1, 'line': n, 'body': []}
            sections.append(cur)
        elif cur:
            cur['body'].append(line)

    entries, topics, index, sources = [], [], {}, []
    for sec in sections:
        title = sec['title']
        blocks = parse_blocks(sec['body'], sec['line'] + 1)
        digital = sec['h1'].startswith('2018+')
        head, _, name = title.partition(' - ')
        ids = find_ids(head) if name else []

        if title == 'Index':
            for b in blocks:
                if b['t'] == 'table':
                    for r in b['rows']:
                        c = r['cells']
                        for i in find_ids(c[0]):
                            index[i] = {'name': re.sub(r'\*\*', '', c[1]), 'status': c[2], 'sentBy': c[3]}
            continue

        if title == 'Sources':
            for b in blocks:
                if b['t'] == 'table' and 'Vehicle' in b['head']:
                    vi = b['head'].index('Vehicle')
                    for r in b['rows']:
                        m = re.search(r'`([^`]+)`', r['cells'][0])
                        sources.append({'path': m.group(1).lstrip('/') if m else '', 'label': r['cells'][vi],
                                        'md': r['cells'][0]})

        if ids and (sec['level'] == 1 or digital):
            meta = next((b for b in blocks if b['t'] == 'meta'), None)
            entries.append({
                'ids': ids, 'title': title, 'name': name.strip(), 'line': sec['line'],
                'variant': 'digital' if digital else 'analog',
                'status': (meta['fields'].get('status', '') if meta else ''),
                'samples': (meta['samples'] if meta else []) + code_samples(blocks),
                'blocks': blocks,
            })
            continue

        topics.append({'key': slug(title), 'title': title, 'line': sec['line'], 'blocks': blocks})

        # Cluster TX tables list one ID per row, give each one an entry so it shows up on that ID's page
        if title.startswith('Cluster (IPC) Transmits'):
            for b in blocks:
                if b['t'] == 'table' and b['head'][0] == 'ID':
                    for r in b['rows']:
                        c = r['cells']
                        for i in find_ids(c[0]):
                            d = c[1].strip('`').upper()
                            entries.append({
                                'ids': [i], 'title': '%s - Cluster transmit' % i, 'name': 'Cluster transmit',
                                'line': sec['line'], 'variant': 'cluster-tx', 'status': 'Cluster sends',
                                'samples': [{'d': d, 'label': 'bench cluster'}] if HEX_FRAME.match(d) else [],
                                'blocks': [{'t': 'p', 'md': c[2], 'bytes': bytes_from_prose(c[2])}] if c[2] else [],
                                'topic': slug(title),
                            })

    # Index-only IDs (no section of their own yet)
    have = {i for e in entries for i in e['ids'] if e['variant'] != 'cluster-tx'}
    for i, row in index.items():
        if i not in have:
            entries.append({'ids': [i], 'title': '%s - %s' % (i, row['name']), 'name': row['name'], 'line': 0,
                            'variant': 'analog', 'status': row['status'], 'samples': [], 'blocks': []})
    for e in entries:
        for i in e['ids']:
            if i in index:
                e['sentBy'] = index[i]['sentBy']
    return entries, topics, sources


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ---------------------------------------------------------------- logs

def read_frames(path):
    '''yield (id, 'AA BB ..') from any of the log formats in this repo'''
    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        first = f.readline()
        f.seek(0)
        if first.startswith('timestamp,arbitration_id'):          # python-can CSV, base64 payload
            r = csv.reader(f)
            next(r)
            for row in r:
                if len(row) >= 7:
                    yield int(row[1], 16), row[6]
        elif 'ID (HEX)' in first:                                  # freeze frame export
            r = csv.DictReader(f)
            for row in r:
                if row.get('ID (HEX)') and row.get('Sample Data'):
                    yield int(row['ID (HEX)'], 16), row['Sample Data']
        elif first.startswith('id,count,data'):                    # cluster_tx.csv
            for row in csv.DictReader(f):
                yield int(row['id'], 16), row['data']
        else:                                                      # "820298   0x085: 7C 33 80 .."
            for line in f:
                m = re.search(r'0x([0-9A-Fa-f]+):\s*((?:[0-9A-Fa-f]{2}\s*)+)$', line)
                if m:
                    yield int(m.group(1), 16), m.group(2)


def to_hex(payload):
    p = payload.strip()
    if not re.fullmatch(r'(?:[0-9A-Fa-f]{2}\s*)+', p):
        p = base64.b64decode(p).hex(' ')
    return ' '.join(p.split()).upper()


def source_files(path):
    full = os.path.join(ROOT, path)
    if os.path.isdir(full):
        return sorted(f for ext in ('*.csv', '*.txt', '*.log') for f in glob.glob(os.path.join(full, ext)))
    return sorted(glob.glob(full))


def collect_samples(sources):
    samples = {}        # id -> [ {v, d, f} ]
    vehicles = []
    for src in sources:
        files = source_files(src['path']) if src['path'] else []
        vehicles.append({'label': src['label'], 'source': src['md'], 'files': len(files)})
        if not files:
            if src['path'].endswith(('.csv', '.txt')) or '*' in src['path'] or os.path.isdir(os.path.join(ROOT, src['path'])):
                print('  no log found for %s (%s)' % (src['label'], src['path']), file=sys.stderr)
            continue
        v = len(vehicles) - 1
        seen = {}
        for path in files:
            rel = os.path.relpath(path, ROOT).replace('\\', '/')
            for cid, payload in read_frames(path):
                got = seen.setdefault(cid, [])
                if len(got) >= SAMPLES_PER_VEHICLE:
                    continue
                d = to_hex(payload)
                if d not in got:
                    got.append(d)
                    samples.setdefault('0x%X' % cid, []).append({'v': v, 'd': d, 'f': rel})
        print('  %-40s %d files, %d IDs' % (src['label'], len(files), len(seen)))
    return vehicles, samples


def repo_url():
    repo = os.environ.get('GITHUB_REPOSITORY')
    if not repo:
        try:
            url = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=ROOT, capture_output=True,
                                 text=True).stdout.strip()
            m = re.search(r'github\.com[:/](.+?)(?:\.git)?$', url)
            repo = m.group(1) if m else ''
        except OSError:
            repo = ''
    return 'https://github.com/%s/blob/HEAD/database.md' % repo if repo else ''


def main():
    print('parsing database.md')
    entries, topics, sources = parse_database(DB_MD)
    print('  %d ID entries, %d topics, %d sources' % (len(entries), len(topics), len(sources)))
    print('reading logs')
    vehicles, samples = collect_samples(sources)

    data = {
        'generated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'source': repo_url(),
        'vehicles': vehicles,
        'entries': entries,
        'topics': topics,
        'samples': samples,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('// generated by build_web.py from database.md - do not edit\n')
        f.write('window.S550 = ')
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')
    print('wrote %s (%d KB)' % (os.path.relpath(OUT, ROOT), os.path.getsize(OUT) // 1024))


if __name__ == '__main__':
    main()
