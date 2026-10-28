# screenshot-claim-audit

An offline static auditor for documented still-image capture claims and Python source evidence. Version 0.1.0 requires Python 3.9 or newer and has no runtime dependencies. Audited source is parsed, never executed.

Install and run:

```sh
python3 -m pip install .
screenshot-claim-audit /path/to/project --json
python3 -m screenshot_claim_audit /path/to/project --verbose
python3 -m unittest discover
```

The positional argument is a directory. Options include `--json`, `--verbose`, repeatable `--ignore GLOB` for root-relative paths, `--fail-on HIGH` (default), `--fail-on MEDIUM`, and `--version`. Output contains a verdict and findings, each identifying a rule, severity, and message. Verbose text lists evidence locations; JSON also includes production evidence, test evidence, and parsing warnings.

Exit status 0 means the configured threshold was met; 2 means a finding reached that threshold; 1 means invalid arguments or an inaccessible root. A positive assertion lacking production evidence yields HIGH, or MEDIUM when evidence exists only in test modules. An assertion of absence contradicted by production evidence yields HIGH. Each family yields at most one finding. Without a matching assertion the result is PASS. Without source, positive assertions yield HIGH and assertions of absence pass.

## Limitations

Only the fixed phrase vocabulary implemented in the two phrase constants is recognized; arbitrary paraphrases are outside scope. A lone noun such as `screenshot`, chapter titles, and dependency names do not imply capability. Video recording, clipboard operations, speech, notifications, and ordinary image file operations belong outside this audit.

Documentation scope is root README.md and Markdown files beneath any directory component named docs. Fenced blocks are excluded; inline code counts. Matching lowercases text, expands contracted negation, replaces hyphens by spaces, and joins wrapped lines within each paragraph. Word boundaries and longest-first matching apply; negative spans are removed before positive matching.

Evidence requires alias-resolved calls from pyautogui, PIL.ImageGrab, or pyscreenshot, or a shot/grab method in a module importing mss. The mss rule approximates receiver identity: it does not prove the receiver came from that provider. Imports alone, comments, strings, ordinary image I/O, and video APIs provide no evidence. Shell capture helpers are outside the supported evidence routes. Import shadowing, runtime reachability, successful execution, and image quality are not proven.

Production source excludes tests directories, test-named modules, fixtures, docs, examples, and symlinked files or directories. Test modules are examined separately for the MEDIUM classification; excluded fixture, example, and documentation source remains excluded. Environment files are never opened. Syntax-invalid modules generate warnings and supply no evidence. Ignore globs apply to files relative to the root.

The MIT license applies. Tests and fixtures are included in the source distribution.
