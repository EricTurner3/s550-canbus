# Contributing

Thanks for helping map the S550 Ford Mustang CAN bus. The goal of this project is to document our research and
findings on the network messages: what each message means, how it was found, and the status (confirmed, from logs, from firmware.etc).

**The minimum is one markdown file.** Add your findings to your cluster's file in `database/` and open a pull
request. Logs are optional, and the pull request runs the checks for you.

## Adding new message data

You only need Git and Python 3.

1. **Fork** [EricTurner3/s550-canbus](https://github.com/EricTurner3/s550-canbus), clone your fork and make a branch:

   ```
   git clone https://github.com/<you>/s550-canbus.git
   cd s550-canbus
   git checkout -b lr3t-notes
   ```

2. **Edit your cluster's file** in `database/`, or start one from the template. Template and rules:
   [database/README.md](database/README.md).
3. **Optional: add a log** in `canbus_samples/<you>/<car or bench>/`, see
   [Log samples](database/README.md#log-samples-sources).
4. **Check it:**

   ```
   python build_web.py --check     # has to say 0 problems
   python build_web.py             # optional: open docs/index.html to see your IDs
   ```

5. **Open a pull request** against `master`. Say which module (part number), where the data came from and what you
   tested.

## Changes to the scripts

Welcome. In the pull request, say **why** (the problem you ran into) and **what it solves** (what works now, how you
tested it). One change per pull request, separate from data changes.

## Using AI tools

Welcome, with a person in charge:

- Check everything it wrote. Only your own bench or car test makes something `Confirmed`.
- Same format and checks as everything else.
- Say in the pull request what the AI helped with.

[CLAUDE.md](CLAUDE.md) gives AI assistants these rules.

## What not to upload

This repo documents findings, not the source proprietary data they came from. No:

- **Firmware**: `.vbf` files, flash or memory dumps, `.bin` read-outs.
- **Security keys**: seed / key secrets or anything that unlocks a module.
- **Proprietary data**: manuals, datasheets, software or databases you don't have the rights to share.

Write down what you learned instead. If you see one of these already committed, open a pull request that removes it
and say what it is (it stays in the history, so the maintainer may need to clean that up too).
