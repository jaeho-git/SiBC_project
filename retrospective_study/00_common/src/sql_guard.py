# -*- coding: utf-8 -*-
"""Statement check used by db_query.sh before it connects. Exit 0 = allowed, exit 2 = refused (reason on stderr).

Deliberately strict: only the SQL syntax the extracts need is accepted, so the scanner never has to guess where a
literal ends. A false refusal is harmless; a false acceptance is not.
- Accepted literals: standard '...' strings with '' for a quote (db_query.sh forces standard_conforming_strings=on,
  so a backslash is an ordinary character). Accepted comments: -- to end of line.
- Refused outright: block comments (/* */), escape strings (E'...'), Unicode strings (U&'...'), dollar quoting and
  any other $, double-quoted identifiers ("..."), a backslash outside a string (psql meta-commands such as \\! or \\o),
  CR and every other control character except LF and TAB. Input is read as raw UTF-8 bytes (no newline translation).
- Exactly one statement (a trailing semicolon is fine). It must start with SELECT, WITH, COPY, SHOW, EXPLAIN, TABLE
  or VALUES. COPY must write TO STDOUT.
- Transaction-control and write keywords, and a few risky functions, are refused anywhere outside literals.
This is a second safeguard; the first is a database role that can only read.
"""
import re
import sys

READ_START = {"select", "with", "copy", "show", "explain", "table", "values"}
BLOCKED = {"begin", "commit", "rollback", "end", "abort", "start", "savepoint", "release", "prepare", "set", "reset",
		   "insert", "update", "delete", "merge", "truncate", "drop", "alter", "create", "grant", "revoke", "comment",
		   "vacuum", "analyze", "cluster", "reindex", "refresh", "lock", "call", "do", "listen", "notify", "discard",
		   "import", "load", "checkpoint", "security",
		   # functions that change settings, reach other servers or files, or act on other sessions
		   "set_config", "dblink", "dblink_exec", "lo_import", "lo_export", "pg_read_file", "pg_read_binary_file",
		   "pg_ls_dir", "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf"}
CONTEXT_OK = {"end"}  # allowed when the statement uses CASE ... END


def refuse(msg):
	print("refused: " + msg, file=sys.stderr)
	sys.exit(2)


def scan(sql):
	"""Split into statements; each is a list of (kind, value, paren depth) tokens found outside '...' literals and
	-- comments, where kind is "w" (lower-case word), "s" (a '...' literal), "(" or ")"."""
	# PostgreSQL ends -- comments at LF or CR; refuse CR and every other control character except LF and TAB,
	# so the only line ending this scanner has to understand is LF.
	bad_ctrl = sorted({f"0x{ord(ch):02x}" for ch in sql if (ord(ch) < 32 and ch not in "\n\t") or ord(ch) == 127})
	if bad_ctrl:
		refuse("control characters are not allowed (found " + ", ".join(bad_ctrl) + "); use LF line endings")
	stmts, toks, i, n, depth = [], [], 0, len(sql), 0
	while i < n:
		c = sql[i]
		if sql.startswith("--", i):
			j = sql.find("\n", i)
			i = n if j < 0 else j + 1
		elif sql.startswith("/*", i) or sql.startswith("*/", i):
			refuse("block comments (/* */) are not allowed; use -- comments")
		elif c == "'":
			if i > 0 and (sql[i - 1].isalnum() or sql[i - 1] in "_&"):
				refuse("prefixed string literals (E'...', U&'...', B'...', X'...') are not allowed")
			i += 1
			while True:
				j = sql.find("'", i)
				if j < 0:
					refuse("unterminated string")
				if j + 1 < n and sql[j + 1] == "'":
					i = j + 2
					continue
				i = j + 1
				break
			toks.append(("s", "", depth))  # a literal is kept as a token so it cannot be skipped over in structure checks
		elif c == '"':
			refuse('double-quoted identifiers are not allowed')
		elif c == "$":
			refuse("dollar quoting and $ parameters are not allowed")
		elif c == "\\":
			refuse("backslash outside a string is not allowed (psql would treat it as a meta-command such as \\! or \\o)")
		elif c == ";":
			if depth:
				refuse("unbalanced parentheses")
			stmts.append(toks)
			toks = []
			i += 1
		elif c == "(":
			toks.append(("(", "(", depth))
			depth += 1
			i += 1
		elif c == ")":
			depth -= 1
			if depth < 0:
				refuse("unbalanced parentheses")
			toks.append((")", ")", depth))
			i += 1
		elif c.isalpha() or c == "_":
			m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", sql[i:])
			toks.append(("w", m.group(0).lower(), depth))
			i += len(m.group(0))
		else:
			i += 1
	if depth:
		refuse("unbalanced parentheses")
	stmts.append(toks)
	return [t for t in stmts if any(k == "w" for k, _, _ in t)]


def check(sql):
	stmts = scan(sql)
	if len(stmts) != 1:
		refuse("exactly one statement is allowed")
	toks = stmts[0]
	words = [v for k, v, _ in toks if k == "w"]
	if toks[0][0] != "w" or toks[0][1] not in READ_START:
		refuse("the statement must start with SELECT, WITH, COPY, SHOW, EXPLAIN, TABLE or VALUES")
	if toks[0][1] == "copy":
		check_copy(toks)
	has_case = "case" in words
	bad = sorted({w for w in words if w in BLOCKED and not (w in CONTEXT_OK and has_case)})
	if bad:
		refuse("blocked keyword(s) outside literals: " + ", ".join(bad))


COPY_OPTION_WORDS = {"csv", "header", "with", "format", "delimiter", "null", "quote", "escape", "force_quote",
					 "encoding", "text", "true", "false", "on", "off"}


def check_copy(toks):
	"""Only `COPY ( <query> ) TO STDOUT [options]` is accepted, checked at the outer (depth 0) level, so words such as
	`to stdout` inside the query cannot stand in for the real destination."""
	if len(toks) < 2 or toks[1][0] != "(":
		refuse("COPY must have the form COPY (<query>) TO STDOUT")
	close = next((j for j in range(2, len(toks)) if toks[j][0] == ")" and toks[j][2] == 0), None)
	if close is None:
		refuse("COPY must have the form COPY (<query>) TO STDOUT")
	rest = toks[close + 1:]
	if len(rest) < 2 or rest[0][:2] != ("w", "to") or rest[1][:2] != ("w", "stdout"):
		refuse("COPY must write TO STDOUT immediately after the query (no file name, no PROGRAM)")
	extra = sorted({v for k, v, _ in rest[2:] if k == "w" and v not in COPY_OPTION_WORDS})
	if extra:
		refuse("unsupported word(s) after TO STDOUT: " + ", ".join(extra))


if __name__ == "__main__":
	raw = sys.stdin.buffer.read()  # bytes: no newline translation, so a CR is seen as a CR
	try:
		text = raw.decode("utf-8")
	except UnicodeDecodeError:
		refuse("input is not valid UTF-8")
	if text.endswith("\n"):
		text = text[:-1]  # the newline added by `print -r --` in db_query.sh
	check(text)
