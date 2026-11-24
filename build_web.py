'''
    build_web.py
    8 Nov 2026

    Builds docs/data.js for the database viewer (docs/index.html) from database/ and the logs it lists.
    The markdown stays the only source of truth, this just parses it:

      - database/database.md is the 2015-17 analog cluster. Every database/*_database.md is another cluster or
        firmware, one variant per file, labelled by its "**Label:**" line. database/README.md is not read.
      - In each file: the first "# Title" (its "##" sections are intro topics), then one "# 0xNNN - Name" section per
        ID, then "# Topics" with a "## Name" per topic. A topic heading can name several IDs, those ID pages link to it.
      - Tables with a Byte / Bytes / Bits column (or "Byte N" columns) tag each row with the byte(s) it describes,
        prose that says "byte 3" / "bytes 4 - 5" / "b2" gets tagged too. The viewer colors notes by those bytes.
      - The Sources table's Vehicle column labels the sample rows. Every source whose path exists on disk is read
        and the first frame of each ID from that vehicle becomes one sample row.

    Standard library only. Usage:
        python build_web.py            then open docs/index.html
        python build_web.py --check    only check the format of database/*.md, exit 1 on problems
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
DB_DIR = os.path.join(ROOT, 'database')
DB_MAIN = 'database.md'
OUT = os.path.join(ROOT, 'docs', 'data.js')

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
    '''Body lines of one section -> list of blocks.'''
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
            md = ''.join(('\n' if re.match(r'(\d+\.|[-*]) ', l) else ' ') + l for l in body).strip()
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
        if re.match(r'\*\*(Sample|Status|Rate|Label):\*\*', md):
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


def db_files():
    '''-> [(variant, file name)], the analog base file first'''
    extra = sorted(os.path.basename(p) for p in glob.glob(os.path.join(DB_DIR, '*_database.md')))
    return [('analog', DB_MAIN)] + [(f[:-len('_database.md')], f) for f in extra]


def read_sections(path):
    '''-> (lines, sections) split on # / ## headings outside code fences'''
    with open(path, encoding='utf-8') as f:
        lines = f.read().split('\n')

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
    return lines, sections


def file_label(sections):
    '''The **Label:** field of a file's first section'''
    meta = next((b for b in parse_blocks(sections[0]['body'], 0) if b['t'] == 'meta'), None) if sections else None
    return meta['fields'].get('label', '') if meta else ''


def parse_database():
    files, entries, topics, index, sources = [], [], [], {}, []
    for variant, fname in db_files():
        _, sections = read_sections(os.path.join(DB_DIR, fname))
        f = {'variant': variant, 'file': fname, 'topics': [], 'label': file_label(sections) or variant}
        files.append(f)
        parse_file(f, sections, entries, topics, index, sources)

    # Index-only IDs (no section of their own yet)
    have = {i for e in entries for i in e['ids'] if e['variant'] != 'cluster-tx'}
    for i, row in index.items():
        if i not in have:
            entries.append({'ids': [i], 'title': '%s - %s' % (i, row['name']), 'name': row['name'], 'line': 0,
                            'file': DB_MAIN, 'variant': 'analog', 'status': row['status'], 'samples': [], 'blocks': []})
    for e in entries:
        for i in e['ids']:
            if i in index:
                e['sentBy'] = index[i]['sentBy']
    return files, entries, topics, sources


def sources_from(blocks):
    '''Rows of a Sources table: the log path in backticks in the first column, Vehicle labels its samples'''
    out = []
    for b in blocks:
        if b['t'] == 'table' and 'Vehicle' in b['head']:
            vi = b['head'].index('Vehicle')
            for r in b['rows']:
                m = re.search(r'`([^`]+)`', r['cells'][0])
                out.append({'path': m.group(1).lstrip('/') if m else '', 'label': r['cells'][vi], 'md': r['cells'][0]})
    return out


