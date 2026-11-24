'''
    test_web.py
    23 Nov 2026

    Tests for build_web.py and the database viewer. Standard library only:

      - Parser / --check tests run on small database folders written to a temp dir.
      - The real database/ has to pass --check.
      - The page test builds docs/data.js from the real database/, opens docs/index.html#selftest in headless
        Edge / Chrome / Chromium (or $BROWSER), which renders every ID and topic page, and fails on anything
        the self test reports. Skipped if no browser is found, unless $REQUIRE_BROWSER is set (CI).

    Usage:
        python test_web.py
'''

import glob
import html
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import build_web

ROOT = os.path.dirname(os.path.abspath(__file__))

BASE = '''# Test Database

**Label:** test analog

## Conventions

Nothing here.

# 0x3B3 - Cluster On

**Sample:** `40 48 02 0A 10 05 00 02` · **Rate:** 10 Hz · **Status:** Confirmed

| Byte | Signal |
|---|---|
| 0 bits 7 - 4 | Ignition |
'''

GOOD = '''# 2020+ Digital Cluster (LR3T-14C026-JE)

**Label:** 2020+ digital (LR3T) · **Status:** From firmware

Intro for the file.

# 0x3B3 - Cluster On (2020 firmware)

**Sample:** `40 48 02 0A 10 05 00 02` (key on) · **Rate:** 100 ms · **Status:** From firmware, not tested

| Byte | Signal | Values |
|---|---|---|
| 0 bits 7 - 4 | Power mode | `4` run |
| 4 | Outside temp | `raw * 0.5 - 40` |

Byte 4 is the same as the 2015.

# 0x3B4 - TPMS Lamp

**Status:** Confirmed

# Topics

## Timeouts

A topic of its own.

## 0x3B3 / 0x3B4 - Boot Order

Topics can name several IDs.
'''


SOURCES = '''
## Sources

| Source | Vehicle | Bus | Notes |
|---|---|---|---|
| `canbus_samples/someone/bench_cluster/keyon.txt` | 2020 GT, LR3T bench | HS3 | |
'''

# GOOD with a Sources table, for a log in canbus_samples/someone/bench_cluster/
WITH_SOURCES = GOOD.replace('Intro for the file.\n', 'Intro for the file.\n' + SOURCES)


def write_db(files):
    '''database files in the folder's root, logs under their canbus_samples/ path'''
    d = tempfile.mkdtemp(prefix='s550db_')
    for name, text in files.items():
        Path(d, name).parent.mkdir(parents=True, exist_ok=True)
        Path(d, name).write_text(text, encoding='utf-8')
    return d


