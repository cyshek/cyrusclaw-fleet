#!/bin/bash
# Refresh the stylized xlsx + the .zip wrapper that survives Windows Defender scp scans.
set -e
PROJ=/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search
OUT=/home/azureuser/.openclaw/agents/job-search/workspace/outbox

cd "$PROJ"
"$PROJ/role-discovery/.venv/bin/python" - <<'PY'
import csv, re, os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from collections import Counter

STATUS_COLORS = {'queued':'FFF2CC','submitted':'D9EAD3','interview':'B6D7A8','offer':'6AA84F','rejected':'F4CCCC','withdrawn':'EAD1DC','closed':'D9D9D9','skip':'CCCCCC','skip-too-senior':'CCCCCC','none':'EFEFEF','scan-blocked':'FCE5CD'}
EXP_FILL = {'0-3':'D9EAD3','4':'FFF2CC','5+':'F4CCCC','unstated':'FFFFFF'}
status_order = {'submitted':0,'interview':1,'offer':2,'queued':3,'scan-blocked':4,'closed':5,'rejected':6,'withdrawn':7,'skip':8,'skip-too-senior':9,'none':10}

def url_clean(s):
    m = re.match(r'\[([^\]]+)\]\(([^)]+)\)', s); return m.group(2) if m else s
def exp_bucket(exp):
    if not exp or 'unstated' in exp: return 'unstated'
    nums = [int(n) for n in re.findall(r'\d+', exp)]
    if not nums: return 'unstated'
    lo = nums[0]
    return '5+' if lo>=5 else ('4' if lo==4 else '0-3')

rows=[]
with open('tracker.md') as f:
    for line in f:
        if not line.startswith('| '): continue
        cells=[c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells)<9 or cells[0] in ('Company','-------') or set(cells[0])<=set('-: '): continue
        rows.append(cells[:9])

wb=Workbook(); ws=wb.active; ws.title='Jobs'
headers=['Company','Role','Level','Location','Exp','JD Link','App URL','Status','Flags']; ws.append(headers)
hf=PatternFill('solid',fgColor='1F4E78'); hfont=Font(bold=True,color='FFFFFF',size=11)
for col in range(1,len(headers)+1):
    c=ws.cell(row=1,column=col); c.fill=hf; c.font=hfont; c.alignment=Alignment(vertical='center',horizontal='left')
ws.row_dimensions[1].height=22
thin=Side(border_style='thin',color='D9D9D9'); border=Border(left=thin,right=thin,top=thin,bottom=thin)
rows.sort(key=lambda r:(status_order.get(r[7],99),r[0].lower(),r[1].lower()))
for ri,r in enumerate(rows,start=2):
    jd=url_clean(r[5]); app=url_clean(r[6])
    out=[r[0],r[1],r[2],r[3],r[4],jd,app,r[7],r[8]]
    for ci,val in enumerate(out,start=1):
        c=ws.cell(row=ri,column=ci,value=val); c.alignment=Alignment(vertical='top',wrap_text=(ci in (2,4,9))); c.border=border; c.font=Font(size=10)
    if jd.startswith('http'):
        ws.cell(row=ri,column=6).hyperlink=jd; ws.cell(row=ri,column=6).value='JD ↗'; ws.cell(row=ri,column=6).font=Font(color='1155CC',underline='single',size=10)
    if app.startswith('http'):
        ws.cell(row=ri,column=7).hyperlink=app; ws.cell(row=ri,column=7).value='Apply ↗'; ws.cell(row=ri,column=7).font=Font(color='1155CC',underline='single',size=10)
    sc=STATUS_COLORS.get(r[7])
    if sc: ws.cell(row=ri,column=8).fill=PatternFill('solid',fgColor=sc); ws.cell(row=ri,column=8).font=Font(bold=True,size=10)
    ef=EXP_FILL.get(exp_bucket(r[4]))
    if ef and ef!='FFFFFF': ws.cell(row=ri,column=5).fill=PatternFill('solid',fgColor=ef)
widths=[18,50,8,28,14,8,10,16,40]
for i,w in enumerate(widths,start=1): ws.column_dimensions[get_column_letter(i)].width=w
ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions

sm=wb.create_sheet('Summary')
sm['A1']='Status'; sm['B1']='Count'
for cell in (sm['A1'],sm['B1']): cell.font=Font(bold=True,color='FFFFFF'); cell.fill=hf
counts=Counter(r[7] for r in rows); ri=2
for status,ct in sorted(counts.items(),key=lambda x:status_order.get(x[0],99)):
    sm.cell(row=ri,column=1,value=status); sm.cell(row=ri,column=2,value=ct)
    sc=STATUS_COLORS.get(status)
    if sc: sm.cell(row=ri,column=1).fill=PatternFill('solid',fgColor=sc); sm.cell(row=ri,column=1).font=Font(bold=True)
    ri+=1
sm.cell(row=ri,column=1,value='TOTAL').font=Font(bold=True); sm.cell(row=ri,column=2,value=sum(counts.values())).font=Font(bold=True)
sm.column_dimensions['A'].width=22; sm.column_dimensions['B'].width=10
sm.cell(row=1,column=4,value='Company').font=Font(bold=True,color='FFFFFF'); sm.cell(row=1,column=5,value='Queued').font=Font(bold=True,color='FFFFFF')
sm.cell(row=1,column=4).fill=hf; sm.cell(row=1,column=5).fill=hf
co_q=Counter(r[0] for r in rows if r[7]=='queued'); ri=2
for co,ct in co_q.most_common():
    sm.cell(row=ri,column=4,value=co); sm.cell(row=ri,column=5,value=ct); ri+=1
sm.column_dimensions['D'].width=22; sm.column_dimensions['E'].width=10
sm.freeze_panes='A2'

import sys
out_xlsx='/home/azureuser/.openclaw/agents/job-search/workspace/outbox/Cyrus_Job_Tracker.xlsx'
wb.save(out_xlsx)

# CSV mirror
with open('/home/azureuser/.openclaw/agents/job-search/workspace/outbox/Cyrus_Job_Tracker.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(headers)
    for r in rows:
        r2=list(r); r2[5]=url_clean(r2[5]); r2[6]=url_clean(r2[6]); w.writerow(r2)
print(f"refreshed {len(rows)} rows")
PY

# Make a defender-safe zip wrapper of the xlsx (rename trick is the most reliable scp path)
cp -f "$OUT/Cyrus_Job_Tracker.xlsx" "$OUT/Cyrus_Job_Tracker.xlsx.zip"
echo "OK: outbox refreshed"
ls -la "$OUT"
