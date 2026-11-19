# -*- coding: utf-8 -*-
"""Run one named extract from a tracked SQL file through db_query.sh and save it as CSV.

usage: RETRO_DB_ENV=<env file> python3 00_common/src/run_extract.py <sql file> <name> <out.csv> [--list KEY=FILE ...]

- A block starts at a line `-- @extract <name>` and ends at the next `-- @extract` line or a line `-- @end`.
  Block names must be unique within a file (duplicates are refused before anything runs).
  The block is one SELECT/WITH statement (one trailing semicolon outside literals and comments is dropped); it is run
  as `copy (<block>) to stdout csv header` by db_query.sh (read-only transaction, statement check).
- `{{KEY}}` in the block is replaced by the contents of FILE given with --list KEY=FILE. The file must hold a
  comma-separated list of integers (for example the seq lists in 03_irs_risk_rank/00_Data/frozen_20261119/).
- The output file must not exist yet; existing extracts are never overwritten. Rows go to a new uniquely named
  temporary file in the output folder, which is published with a hard link only when the query succeeds (the link
  fails if the output appeared meanwhile) and is always removed afterwards.
- Prints the number of data records to stderr. Counts are not written anywhere else.
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DB_QUERY = os.path.join(HERE, "db_query.sh")
MARK = re.compile(r"^--\s*@extract\s+(\w+)\s*$")
END = re.compile(r"^--\s*@end\s*$")
INT_LIST = re.compile(r"^\d+(,\d+)*$")


def read_block(path, name):
	lines = open(path, encoding="utf-8").read().split("\n")
	seen, cur, found = {}, None, []
	for no, ln in enumerate(lines, 1):
		m = MARK.match(ln.strip())
		if m:
			cur = m.group(1)
			seen.setdefault(cur, []).append(no)
			continue
		if END.match(ln.strip()):
			cur = None
			continue
		if cur == name:
			found.append(ln)
	dup = {k: v for k, v in seen.items() if len(v) > 1}
	if dup:
		sys.exit(f"refused: duplicate block names in {path}: " + "; ".join(f"{k} (lines {', '.join(map(str, v))})" for k, v in sorted(dup.items())))
	body = "\n".join(found).strip()
	if not body:
		sys.exit(f"no block named {name!r} in {path}")
	return body


def strip_semicolon(body):
	"""Drop the statement's final semicolon when only whitespace and -- comments follow it.
	Semicolons inside '...' literals or -- comments are never touched; any other semicolon stays for sql_guard."""
	i, n, last = 0, len(body), None
	while i < n:
		if body.startswith("--", i):
			j = body.find("\n", i)
			i = n if j < 0 else j + 1
		elif body[i] == "'":
			j = i + 1
			while True:
				k = body.find("'", j)
				if k < 0:
					return body  # unterminated literal: leave it for sql_guard to refuse
				if k + 1 < n and body[k + 1] == "'":
					j = k + 2
					continue
				i = k + 1
				break
		else:
			if body[i] == ";":
				last = i
			i += 1
	if last is None:
		return body
	rest = body[last + 1:]
	if all(not ln.strip() or ln.strip().startswith("--") for ln in rest.split("\n")):
		return body[:last] + rest
	return body


def main():
	ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
	ap.add_argument("sql_file")
	ap.add_argument("name")
	ap.add_argument("out")
	ap.add_argument("--list", action="append", default=[], metavar="KEY=FILE")
	a = ap.parse_args()
	if os.path.lexists(a.out):
		sys.exit(f"refused: {a.out} already exists (extracts are never overwritten)")
	body = strip_semicolon(read_block(a.sql_file, a.name))
	for item in a.list:
		key, _, f = item.partition("=")
		vals = open(f, encoding="utf-8").read().strip()
		if not INT_LIST.match(vals):
			sys.exit(f"refused: {f} is not a comma-separated list of integers")
		body = body.replace("{{" + key + "}}", vals)
	left = re.findall(r"\{\{(\w+)\}\}", body)
	if left:
		sys.exit("missing --list for: " + ", ".join(sorted(set(left))))
	sql = f"copy (\n{body}\n) to stdout csv header"
	out_dir = os.path.dirname(os.path.abspath(a.out))
	os.makedirs(out_dir, exist_ok=True)
	fd, tmp = tempfile.mkstemp(dir=out_dir, prefix="." + os.path.basename(a.out) + ".", suffix=".part")  # O_EXCL, unique
	try:
		with os.fdopen(fd, "wb") as fh:
			r = subprocess.run([DB_QUERY, sql], stdout=fh)
		if r.returncode != 0:
			sys.exit(f"query failed (exit {r.returncode}); nothing saved")
		n = count_records(tmp)  # before publishing; reporting only, never decides success
		try:
			os.link(tmp, a.out)  # fails if the output appeared meanwhile, so nothing is overwritten
		except FileExistsError:
			sys.exit(f"refused: {a.out} already exists (extracts are never overwritten)")
	finally:
		if os.path.lexists(tmp):
			os.remove(tmp)
	print(f"{a.name}: {'?' if n is None else n} records -> {a.out}", file=sys.stderr)


def count_records(path):
	"""Number of CSV records excluding the header (quoted newlines handled); None if the file cannot be parsed."""
	csv.field_size_limit(2**31 - 1)  # JSON columns can be long; the default limit is 131072 characters
	try:
		with open(path, newline="", encoding="utf-8") as fh:
			return max(sum(1 for _ in csv.reader(fh)) - 1, 0)
	except (csv.Error, UnicodeDecodeError):
		return None


if __name__ == "__main__":
	main()