def parse_file(f, sections, entries, topics, index, sources):
    variant, fname = f['variant'], f['file']
    for k, sec in enumerate(sections):
        title = sec['title']
        blocks = parse_blocks(sec['body'], sec['line'] + 1)
        head, _, name = title.partition(' - ')
        ids = find_ids(head) if name and k and sec['level'] == 1 else []
        if title == TOPICS and sec['level'] == 1 and not blocks:
            continue

        if title == 'Index':
            for b in blocks:
                if b['t'] == 'table':
                    for r in b['rows']:
                        c = r['cells']
                        for i in find_ids(c[0]):
                            index[i] = {'name': re.sub(r'\*\*', '', c[1]), 'status': c[2], 'sentBy': c[3]}
            continue

        if title == 'Sources':
            sources += sources_from(blocks)

        if ids:
            meta = next((b for b in blocks if b['t'] == 'meta'), None)
            entries.append({
                'ids': ids, 'title': title, 'name': name.strip(), 'line': sec['line'], 'file': fname,
                'variant': variant,
                'status': (meta['fields'].get('status', '') if meta else ''),
                'samples': (meta['samples'] if meta else []) + code_samples(blocks),
                'blocks': blocks,
            })
            continue

        # base file keys stay plain so old #t/ links keep working
        key = slug(title) if variant == 'analog' else variant + '/' + slug(title)
        topics.append({'key': key, 'title': title, 'line': sec['line'], 'file': fname, 'variant': variant,
                       'ids': find_ids(title), 'blocks': blocks})
        f['topics'].append(key)

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
                                'line': sec['line'], 'file': fname, 'variant': 'cluster-tx', 'status': 'Cluster sends',
                                'samples': [{'d': d, 'label': 'bench cluster'}] if HEX_FRAME.match(d) else [],
                                'blocks': [{'t': 'p', 'md': c[2], 'bytes': bytes_from_prose(c[2])}] if c[2] else [],
                                'topic': key,
                            })


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ---------------------------------------------------------------- format check

TOPICS = 'Topics'
SAMPLES_DIR = 'canbus_samples'
# keep in step with the Status values table in database/README.md (test_web.py checks)
STATUSES = ('Confirmed', 'From logs', 'From firmware', 'Cluster sends', 'APIM sends')
STATUS_RE = re.compile(r'(?:%s)(?=$|[\s,(.;:-])' % '|'.join(map(re.escape, STATUSES)))


def bad_status(status):
    return ('Status has to start with one of: %s, see "Status values" in database/README.md (got "%s")'
            % (', '.join(STATUSES), status[:40]))


def check_topic_status(sec, err):
    '''Topics don't need a Status, but one they have uses the same list'''
    meta = next((b for b in parse_blocks(sec['body'], 0) if b['t'] == 'meta'), None)
    status = meta['fields'].get('status', '') if meta else ''
    if status and not STATUS_RE.match(status):
        err(sec['line'], bad_status(status))


def check_sources(sec, err):
    '''Logs in canbus_samples/ have to exist and have frames build_web can read'''
    for src in sources_from(parse_blocks(sec['body'], sec['line'] + 1)):
        if not src['path'].startswith(SAMPLES_DIR + '/'):
            continue
        files = source_files(src['path'])
        if not files:
            err(sec['line'], 'Sources: no log at `%s`' % src['path'])
            continue
        n, why = 0, ''
        for path in files:
            try:
                n += sum(1 for _ in read_frames(path))
            except Exception as e:
                why = ' (%s: %s)' % (os.path.basename(path), e)
        if not n:
            err(sec['line'], 'Sources: no CAN frames read from `%s`%s, see database/README.md for the formats'
                % (src['path'], why))


