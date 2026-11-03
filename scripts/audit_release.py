#!/usr/bin/env python3
"""Conservative filename/credential pattern check for publishing a Git repository.

Run at the repository root: python scripts/audit_release.py --git-history
This is an aid, NOT a guarantee that all confidential information is absent.
Only prints matching file names and issue categories, never matched tokens.
"""
from __future__ import annotations
import argparse, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

SUSPICIOUS_NAMES=re.compile(r'(?i)(?:^|/)(?:enterprise[ _-]?data|data/raw|secrets?|credentials?|private[ _-]?keys?)(?:/|$)|(?:^|/)(?:gurobi\.lic|\.env|[^/]+\.(?:xlsx|xls|pem|p12|pfx|key|lic))$')
SENSITIVE_CONTENT=[
 ('Gurobi LicenseID assignment',re.compile(rb'(?i)\bLicenseID\b\s*(?:=|:|to value|,)\s*["\']?\d{5,}')),
 ('Gurobi web license credential',re.compile(rb'(?i)\b(?:WLSACCESSID|WLSSECRET|GUROBI_WLSSECRET)\b\s*[=:]\s*[A-Za-z0-9+/=_-]{8,}')),
 ('access token pattern',re.compile(rb'\b(?:ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{15,}')),
 ('private key block',re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')),
 ('AWS access key format',re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
 ('literal credential assignment',re.compile(rb'(?im)^\s*(?:password|api[_-]?key|access[_-]?token|secret)\s*[=:]\s*["\'][^"\']{8,}["\']')),
]
RESTRICTED_CONTENT=[]  # Restricted hourly and empirical CSV file names are checked above.

def git(*args):
 return subprocess.run(['git',*args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout

def scan(name,data):
 issues=[]
 if SUSPICIOUS_NAMES.search(name.replace('\\','/')): issues.append('suspicious file path')
 if name.lower().endswith('.csv') and (('hourly' in name.lower()) or ('representative' in name.lower())):issues.append('restricted-looking CSV file path')
 if data is not None:
  for category,pat in SENSITIVE_CONTENT+RESTRICTED_CONTENT:
   if pat.search(data):issues.append(category)
 return sorted(set(issues))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--git-history',action='store_true');args=ap.parse_args()
 findings=[];checked=0
 for p in ROOT.rglob('*'):
  if not p.is_file() or '.git' in p.parts or '__pycache__' in p.parts:continue
  name=p.relative_to(ROOT).as_posix()
  data=p.read_bytes() if p.stat().st_size < 5_000_000 else None
  checked+=1
  for category in scan(name,data):findings.append(('working tree',name,category))
 if args.git_history:
  try:
   objects=git('rev-list','--objects','--all').decode('utf-8','replace').splitlines()
  except (OSError,subprocess.CalledProcessError):
   print('[ERROR] Git clone/history not available; run from a cloned repository, with Git installed.')
   return 2
  for line in objects:
   oid,_,name=line.partition(' ')
   if not name:continue
   if git('cat-file','-t',oid).strip()!=b'blob':continue
   size=int(git('cat-file','-s',oid).strip())
   data=git('cat-file','-p',oid) if size<5_000_000 else None
   checked+=1
   for category in scan(name,data):findings.append(('git history',name,category))
 print(f'[CHECK] {checked} files/objects scanned; {len(findings)} potential issues.')
 for scope,path,category in sorted(set(findings)):
  print(f'[REVIEW] {scope}: {path} — {category}')
 if findings:
  print('[ACTION] Review flagged files and ALL relevant history before publishing. Do not print credential contents.')
  return 1
 print('[PASS] No matches for this limited set of patterns. Manual privacy review remains required.')
 return 0

if __name__=='__main__':sys.exit(main())
