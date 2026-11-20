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
- --forbid-scan TABLE (repeatable): before extracting, run EXPLAIN (FORMAT JSON) on the block and refuse unless every
  plan node that reads TABLE is an Index Scan or Index Only Scan (a plan that never reads TABLE is refused too).
  Inherited or partitioned tables are refused. Use it for blocks that must stay on an index of a very large table
  (for example heartrate_days).
"""
import argparse
import csv
import json
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


def _psql_lines(out):
	"""Data lines of psql aligned output (between the dashed header rule and the row-count footer)."""
	lines = out.split("\n")
	k = next((n for n, ln in enumerate(lines) if re.match(r"^-+(\+-+)*$", ln.strip())), None)
	if k is None:
		return []
	data = []
	for ln in lines[k + 1:]:
		if re.match(r"^\(\d+ rows?\)$", ln.strip()):
			break
		data.append(ln)
	return data


def _plan_nodes(node):
	yield node
	for child in node.get("Plans", []):  # includes InitPlan / SubPlan children
		yield from _plan_nodes(child)


def check_plan(body, rel):
	"""Refuse unless every access to table rel in the EXPLAIN (FORMAT JSON) plan is an index scan.
	Inherited or partitioned tables are refused, because their plans name the child tables instead."""
	if not re.match(r"^\w+$", rel):
		sys.exit(f"refused: {rel!r} is not a plain table name")
	q = (f"select (select count(*) from pg_inherits i join pg_class c on c.oid in (i.inhparent, i.inhrelid) "
		 f"where c.relname = '{rel}') + (select count(*) from pg_class where relname = '{rel}' and relkind = 'p') n")
	r = subprocess.run([DB_QUERY, q], capture_output=True, text=True)
	vals = [ln.strip() for ln in _psql_lines(r.stdout) if ln.strip()]
	if r.returncode != 0 or len(vals) != 1 or not vals[0].isdigit():
		sys.exit(f"plan check failed: could not read the inheritance check for {rel}")
	if int(vals[0]):
		sys.exit(f"refused: {rel} is inherited or partitioned; --forbid-scan supports plain tables only")
	r = subprocess.run([DB_QUERY, "explain (format json)\n" + body], capture_output=True, text=True)
	if r.returncode != 0:
		sys.exit(f"plan check failed (exit {r.returncode}): {r.stderr.strip()[-300:]}")
	text = "\n".join(ln.rstrip()[:-1] if ln.rstrip().endswith("+") else ln for ln in _psql_lines(r.stdout))
	try:
		plans = json.loads(text)
	except ValueError:
		sys.exit("plan check failed: could not parse the JSON plan")
	nodes = [n for p in plans for n in _plan_nodes(p["Plan"])]
	hits = [n for n in nodes if n.get("Relation Name") == rel]
	if not hits:
		sys.exit(f"refused: the plan does not read table {rel}; check the table name")
	bad = sorted({n["Node Type"] for n in hits if n["Node Type"] not in ("Index Only Scan", "Index Scan")})
	if bad:
		sys.exit(f"refused: the plan reads {rel} by {', '.join(bad)}; nothing extracted")
	print(f"plan check: {rel} is read only by index scans ({len(hits)} plan nodes)", file=sys.stderr)


def main():
	ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
	ap.add_argument("sql_file")
	ap.add_argument("name")
	ap.add_argument("out")
	ap.add_argument("--list", action="append", default=[], metavar="KEY=FILE")
	ap.add_argument("--forbid-scan", action="append", default=[], metavar="TABLE")
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
	for rel in a.forbid_scan:
		check_plan(body, rel)
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