def check():
    '''Problems the parser would silently get wrong, see database/README.md. -> exit code'''
    problems = []
    labels = {}
    for variant, fname in db_files():
        lines, sections = read_sections(os.path.join(DB_DIR, fname))
        err = lambda n, msg: problems.append('database/%s:%d: %s' % (fname, n, msg))

        fence = 0
        for n, line in enumerate(lines, 1):
            if line.strip().startswith('```'):
                fence = 0 if fence else n
            elif not fence and re.match(r'#{3,} ', line):
                err(n, 'only # and ## headings are read, this one gets merged into the section above it')
        if fence:
            err(fence, 'code block (```) is never closed, everything after it is skipped')

        first = next((l for l in lines if l.strip()), '')
        if not sections or not first.startswith('# ') or sections[0]['title'].startswith('0x'):
            err(1, 'must start with a "# Title" heading for the file, before any ID')
            continue
        intro = sections[0]['title']
        check_topic_status(sections[0], err)
        label = file_label(sections)
        if not label:
            err(sections[0]['line'], 'the title section needs a "**Label:** short name" line (shown on the site)')
        elif label.lower() in labels:
            err(sections[0]['line'], 'label "%s" is already used by %s' % (label, labels[label.lower()]))
        labels[label.lower()] = fname

        seen, topics_at = {}, 0
        for sec in sections[1:]:
            title = sec['title']
            head, _, name = title.partition(' - ')
            if title == 'Sources':
                check_sources(sec, err)
            if sec['level'] == 2 or title == TOPICS:
                check_topic_status(sec, err)
            if sec['level'] == 2:
                if sec['h1'] not in (intro, TOPICS):
                    err(sec['line'], '## inside an ID section is not part of it. Use **bold** text, or make it a '
                                     'topic: "## %s" under "# %s"' % (title, TOPICS))
                continue
            if title == TOPICS:
                if topics_at:
                    err(sec['line'], 'second "# %s", the first is at line %d' % (TOPICS, topics_at))
                topics_at = sec['line']
                continue
            if re.match(r'0x', title) and not name:
                err(sec['line'], 'ID heading needs " - Name" after the ID, e.g. "# 0x3B3 - Cluster On"')
                continue
            ids = find_ids(head) if name else []
            if not ids:
                err(sec['line'], '"# %s" is not an ID. Topics go under "# %s" as "## %s"' % (title, TOPICS, title))
                continue
            if len(ids) > 1:
                err(sec['line'], 'one ID per section (%s). Give each its own "# 0xNNN - Name" section, notes about '
                                 'them together go in a topic under "# %s"' % (' '.join(ids), TOPICS))
                continue
            for i in ids:
                if i in seen:
                    err(sec['line'], '%s already has a section at line %d, keep one section per ID per file' % (i, seen[i]))
                seen[i] = sec['line']

            blocks = parse_blocks(sec['body'], sec['line'] + 1)
            meta = next((b for b in blocks if b['t'] == 'meta'), None)
            status = meta['fields'].get('status', '') if meta else ''
            if not status:
                err(sec['line'], 'needs a "**Sample:** .. · **Rate:** .. · **Status:** .." line (Status at least)')
            elif not STATUS_RE.match(status):
                err(sec['line'], bad_status(status))
            if meta:
                for d in re.findall(r'`([^`]*)`', meta['fields'].get('sample', '')):
                    if not HEX_FRAME.match(d.strip()):
                        err(sec['line'], 'sample `%s` is not 1 - 8 hex bytes like `40 48 02 0A`, it is dropped' % d)
            for b in blocks:
                if b['t'] == 'table' and b['byteCol'] >= 0:
                    for r in b['rows']:
                        if not r['bytes']:
                            err(sec['line'], 'byte table row "%s": no byte number in the %s column'
                                % (' | '.join(r['cells'])[:50], b['head'][b['byteCol']]))
    for p in problems:
        print(p)
    print('%d problem%s in database/' % (len(problems), '' if len(problems) == 1 else 's'))
    return 1 if problems else 0


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
        elif first.startswith('('):                                # candump: "(6.530000) can0 078#00E2000000000000"
            for line in f:
                m = re.match(r'\([\d.]+\)\s+\S+\s+([0-9A-Fa-f]+)#((?:[0-9A-Fa-f]{2})+)\s*$', line)
                if m:
                    yield int(m.group(1), 16), ' '.join(re.findall('..', m.group(2)))
        else:                                                     # "820298   0x085: 7C 33 80 .."
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
    return 'https://github.com/%s/blob/HEAD/database/' % repo if repo else ''


def main():
    if '--check' in sys.argv:
        sys.exit(check())
    print('parsing database/')
    files, entries, topics, sources = parse_database()
    print('  %d ID entries, %d topics, %d sources' % (len(entries), len(topics), len(sources)))
    print('reading logs')
    vehicles, samples = collect_samples(sources)

    data = {
        'generated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'source': repo_url(),
        'files': files,
        'vehicles': vehicles,
        'entries': entries,
        'topics': topics,
        'samples': samples,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('// generated by build_web.py from database/ - do not edit\n')
        f.write('window.S550 = ')
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')
    print('wrote %s (%d KB)' % (os.path.relpath(OUT, ROOT), os.path.getsize(OUT) // 1024))


if __name__ == '__main__':
    main()
