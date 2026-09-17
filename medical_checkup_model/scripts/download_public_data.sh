#!/usr/bin/env bash
# 공공데이터 다운로드 (00_Data/public). 이미 받은 파일은 건너뜀.
set -euo pipefail
cd "$(dirname "$0")/../00_Data/public"

BASE11="https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2011/DataFiles"
BASE13="https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles"

mkdir -p nhanes/2011_2012 nhanes/2013_2014 lifesnaps

for f in DEMO_G BPX_G BMX_G GLU_G TCHOL_G HDL_G TRIGLY_G MGX_G PAXHD_G PAXHR_G; do
  [ -s "nhanes/2011_2012/$f.xpt" ] || curl -sf -o "nhanes/2011_2012/$f.xpt" "$BASE11/$f.xpt"
done
for f in DEMO_H BPX_H BMX_H GLU_H TCHOL_H HDL_H TRIGLY_H MGX_H PAXHD_H PAXHR_H; do
  [ -s "nhanes/2013_2014/$f.xpt" ] || curl -sf -o "nhanes/2013_2014/$f.xpt" "$BASE13/$f.xpt"
done

[ -s lifesnaps/rais_anonymized.zip ] || \
  curl -sfL -o lifesnaps/rais_anonymized.zip \
    "https://zenodo.org/api/records/7229547/files/rais_anonymized.zip/content"

du -sh nhanes/2011_2012 nhanes/2013_2014 lifesnaps