class DbTest(unittest.TestCase):
    '''Points build_web at a temp database folder'''

    def use(self, files):
        d = write_db(files)
        self.addCleanup(shutil.rmtree, d)
        for var in ('DB_DIR', 'ROOT'):
            self.addCleanup(setattr, build_web, var, getattr(build_web, var))
            setattr(build_web, var, d)

    def check(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = build_web.check()
        return code, [l for l in out.getvalue().splitlines() if l.startswith('database/')]

    def assertProblem(self, files, pattern):
        self.use(files)
        code, problems = self.check()
        self.assertEqual(code, 1, 'expected a problem matching %r' % pattern)
        self.assertTrue(any(re.search(pattern, p) for p in problems), problems)


class TestParse(DbTest):

    def test_files_and_variants(self):
        self.use({'database.md': BASE, '2020_lr3t_database.md': GOOD, 'README.md': '# 0x999 - not read\n'})
        files, entries, topics, _ = build_web.parse_database()
        self.assertEqual([(f['variant'], f['file'], f['label']) for f in files],
                         [('analog', 'database.md', 'test analog'),
                          ('2020_lr3t', '2020_lr3t_database.md', '2020+ digital (LR3T)')])
        e = [x for x in entries if x['variant'] == '2020_lr3t']
        self.assertEqual([x['ids'] for x in e], [['0x3B3'], ['0x3B4']])
        self.assertEqual((e[0]['ids'], e[0]['file'], e[0]['line']), (['0x3B3'], '2020_lr3t_database.md', 7))
        self.assertEqual(e[0]['samples'], [{'d': '40 48 02 0A 10 05 00 02', 'label': 'key on'}])
        self.assertTrue(e[0]['status'].startswith('From firmware'))
        table = next(b for b in e[0]['blocks'] if b['t'] == 'table')
        self.assertEqual([r['bytes'] for r in table['rows']], [[0], [4]])
        self.assertNotIn('0x999', {i for x in entries for i in x['ids']})
        # base file topic keys are unchanged, the others are under their variant
        self.assertIn('conventions', [t['key'] for t in topics])
        self.assertEqual(files[1]['topics'], ['2020_lr3t/2020-digital-cluster-lr3t-14c026-je', '2020_lr3t/timeouts',
                                              '2020_lr3t/0x3b3-0x3b4-boot-order'])
        # a topic heading can name several IDs: it stays a topic and those ID pages link to it
        t = next(x for x in topics if x['title'].endswith('Boot Order'))
        self.assertEqual(t['ids'], ['0x3B3', '0x3B4'])
        self.assertNotIn('Topics', [x['title'] for x in topics])

    def test_good_file_passes(self):
        self.use({'database.md': BASE, '2020_lr3t_database.md': GOOD})
        self.assertEqual(self.check(), (0, []))

    def test_sources_log(self):
        # a small text log, one frame per ID is all the site uses
        self.use({'database.md': BASE, '2020_lr3t_database.md': WITH_SOURCES,
                  'canbus_samples/someone/bench_cluster/keyon.txt': '0x3B3: 40 48 02 0A 10 05 00 02\n0x3B3: 44 48 02 0A 10 05 00 02\n'
                                                    '0x42F: C0 00 7D 00 00 00 1F 40\n'})
        self.assertEqual(self.check(), (0, []))
        _, _, _, sources = build_web.parse_database()
        with redirect_stdout(io.StringIO()):
            vehicles, samples = build_web.collect_samples(sources)
        self.assertEqual(vehicles, [{'label': '2020 GT, LR3T bench', 'source': '`canbus_samples/someone/bench_cluster/keyon.txt`', 'files': 1}])
        self.assertEqual(samples['0x3B3'], [{'v': 0, 'd': '40 48 02 0A 10 05 00 02', 'f': 'canbus_samples/someone/bench_cluster/keyon.txt'}])
        self.assertEqual([s['d'] for s in samples['0x42F']], ['C0 00 7D 00 00 00 1F 40'])


class TestCheck(DbTest):
    '''Each mistake --check has to catch'''

    def bad(self, text, pattern):
        self.assertProblem({'database.md': BASE, '2020_lr3t_database.md': text}, pattern)

    def test_no_title(self):
        self.bad(GOOD.split('\n', 4)[4], 'must start with a "# Title"')

    def test_no_label(self):
        self.bad(GOOD.replace('**Label:** 2020+ digital (LR3T) · ', ''), 'needs a "\\*\\*Label:\\*\\*')

    def test_duplicate_label(self):
        self.assertProblem({'database.md': BASE, 'a_database.md': GOOD, 'b_database.md': GOOD}, 'already used by a_database.md')

    def test_no_meta(self):
        self.bad(GOOD.replace('**Sample:** `40 48 02 0A 10 05 00 02` (key on) · **Rate:** 100 ms · **Status:** From firmware, not tested', ''),
                 ':7: needs a "\\*\\*Sample')

    def test_meta_not_bold(self):
        # how PR #17 wrote it: "**From the 2020 firmware** · Status: ..." is just a paragraph
        self.bad(GOOD.replace('**Sample:** `40 48 02 0A 10 05 00 02` (key on) · **Rate:** 100 ms · **Status:** From firmware, not tested',
                              '**From the 2020+ firmware** · Status: From firmware'), ':7: needs a "\\*\\*Sample')

    def test_unknown_status(self):
        self.bad(GOOD.replace('**Status:** From firmware, not tested', '**Status:** maybe'), 'Status has to start with')

    def test_status_lookalike(self):
        self.bad(GOOD.replace('**Status:** From firmware, not tested', '**Status:** Confirmedish'), 'Status has to start with')

    def test_status_with_detail(self):
        for status in ('Confirmed', 'Confirmed (byte 4)', 'Confirmed, solved 14 Nov', 'From logs - DBC layout'):
            self.use({'database.md': BASE, '2020_lr3t_database.md':
                      GOOD.replace('**Status:** From firmware, not tested', '**Status:** ' + status)})
            self.assertEqual(self.check(), (0, []), status)

    def test_topic_status(self):
        # topics don't need a Status, one they have uses the same list
        self.bad(GOOD.replace('A topic of its own.', '**Status:** Solved\n\nA topic of its own.'), ':\\d+: Status has to start with')

    def test_bad_sample(self):
        self.bad(GOOD.replace('`40 48 02 0A 10 05 00 02`', '`40 48 02 0A 10 05 00 02 FF`'), 'not 1 - 8 hex bytes')

    def test_h3(self):
        self.bad(GOOD + '\n### 0x3B3 extra\n', 'only # and ## headings')

    def test_h2_under_id(self):
        self.bad(GOOD.replace('Byte 4 is the same', '## Details\n\nByte 4 is the same'), '## inside an ID section')

    def test_h2_id_under_id(self):
        self.bad(GOOD.replace('# 0x3B4 - TPMS Lamp', '## 0x3B4 - TPMS Lamp'), '## inside an ID section')

    def test_several_ids(self):
        self.bad(GOOD.replace('# 0x3B4 - TPMS Lamp', '# 0x3B4 / 0x3B5 - TPMS'), r'one ID per section \(0x3B4 0x3B5\)')

    def test_topic_outside_topics(self):
        self.bad(GOOD.replace('# Topics\n', '# Timeouts first\n\nText.\n\n# Topics\n'), 'is not an ID. Topics go under')

    def test_second_topics(self):
        self.bad(GOOD + '\n# Topics\n\n## More\n', 'second "# Topics"')

    def test_base_file_follows_the_rules_too(self):
        self.assertProblem({'database.md': BASE + '\n# 0x3E0 / 0x3E3 - Startup\n\n**Status:** Confirmed\n'},
                           r'database\.md:.*one ID per section')

    def test_id_without_name(self):
        self.bad(GOOD.replace('# Topics', '# 0x42C Cruise\n\n**Status:** Confirmed\n\n# Topics'), 'needs " - Name"')

    def test_duplicate_id(self):
        self.bad(GOOD.replace('# Topics', '# 0x3B3 - Again\n\n**Status:** Confirmed\n\n# Topics'),
                 '0x3B3 already has a section at line 7')

    def test_byte_row_without_byte(self):
        self.bad(GOOD.replace('| 4 | Outside temp', '| ? | Outside temp'), 'no byte number')

    def test_open_fence(self):
        self.bad(GOOD + '\n```\nnever closed\n', 'never closed')

    def test_sources_missing_log(self):
        self.bad(WITH_SOURCES, r'Sources: no log at `canbus_samples/someone/bench_cluster/keyon.txt`')

    def test_sources_unreadable_log(self):
        self.assertProblem({'database.md': BASE, '2020_lr3t_database.md': WITH_SOURCES,
                            'canbus_samples/someone/bench_cluster/keyon.txt': 'ID 3B3 = 40 48 02\n'}, 'Sources: no CAN frames read')


class TestDocs(unittest.TestCase):
    '''The status list is written down in three places, they have to agree'''

    def test_readme_status_table(self):
        text = Path(ROOT, 'database', 'README.md').read_text(encoding='utf-8')
        table = text.split('## Status values', 1)[1].split('\n## ', 1)[0]
        self.assertEqual(tuple(re.findall(r'^\| \*\*(.+?)\*\* \|', table, re.M)), build_web.STATUSES)

    def test_database_md_conventions(self):
        text = Path(ROOT, 'database', 'database.md').read_text(encoding='utf-8')
        conv = text.split('## Conventions', 1)[1].split('\n## ', 1)[0]
        self.assertEqual(tuple(re.findall(r'^  - \*\*(.+?)\*\*:', conv, re.M)), build_web.STATUSES)


class TestRealDatabase(unittest.TestCase):

    def test_check_passes(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = build_web.check()
        self.assertEqual(code, 0, out.getvalue())


def find_browser():
    if os.environ.get('BROWSER'):
        return os.environ['BROWSER']
    for name in ('msedge', 'chrome', 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        if shutil.which(name):
            return shutil.which(name)
    for pf in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LocalAppData')):
        for rel in (r'Microsoft\Edge\Application\msedge.exe', r'Google\Chrome\Application\chrome.exe'):
            if pf and os.path.exists(os.path.join(pf, rel)):
                return os.path.join(pf, rel)
    return None


class TestPage(unittest.TestCase):

    def test_selftest(self):
        browser = find_browser()
        if not browser:
            if os.environ.get('REQUIRE_BROWSER'):
                self.fail('no browser found for the page test')
            self.skipTest('no Edge / Chrome / Chromium found, set BROWSER=path')
        with redirect_stdout(io.StringIO()):
            build_web.main()
        url = Path(ROOT, 'docs', 'index.html').as_uri() + '#selftest'
        profile = tempfile.mkdtemp(prefix='s550browser_')
        try:
            r = subprocess.run([browser, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
                                '--user-data-dir=' + profile, '--dump-dom', url],
                               capture_output=True, text=True, encoding='utf-8', timeout=120)
        finally:
            shutil.rmtree(profile, ignore_errors=True)
        m = re.search(r'<pre id="selftest">(.*?)</pre>', r.stdout, re.S)
        self.assertTrue(m, 'self test did not run (script error?)\n' + r.stdout[-2000:] + r.stderr[-2000:])
        res = json.loads(html.unescape(m.group(1)))
        self.assertEqual(res['files'], [f for _, f in build_web.db_files()])
        self.assertGreater(res['pages'], 50)
        self.assertEqual(res['fail'], [], '\n'.join(res['fail']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
