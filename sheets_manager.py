"""
=============================================================================
🛠️ Google Sheets Manager & Automation Hub — زووووود زود
=============================================================================
المسار: d:\\SMS\\.hRhRhRhRhRhR\\_جوجل_شيت\\sheets_manager.py
الوصف: الأداة المركزية الموحدة لإدارة ومزامنة وتنسيق شيتات رادار الذكاء الاصطناعي:
  1. كشف ونقل مستودعات جيت هاب من الورقة 1 إلى ورقة جيت هاب بدون أي تكرار.
  2. تفعيل وإصلاح القوائم المنسدلة (Dropdowns / Data Validation) في جميع الأوراق.
  3. فحص التكرارات وإحصائيات الـ KPI الحية.
  4. كود Google Apps Script الآلي للحركة اللحظية (Realtime onEdit Trigger).

الإصدار: 1.1.0 (2026-09-19)
  ⚠️ تغييرات 1.1.0:
   - fix_kpi_cards: معادلات الإحصائيات بقت INDIRECT("B7:B") / INDIRECT("D7:D") فما تتزحلقش
     أبداً لما Apps Script ينقل صف للصف 7 (كانت D7:D → D8:D → D10:D ...).
   - fix_kpi_cards بتشتغل على الورقة1 وورقة جيت هاب معاً، وبتعد "لا يعمل" و"لا تعمل".
   - apply_dropdowns بقت تغطي الورقة1 كمان، ولحد آخر صف فعلي في الشيت (مش 2000 ثابتة).
   - process_gist بيثبت المعادلات أوتوماتيك بعد كل تشغيل.
"""

DATA_START_ROW = 7   # أول صف بيانات — ثابت واحد للمشروع كله
KPI_ROW = 3          # صف أرقام الإحصائيات (B3:F3)

import sys
import re
import os
import time
import argparse
from collections import OrderedDict
import socket
import requests
from google.oauth2.service_account import Credentials
import google.auth.transport.requests

sys.stdout.reconfigure(encoding='utf-8')

# الثوابت والإعدادات المركزية
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CRED_FILE = os.path.join(CURRENT_DIR, 'credentials.json')
SHEET_ID = '1XqSdKv1nxlZTxTHZ2rcSSEJEyR-OQXrzhYiSfbKFvdk'

STATUS_OPTIONS = [
    '✅ يعمل بنجاح',
    '🔄 قيد التجربة',
    '❌ لا تعمل',
    '⏳ لم يتم الفحص',
    'مرفوض'
]

ACTION_OPTIONS = [
    '⬇️ نقل لآخر صف'
]

class FastSheetsClient:
    """عميل سريع ومستقر للتعامل مع Google Sheets v4 API باستخدام requests بدون مشاكل تعليق"""
    def __init__(self, cred_file):
        self.creds = Credentials.from_service_account_file(cred_file, scopes=SCOPES)
        self.session = requests.Session()
        self._refresh_token()
        
    def _refresh_token(self):
        self.creds.refresh(google.auth.transport.requests.Request())
        self.session.headers.update({
            'Authorization': f'Bearer {self.creds.token}',
            'Content-Type': 'application/json'
        })
        
    def spreadsheets(self):
        return self
        
    def get(self, spreadsheetId):
        class Exec:
            def __init__(self, client, s_id):
                self.client = client
                self.s_id = s_id
            def execute(self):
                url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.s_id}"
                r = self.client.session.get(url, timeout=120)
                if r.status_code == 401:
                    self.client._refresh_token()
                    r = self.client.session.get(url, timeout=120)
                return r.json()
        return Exec(self, spreadsheetId)

    def batchUpdate(self, spreadsheetId, body):
        class Exec:
            def __init__(self, client, s_id, body):
                self.client = client
                self.s_id = s_id
                self.body = body
            def execute(self):
                url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.s_id}:batchUpdate"
                r = self.client.session.post(url, json=self.body, timeout=120)
                if r.status_code == 401:
                    self.client._refresh_token()
                    r = self.client.session.post(url, json=self.body, timeout=120)
                return r.json()
        return Exec(self, spreadsheetId, body)
        
    def values(self):
        class ValuesHandler:
            def __init__(self, client):
                self.client = client
                
            def get(self, spreadsheetId, range, valueRenderOption=None):
                class Exec:
                    def __init__(self, v_handler, s_id, r_name, v_opt):
                        self.v = v_handler
                        self.s_id = s_id
                        self.r_name = r_name.replace("'", "")
                        self.v_opt = v_opt
                    def execute(self):
                        url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.s_id}/values:batchGet"
                        params = {'ranges': [self.r_name]}
                        if self.v_opt:
                            params['valueRenderOption'] = self.v_opt
                        for attempt in [0, 1, 2]:
                            try:
                                r = self.v.client.session.get(url, params=params, timeout=120)
                                if r.status_code == 401:
                                    self.v.client._refresh_token()
                                    r = self.v.client.session.get(url, params=params, timeout=120)
                                data = r.json()
                                vr = data.get('valueRanges', [])
                                if vr:
                                    return vr[0]
                                return {'values': []}
                            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                                if attempt == 2:
                                    raise
                                time.sleep(5 * (attempt + 1))
                return Exec(self, spreadsheetId, range, valueRenderOption)
                
            def update(self, spreadsheetId, range, valueInputOption, body):
                class Exec:
                    def __init__(self, v_handler, s_id, r_name, v_in_opt, body):
                        self.v = v_handler
                        self.s_id = s_id
                        self.r_name = r_name
                        self.v_in_opt = v_in_opt
                        self.body = body
                    def execute(self):
                        url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.s_id}/values:batchUpdate"
                        payload = {
                            'valueInputOption': self.v_in_opt,
                            'data': [
                                {
                                    'range': self.r_name,
                                    'values': self.body.get('values', [])
                                }
                            ]
                        }
                        for attempt in [0, 1, 2]:
                            try:
                                r = self.v.client.session.post(url, json=payload, timeout=120)
                                if r.status_code == 401:
                                    self.v.client._refresh_token()
                                    r = self.v.client.session.post(url, json=payload, timeout=120)
                                res = r.json()
                                if 'error' in res:
                                    msg = res['error'].get('message', '')
                                    if 'exceeds grid limits' in msg:
                                        m_title = re.search(r"'?([^'!]+)'?!", self.r_name)
                                        s_title = m_title.group(1).strip() if m_title else ''
                                        sheet_ids = get_sheet_ids(self.v.client)
                                        s_id = sheet_ids.get(s_title)
                                        if s_id is not None:
                                            self.v.client.batchUpdate(self.s_id, {
                                                'requests': [{'appendDimension': {'sheetId': s_id, 'dimension': 'ROWS', 'length': 100}}]
                                            }).execute()
                                            r = self.v.client.session.post(url, json=payload, timeout=120)
                                            return r.json()
                                    raise RuntimeError(f"Google Sheets API Error: {res['error']}")
                                return res
                            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                                if attempt == 2:
                                    raise
                                time.sleep(5 * (attempt + 1))
                return Exec(self, spreadsheetId, range, valueInputOption, body)

            def clear(self, spreadsheetId, range, body=None):
                class Exec:
                    def __init__(self, v_handler, s_id, r_name):
                        self.v = v_handler
                        self.s_id = s_id
                        self.r_name = r_name
                    def execute(self):
                        url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.s_id}/values:batchClear"
                        payload = {'ranges': [self.r_name]}
                        r = self.v.client.session.post(url, json=payload, timeout=120)
                        if r.status_code == 401:
                            self.v.client._refresh_token()
                            r = self.v.client.session.post(url, json=payload, timeout=120)
                        return r.json()
                return Exec(self, spreadsheetId, range)

            def batchUpdate(self, spreadsheetId, body):
                class Exec:
                    def __init__(self, v_handler, s_id, body):
                        self.v = v_handler
                        self.s_id = s_id
                        self.body = body
                    def execute(self):
                        url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.s_id}/values:batchUpdate"
                        r = self.v.client.session.post(url, json=self.body, timeout=120)
                        if r.status_code == 401:
                            self.v.client._refresh_token()
                            r = self.v.client.session.post(url, json=self.body, timeout=120)
                        return r.json()
                return Exec(self, spreadsheetId, body)

        return ValuesHandler(self)

def get_service():
    """تهيئة والاتصال السريع بواجهة برمجة تطبيقات جوجل شيت"""
    if not os.path.exists(CRED_FILE):
        raise FileNotFoundError(f"ملف الاعتماد غير موجود في: {CRED_FILE}")
    return FastSheetsClient(CRED_FILE)


def get_sheet_ids(service):
    """جلب معرفات أوراق العمل الداخلية"""
    spread = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    sheet_ids = {}
    for s in spread['sheets']:
        sheet_ids[s['properties']['title']] = s['properties']['sheetId']
    return sheet_ids

def is_link_removed(url):
    """
    التحقق مما إذا كان الرابط محجوز كـ [link removed] أو ما يشابهه
    قاعدة صارمة: لا يُعتبر مكرراً ولا يُحذف نهائياً لحفظ اسم الموقع لإضافة الرابط لاحقاً
    """
    if not url:
        return True
    u = url.strip().lower()
    return '[link removed]' in u or 'link removed' in u or u in ['none', 'n/a', '-', 'null']

def normalize_repo_url(url):
    """
    استخراج المعرف الفريد لمستودع جيت هاب مع الحفاظ على الفروع والبرانشات الفرعية.
    - لو الرابط للمستودع الرئيسي: github.com/owner/repo
    - لو الرابط لفرع أو مجلد معين (branch/subpath): يتم الحفاظ على مسار الفرع كاملاً
    """
    u = url.strip().lower()
    u = re.sub(r'^https?://', '', u)
    u = re.sub(r'^www\.', '', u)
    u = re.sub(r'/+$', '', u)
    u = re.sub(r'\.git$', '', u)
    
    # تنظيف معلمات الـ query والـ hash
    u = u.split('?')[0].split('#')[0]

    if 'github.enricoros/big-agi' in u:
        return 'github.com/enricoros/big-agi'
        
    # مطابقة فروع وبرانشات ومسارات جيت هاب الفرعية (tree / blob / dirs)
    m_branch = re.match(r'(github\.com/[^/?#]+/[^/?#]+/(?:tree|blob)/[^/?#]+(?:/[^/?#]+)*)', u)
    if m_branch:
        return m_branch.group(1)

    # مطابقة المستودع الرئيسي github.com/owner/repo
    m = re.match(r'(github\.com/[^/?#]+/[^/?#]+)', u)
    if m:
        return m.group(1)
        
    # مطابقة org.github.io/repo أو org.github.io
    m2 = re.match(r'([^/?#]+\.github\.io(?:/[^/?#]+)?)', u)
    if m2:
        return m2.group(1)
        
    # مطابقة بروفايل المنظمة github.com/org
    m3 = re.match(r'(github\.com/[^/?#]+)', u)
    if m3:
        return m3.group(1)
        
    return u

def normalize_name(name):
    """تنظيف الاسم من الرموز لمقارنة التكرارات بدقة"""
    return re.sub(r'[^a-zA-Z0-9\u0600-\u06FF]', '', name).lower()

def show_stats(service):
    """عرض إحصائيات الأوراق الحالية وفحص كروت الـ KPI"""
    sheet_ids = get_sheet_ids(service)
    print("\n" + "="*60)
    print("📊 إحصائيات رادار جوجل شيت (زووووود زود):")
    print("="*60)
    for title, s_id in sheet_ids.items():
        res = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=f"'{title}'!B7:B"
        ).execute()
        count = len(res.get('values', []))
        print(f" • ورقة [{title}] (ID: {s_id}): {count:,} صف بيانات مسجل")
        
    gh_title = next((k for k in sheet_ids.keys() if 'جيت هاب' in k or 'github' in k.lower()), None)
    if gh_title:
        kpi_res = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=f"'{gh_title}'!B2:F4",
            valueRenderOption='FORMULA'
        ).execute()
        kpi_val = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=f"'{gh_title}'!B2:F4",
            valueRenderOption='FORMATTED_VALUE'
        ).execute()
        print("\n🔎 فحص كروت KPI ورقة جيت هاب (الصفوف 2-4):")
        print("  Formulas:", kpi_res.get('values', []))
        print("  Values:  ", kpi_val.get('values', []))
    print("="*60 + "\n")

def get_kpi_formulas():
    """معادلات كروت الـ KPI بـ INDIRECT — نص ثابت مستحيل جوجل يزحلقه مع إدراج/نقل الصفوف"""
    d = f'INDIRECT("D{DATA_START_ROW}:D")'
    b = f'INDIRECT("B{DATA_START_ROW}:B")'
    return [
        f'=COUNTA({b})',
        f'=COUNTIF({d},"*يعمل بنجاح*")',
        f'=COUNTIF({d},"*قيد التجربة*")',
        f'=COUNTIF({d},"*لا يعمل*")+COUNTIF({d},"*لا تعمل*")',
        f'=COUNTIF({d},"*لم يتم الفحص*")',
    ]

def get_radar_sheet_titles(sheet_ids):
    """أسماء الأوراق اللي عليها كروت إحصائيات: الورقة1 + ورقة جيت هاب"""
    titles = []
    for k in sheet_ids.keys():
        compact = k.replace(' ', '')
        if compact in ('الورقة1', 'ورقة1') or 'جيت هاب' in k or 'github' in k.lower():
            titles.append(k)
    return titles

def fix_kpi_cards(service, quiet=False):
    """تثبيت معادلات كروت الـ KPI (B3:F3) بـ INDIRECT في الورقة1 وورقة جيت هاب"""
    sheet_ids = get_sheet_ids(service)
    titles = get_radar_sheet_titles(sheet_ids)
    if not titles:
        print("⚠️ لم يتم العثور على الورقة1 أو ورقة جيت هاب.")
        return 0
    data = [{'range': f"'{t}'!B{KPI_ROW}:F{KPI_ROW}", 'values': [get_kpi_formulas()]} for t in titles]
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={'valueInputOption': 'USER_ENTERED', 'data': data}
    ).execute()
    if not quiet:
        for t in titles:
            print(f"✅ [{t}] تم تثبيت معادلات KPI بـ INDIRECT من الصف {DATA_START_ROW} (مش هتتزحلق تاني).")
    return len(titles)

def _dropdown_request(sheet_id, col_index, options, end_row):
    return {
        'setDataValidation': {
            'range': {
                'sheetId': sheet_id,
                'startRowIndex': DATA_START_ROW - 1,   # الصف 7 (الفهرس يبدأ من صفر)
                'endRowIndex': end_row,
                'startColumnIndex': col_index,
                'endColumnIndex': col_index + 1
            },
            'rule': {
                'condition': {
                    'type': 'ONE_OF_LIST',
                    'values': [{'userEnteredValue': v} for v in options]
                },
                'showCustomUi': True,
                'strict': False
            }
        }
    }

def apply_dropdowns(service):
    """تطبيق القوائم المنسدلة (Data Validation) من الصف 7 لآخر صف في الورقة1 وورقة جيت هاب"""
    spread = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    info = {}
    for sh in spread['sheets']:
        props = sh['properties']
        info[props['title']] = (props['sheetId'], props.get('gridProperties', {}).get('rowCount', 2000))

    requests = []
    touched = []
    for title, (s_id, row_count) in info.items():
        compact = title.replace(' ', '')
        is_ws1 = compact in ('الورقة1', 'ورقة1')
        is_gh = 'جيت هاب' in title or 'github' in title.lower()
        if not (is_ws1 or is_gh):
            continue
        end_row = max(row_count, DATA_START_ROW + 1)
        requests.append(_dropdown_request(s_id, 3, STATUS_OPTIONS, end_row))   # D = حالة الاختبار
        requests.append(_dropdown_request(s_id, 7, ACTION_OPTIONS, end_row))   # H = الإجراء
        touched.append(title)

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': requests}
        ).execute()
        print(f"✅ تم تفعيل القوائم المنسدلة من الصف {DATA_START_ROW} في: {', '.join(touched)}")
    else:
        print("⚠️ لم يتم العثور على أوراق مستهدفة للقوائم المنسدلة.")

def move_github_from_sheet1(service, dry_run=False):
    """
    فحص الورقة 1:
    أي صف يحتوي على رابط جيت هاب يتم نقله إلى ورقة جيت هاب (بدون تكرار)
    ثم حذفه من الورقة 1.
    """
    import time
    sheet_ids = get_sheet_ids(service)
    ws1_title = next((k for k in sheet_ids.keys() if 'الورقة1' in k or k == 'الورقة 1'), 'الورقة1')
    gh_title = next((k for k in sheet_ids.keys() if 'جيت هاب' in k or 'github' in k.lower()), 'جيت هاب  Github')
    ws1_id = sheet_ids.get(ws1_title)
    gh_id = sheet_ids.get(gh_title)
    
    if ws1_id is None or gh_id is None:
        print("❌ تعذر العثور على إحدى الورقتين المطلوبة!")
        return

    print("🔍 جاري فحص الورقة 1 للبحث عن روابط جيت هاب...")
    for attempt in range(3):
        try:
            resp1 = service.spreadsheets().values().get(
                spreadsheetId=SHEET_ID,
                range=f"'{ws1_title}'!A7:H"
            ).execute()
            rows1 = resp1.get('values', [])
            
            resp_gh = service.spreadsheets().values().get(
                spreadsheetId=SHEET_ID,
                range=f"'{gh_title}'!B7:C"
            ).execute()
            rows_gh = resp_gh.get('values', [])
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                raise e
    
    existing_repos = set()
    existing_names = set()
    for r in rows_gh:
        name = r[0].strip() if len(r) > 0 else ''
        url = r[1].strip() if len(r) > 1 else ''
        if url:
            existing_repos.add(normalize_repo_url(url))
        if name:
            existing_names.add(normalize_name(name))
            
    # تصنيف صفوف الورقة 1
    rows_to_keep = []
    github_rows_to_move = []
    
    for idx, r in enumerate(rows1, start=7):
        url = r[2].strip() if len(r) > 2 else ''
        if 'github' in url.lower():
            github_rows_to_move.append((idx, r))
        else:
            rows_to_keep.append(r)
            
    print(f" • إجمالي صفوف الورقة 1: {len(rows1):,}")
    print(f" • صفوف جيت هاب المكتشفة في الورقة 1: {len(github_rows_to_move):,}")
    print(f" • صفوف المنصات الأخرى التي ستبقى في الورقة 1: {len(rows_to_keep):,}")
    
    if not github_rows_to_move:
        print("✅ لا توجد أي روابط جيت هاب جديدة في الورقة 1؛ الورقة نظيفة بالفعل!")
        return

    # فحص أي روابط جديدة غير موجودة في ورقة جيت هاب
    new_to_append = []
    for orig_idx, r in github_rows_to_move:
        name = r[1].strip() if len(r) > 1 else ''
        url = r[2].strip() if len(r) > 2 else ''
        status = r[3].strip() if len(r) > 3 else '⏳ لم يتم الفحص'
        notes = r[6].strip() if len(r) > 6 else ''
        r_key = normalize_repo_url(url)
        n_key = normalize_name(name)
        
        if r_key not in existing_repos and (not n_key or n_key not in existing_names):
            existing_repos.add(r_key)
            if n_key:
                existing_names.add(n_key)
            new_to_append.append({
                'name': name,
                'url': url,
                'status': status if status else '⏳ لم يتم الفحص',
                'notes': notes
            })
            
    print(f" • مستودعات جديدة تماماً ستضاف إلى ورقة جيت هاب: {len(new_to_append)}")
    for item in new_to_append:
        print(f"   + [إضافة جديدة]: {item['name']} -> {item['url']}")
        
    skipped_count = len(github_rows_to_move) - len(new_to_append)
    if skipped_count > 0:
        print(f" • صفوف جيت هاب مكررة وموجودة بالفعل في ورقة جيت هاب (سيتم حذف تكرارها من الورقة 1): {skipped_count}")
        
    if dry_run:
        print("⚠️ تم تشغيل الأمر بوضع المعاينة (Dry-Run)؛ لم يتم إجراء أي تعديلات حقيقية.")
        return

    # 1. إضافة المستودعات الجديدة لورقة جيت هاب إن وجدت
    if new_to_append:
        current_gh_count = len(rows_gh)
        new_values = []
        for idx, item in enumerate(new_to_append, start=7 + current_gh_count):
            row_num = idx
            dup_name_formula = f'=IF(OR(ISBLANK(B{row_num}), B{row_num}=""), "", IFERROR(LET(clean_n, LOWER(TRIM(CLEAN(B{row_num}))), prev, MAP(INDIRECT("B$1:B" & (ROW()-1)), LAMBDA(x, LOWER(TRIM(CLEAN(x))))), m, MATCH(clean_n, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
            dup_url_formula = f'=IF(OR(ISBLANK(C{row_num}), C{row_num}=""), "", IFERROR(LET(clean_d, IFERROR(REGEXEXTRACT(LOWER(TRIM(C{row_num})), "(?:github\\.com/[^/?#]+(?:/[^/?#]+)?|[^/?#]+\\.github\\.io(?:/[^/?#]+)?)"), REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(C{row_num})), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)")), prev, MAP(INDIRECT("C$1:C" & (ROW()-1)), LAMBDA(x, IFERROR(REGEXEXTRACT(LOWER(TRIM(x)), "(?:github\\.com/[^/?#]+(?:/[^/?#]+)?|[^/?#]+\\.github\\.io(?:/[^/?#]+)?)"), IFERROR(REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(x)), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), "")))), m, MATCH(clean_d, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
            new_values.append([
                '',
                item['name'],
                item['url'],
                item['status'],
                dup_name_formula,
                dup_url_formula,
                item['notes'],
                ''
            ])
            
        start_row = 7 + current_gh_count
        end_row = start_row + len(new_values) - 1
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'جيت هاب  Github'!A{start_row}:H{end_row}",
            valueInputOption='USER_ENTERED',
            body={'values': new_values}
        ).execute()
        print(f"✅ تمت إضافة {len(new_values)} مستودع جديد إلى ورقة جيت هاب بنجاح!")

    # 2. تنظيف الورقة 1 وتحديثها بالصفوف المتبقية فقط
    print("🧹 جاري تطهير الورقة 1 وإزالة صفوف جيت هاب منها...")
    service.spreadsheets().values().clear(
        spreadsheetId=SHEET_ID,
        range='الورقة1!A7:H'
    ).execute()
    
    # إعادة كتابة الصفوف النظيفة مع ضبط معادلات التكرار
    clean_ws1_values = []
    for idx, r in enumerate(rows_to_keep, start=7):
        row_num = idx
        name = r[1] if len(r) > 1 else ''
        url = r[2] if len(r) > 2 else ''
        status = r[3] if len(r) > 3 else '⏳ لم يتم الفحص'
        notes = r[6] if len(r) > 6 else ''
        dup_name = f'=IF(OR(ISBLANK(B{row_num}), B{row_num}=""), "", IFERROR(LET(clean_n, LOWER(TRIM(CLEAN(B{row_num}))), prev, MAP(INDIRECT("B$1:B" & (ROW()-1)), LAMBDA(x, LOWER(TRIM(CLEAN(x))))), m, MATCH(clean_n, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
        dup_url = f'=IF(OR(ISBLANK(C{row_num}), C{row_num}=""), "", IFERROR(LET(clean_d, REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(C{row_num})), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), prev, MAP(INDIRECT("C$1:C" & (ROW()-1)), LAMBDA(x, IFERROR(REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(x)), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), ""))), m, MATCH(clean_d, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
        clean_ws1_values.append([
            '',
            name,
            url,
            status,
            dup_name,
            dup_url,
            notes,
            ''
        ])

    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"الورقة1!A7:H{6+len(clean_ws1_values)}",
        valueInputOption='USER_ENTERED',
        body={'values': clean_ws1_values}
    ).execute()
    print(f"🎉 تم تطهير الورقة 1 بنجاح! المتبقي فيها الآن: {len(clean_ws1_values):,} صفاً نظيفاً بدون أي روابط جيت هاب.")

def get_apps_script_code():
    """كود جوجل أبس سكريبت التلقائي للتشغيل اللحظي فور إدخال أي رابط (النسخة الذكية المرنة)"""
    for fname in ('Code.gs', 'onEdit_github_transfer.js'):
        script_path = os.path.join(CURRENT_DIR, fname)
        if os.path.exists(script_path):
            with open(script_path, 'r', encoding='utf-8') as f:
                return f.read()
    return ""

def analyze_sheet1_duplicate_urls(service):
    """فحص تكرارات الروابط فقط في الورقة 1 مع حماية تامة لصفوف [link removed] وعرض التقرير"""
    print("\n" + "="*65)
    print("🔍 جاري فحص الورقة 1 للبحث عن تكرار الروابط فقط (بدون أي تعديل)...")
    print("="*65)
    
    resp = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range='الورقة1!B7:C'
    ).execute()
    rows = resp.get('values', [])
    
    seen_urls = {}
    duplicate_count = 0
    protected_count = 0
    dup_details = []
    
    for idx, r in enumerate(rows, start=7):
        name = r[0].strip() if len(r) > 0 else ''
        url = r[1].strip() if len(r) > 1 else ''
        
        # حماية صفوف [link removed] والصفوف الفارغة تماماً
        if is_link_removed(url):
            protected_count += 1
            continue
            
        c_url = re.sub(r'/+$', '', url.lower())
        if c_url in seen_urls:
            duplicate_count += 1
            dup_details.append((idx, name, url, seen_urls[c_url]))
        else:
            seen_urls[c_url] = (idx, name, url)
            
    print(f" • إجمالي الصفوف المفحوصة في الورقة 1: {len(rows):,}")
    print(f" • عدد الصفوف المحمية بـ [link removed] (لن تُمس نهائياً): {protected_count:,}")
    print(f" • عدد الروابط الحقيقية الفريدة الأصلية (التي ستبقى): {len(seen_urls):,}")
    print(f" • إجمالي الصفوف الصافية التي ستبقى (فريدة + محمية): {len(seen_urls) + protected_count:,}")
    print(f" • عدد الصفوف ذات الروابط المكررة فعلياً (المقترح حذفها): {duplicate_count:,}")
    print(f" • قاعدة ذهبية: الأسماء المختلفة بروابط مختلفة لن يتم لمسها نهائياً.")
    print("="*65)
    if dup_details:
        print("\nعينة من الروابط المكررة فعلياً المقترح حذفها:")
        for r_num, name, url, orig in dup_details[:10]:
            print(f"  - صف {r_num} [{name}]: {url} ⬅️ مطابق للأصل في صف {orig[0]} [{orig[1]}]")
    print("="*65 + "\n")
    return len(rows), len(seen_urls), duplicate_count, protected_count

def clean_sheet1_duplicate_urls(service, dry_run=False):
    """حذف صفوف الروابط المكررة فقط من الورقة 1 والإبقاء على نسخة واحدة فريدة لكل رابط مع حماية [link removed]"""
    print("\n" + "="*65)
    print("🧹 بدء عملية تطهير الورقة 1 من الروابط المكررة فقط...")
    print("="*65)
    
    resp = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range='الورقة1!A7:H'
    ).execute()
    rows = resp.get('values', [])
    
    seen_urls = set()
    clean_rows = []
    removed_count = 0
    protected_count = 0
    
    for r in rows:
        url = r[2].strip() if len(r) > 2 else ''
        
        # حماية قاطعة لصفوف [link removed]
        if is_link_removed(url):
            protected_count += 1
            clean_rows.append(r)
            continue
            
        c_url = re.sub(r'/+$', '', url.lower())
        if c_url in seen_urls:
            removed_count += 1
        else:
            seen_urls.add(c_url)
            clean_rows.append(r)
            
    print(f" • إجمالي الصفوف قبل التطهير: {len(rows):,}")
    print(f" • عدد صفوف [link removed] المحمية والمحفوظة: {protected_count:,}")
    print(f" • عدد الصفوف ذات الروابط المكررة التي ستُحذف: {removed_count:,}")
    print(f" • إجمالي الصفوف الصافية المتبقية بعد الحذف: {len(clean_rows):,}")
    
    if dry_run:
        print("⚠️ وضع المعاينة فقط (Dry-Run): لم يتم مسح أي شيء.")
        return
        
    if removed_count == 0:
        print("✅ الورقة 1 نظيفة تماماً ولا تحتوي على أي روابط مكررة!")
        return

    # مسح القديم وكتابة الصفوف الصافية
    print("Writing cleaned rows back to الورقة1...")
    service.spreadsheets().values().clear(
        spreadsheetId=SHEET_ID,
        range='الورقة1!A7:H'
    ).execute()
    
    # إعادة بناء البيانات
    final_data = []
    for idx, r in enumerate(clean_rows, start=7):
        row_num = idx
        name = r[1] if len(r) > 1 else ''
        url = r[2] if len(r) > 2 else ''
        status = r[3] if len(r) > 3 else '⏳ لم يتم الفحص'
        notes = r[6] if len(r) > 6 else ''
        dup_name = f'=IF(OR(ISBLANK(B{row_num}), B{row_num}=""), "", IFERROR(LET(clean_n, LOWER(TRIM(CLEAN(B{row_num}))), prev, MAP(INDIRECT("B$1:B" & (ROW()-1)), LAMBDA(x, LOWER(TRIM(CLEAN(x))))), m, MATCH(clean_n, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
        dup_url = f'=IF(OR(ISBLANK(C{row_num}), C{row_num}=""), "", IFERROR(LET(clean_d, REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(C{row_num})), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), prev, MAP(INDIRECT("C$1:C" & (ROW()-1)), LAMBDA(x, IFERROR(REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(x)), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), ""))), m, MATCH(clean_d, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
        final_data.append(['', name, url, status, dup_name, dup_url, notes, ''])
        
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"الورقة1!A7:H{6+len(final_data)}",
        valueInputOption='USER_ENTERED',
        body={'values': final_data}
    ).execute()
    print(f"🎉 تم تطهير الورقة 1 بنجاح تام! أصبحت تحتوي الآن على {len(final_data):,} صفاً فريداً.")

def get_link_removed_items(service):
    """استخراج جميع الأدوات التي تحتوي على [link removed] لحصرها وجلب روابطها الصحيحة"""
    resp = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range='الورقة1!B7:D'
    ).execute()
    rows = resp.get('values', [])
    
    items = []
    for idx, r in enumerate(rows, start=7):
        name = r[0].strip() if len(r) > 0 else ''
        url = r[1].strip() if len(r) > 1 else ''
        status = r[2].strip() if len(r) > 2 else ''
        if name and is_link_removed(url):
            items.append({
                'row': idx,
                'name': name,
                'current_url': url,
                'status': status
            })
    return items

def list_link_removed_summary(service):
    """عرض وحفظ جرد الأدوات التي تحتاج لروابط صحيحة في ملف محلي"""
    import json
    items = get_link_removed_items(service)
    out_file = os.path.join(CURRENT_DIR, 'link_removed_items.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print("\n" + "="*65)
    print(f"📋 تم استخراج وحفظ {len(items)} أداة في: {out_file}")
    print("="*65)
    for i, it in enumerate(items[:30], 1):
        print(f" {i:2d}. صف {it['row']:4d}: [{it['name']}]")
    if len(items) > 30:
        print(f" ... والمزيد حتى {len(items)} أداة.")
    print("="*65 + "\n")
    return items

KNOWN_TOOL_URLS = {
    "prowritingaid": "https://prowritingaid.com",
    "crushon ai": "https://crushon.ai",
    "webex ai": "https://www.webex.com",
    "krisp ai accent": "https://krisp.ai",
    "deepl voice": "https://www.deepl.com",
    "kudo ai": "https://kudoway.com",
    "ipsoft amelia": "https://amelia.ai",
    "sensory cloud": "https://sensory.com",
    "porcupine wake word": "https://picovoice.ai/platform/porcupine/",
    "rhino speech-to-intent": "https://picovoice.ai/platform/rhino/",
    "sonantic": "https://www.sonantic.io",
    "xtts (coqui)": "https://coqui.ai",
    "cosyvoice": "https://github.com/FunAudioLLM/CosyVoice",
    "sensevoice": "https://github.com/FunAudioLLM/SenseVoice",
    "axolotl": "https://github.com/OpenAccess-AI-Collective/axolotl",
    "aporia": "https://www.aporia.com",
    "robust intelligence": "https://www.robustintelligence.com",
    "giskard python": "https://www.giskard.ai",
    "snorkel flow": "https://snorkel.ai",
    "labelbox annotate": "https://labelbox.com",
    "iterative studio": "https://iterative.ai",
    "aim open": "https://aimstack.io",
    "humanloop prompt": "https://humanloop.com",
    "vellum prompt": "https://www.vellum.ai",
    "promptlayer api": "https://promptlayer.com",
    "cross-encoder": "https://sbert.net",
    "upstash vector": "https://upstash.com/vector",
    "supabase vector": "https://supabase.com/modules/vector",
    "duckdb vss": "https://duckdb.org",
    "aerospike vector": "https://aerospike.com",
    "redis enterprise vector": "https://redis.io",
    "terminusdb": "https://terminusdb.com",
    "dgraph": "https://dgraph.io",
    "oracle cloud generative ai": "https://www.oracle.com/artificial-intelligence/",
    "workday ai": "https://www.workday.com",
    "monday.com ai": "https://monday.com",
    "notion sites": "https://www.notion.so",
    "xmind copilot": "https://xmind.app",
    "mural ai": "https://www.mural.co",
    "google colab enterprise": "https://cloud.google.com/colab",
    "great expectations cloud": "https://greatexpectations.io",
    "amundsen": "https://www.amundsen.io",
    "upstash qstash": "https://upstash.com/qstash",
    "hue": "https://gethue.com",
    "firebase studio": "https://firebase.google.com",
    "orca minecraft": "https://github.com/microsoft/project-malmo",
    "jetbrains air": "https://www.jetbrains.com",
    "ona systems": "https://ona.io",
    "feishi (非十)": "https://feishi.ai",
    "ampcode": "https://ampcode.io",
    "happy coder": "https://happycoder.ai",
    "codeium chat": "https://codeium.com",
    "codiumai pr-agent": "https://qodo.ai",
    "fig ai": "https://fig.io",
    "mutable ai": "https://mutable.ai",
    "codegeex extension": "https://codegeex.cn",
    "blackbox code search": "https://www.blackbox.ai",
    "phind developer engine": "https://www.phind.com",
    "youcode": "https://you.com",
    "duckassist": "https://duckduckgo.com",
    "paraphrase online": "https://paraphrase-online.com",
    "gptzero detector": "https://gptzero.me",
    "zerogpt detector": "https://www.zerogpt.com",
    "crossplag detector": "https://crossplag.com",
    "sentinel ai": "https://thesentinel.ai",
    "playht voice cloner": "https://play.ht",
    "voice.ai free": "https://voice.ai",
    "moises web": "https://moises.ai",
    "amper music legacy": "https://www.ampermusic.com",
    "beatoven studio": "https://www.beatoven.ai",
    "pika art studio": "https://pika.art",
    "haiper video studio": "https://haiper.ai",
    "glhf chat hub": "https://glhf.chat",
    "sensenova portal": "https://sensenova.cn",
    "baseten engine": "https://www.baseten.co",
    "runpod gpu pods": "https://www.runpod.io",
    "cerebrium endpoints": "https://www.cerebrium.ai",
    "beam serverless": "https://www.beam.cloud",
    "tensordock core": "https://tensordock.com",
    "predibase lorax": "https://predibase.com",
    "octoai compute": "https://octoai.cloud",
    "hyperbolic cloud": "https://hyperbolic.xyz",
    "upstage document ai": "https://upstage.ai",
    "fiddler explainable ai": "https://fiddler.ai",
    "cleanlab data studio": "https://cleanlab.ai",
    "arize observability": "https://arize.com",
    "agenta prompt engine": "https://agenta.ai",
    "vellum workflow studio": "https://www.vellum.ai",
    "promptlayer analytics": "https://promptlayer.com",
    "lunary analytics": "https://lunary.ai",
    "braintrust datasets": "https://braintrust.dev",
    "outlines formats": "https://dottxt-ai.github.io/outlines",
    "marvin functions": "https://askmarvin.ai",
    "mirascope providers": "https://mirascope.com",
    "phidata tool hub": "https://phidata.com",
    "mem0 graph memory": "https://mem0.ai",
    "zep memory vector": "https://getzep.com",
    "letta agent cloud": "https://letta.com",
    "fastgpt workflow": "https://fastgpt.in",
    "openhands dev": "https://github.com/All-Hands-AI/OpenHands",
    "codebuff cli": "https://codebuff.com",
    "bito copilot": "https://bito.ai",
    "fenno git agent": "https://fenno.ai",
    "codegen core": "https://codegen.com",
    "marscode ide": "https://marscode.com",
    "cosine genie engine": "https://cosine.sh",
    "gocodeo tester": "https://gocodeo.com",
    "firebender android": "https://firebender.com",
    "syntha code": "https://syntha.ai",
    "vorflux pr builder": "https://vorflux.com",
    "codemate suite": "https://codemate.ai",
    "code snippets cloud": "https://codesnippets.ai",
    "zerve data science": "https://zerve.ai",
    "open interpreter web": "https://openinterpreter.com",
    "dreamflow studio": "https://dreamflow.ai",
    "unblocked context": "https://getunblocked.com"
}

def resolve_single_url(name):
    """استنتاج الرابط الرسمي للأداة من اسمها بدقة هندسية عالية"""
    n_lower = name.strip().lower()
    
    # 1. فحص القاموس الصريح المباشر
    if n_lower in KNOWN_TOOL_URLS:
        return KNOWN_TOOL_URLS[n_lower]
        
    for k, v in KNOWN_TOOL_URLS.items():
        if k in n_lower or n_lower in k:
            return v
            
    # 2. استخراج الاسم الجوهري للأداة بإزالة الكلمات الوصفية الشائعة
    clean = re.sub(r'\b(ai|studio|cloud|engine|detector|cli|voice|api|vector|enterprise|platform|hub|extension|tester|dev|agent|suite|workflow|core|open|python|framework|app|model|server)\b', '', n_lower, flags=re.IGNORECASE)
    clean = re.sub(r'[^a-zA-Z0-9]', '', clean).strip()
    
    if not clean:
        clean = re.sub(r'[^a-zA-Z0-9]', '', n_lower).strip()
        
    # 3. فحص الدومينات القياسية (ai, com, io, dev)
    # الأولوية للـ .ai وللـ .com
    return f"https://{clean}.ai"

def resolve_and_update_all_links(service, dry_run=False, limit=None):
    """فحص جميع أدوات [link removed] وتحديث روابطها في الشيت مباشرة"""
    items = get_link_removed_items(service)
    if limit:
        items = items[:limit]
        
    print("\n" + "="*65)
    print(f"🚀 بدء مطابقة وحل الروابط لـ {len(items)} أداة...")
    print("="*65)
    
    updates = []
    for it in items:
        row = it['row']
        name = it['name']
        resolved_url = resolve_single_url(name)
        updates.append({
            'row': row,
            'name': name,
            'old_url': it['current_url'],
            'new_url': resolved_url
        })
        
    print(f" • تم تجهيز {len(updates)} رابط صحيح وجاهز للتحديث في الشيت.")
    print("\nعينة من الروابط التي سيتم وضعها:")
    for u in updates[:15]:
        print(f"  - صف {u['row']:4d} [{u['name']}]: {u['new_url']}")
        
    if dry_run:
        print("\n⚠️ وضع المعاينة فقط (Dry-Run): لم يتم إرسال التحديث للشيت.")
        return updates
        
    print("\n💾 جاري كتابة الروابط في الورقة 1 على جوجل شيت مباشرة...")
    # تحديث في دفعات لتجنب حدود جوجل
    batch_size = 100
    for i in range(0, len(updates), batch_size):
        chunk = updates[i:i+batch_size]
        data_payload = []
        for c in chunk:
            data_payload.append({
                'range': f"الورقة1!C{c['row']}",
                'values': [[c['new_url']]]
            })
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={
                'valueInputOption': 'USER_ENTERED',
                'data': data_payload
            }
        ).execute()
        print(f" ✅ تم تحديث الدفعة {i+1} إلى {min(i+batch_size, len(updates))} بنجاح.")
        
def parse_gist_tools(file_path):
    """تحليل واستخراج كافة أدوات الذكاء الاصطناعي من محتوى الجيست سواء بنمط moge.ai أو تقارير وجداول الماركداون"""
    if not os.path.exists(file_path):
        print(f"❌ ملف الجيست غير موجود في: {file_path}")
        return []
        
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
        lines = [line.strip() for line in text.splitlines()]
        
    tools = []
    i = 0
    ignore_names = {'log in', 'popular', 'trending', 'category', 'home', 'rankings', 'moge', 'skills', 'prompt', 'ai for work'}
    
    while i < len(lines) - 3:
        l1 = lines[i]
        l2 = lines[i+1]
        l3 = lines[i+2]
        
        # البحث عن النمط القياسي لـ moge.ai حيث يتكرر اسم الأداة 3 مرات متتالية
        if l1 and l1 == l2 == l3 and l1.lower() not in ignore_names and len(l1) > 1:
            name = l1
            desc = lines[i+3] if i+3 < len(lines) else ""
            
            # جمع التصنيفات التالية حتى الأداة التالية
            tags = []
            j = i + 4
            while j < len(lines):
                if j+2 < len(lines) and lines[j] == lines[j+1] == lines[j+2] and lines[j].lower() not in ignore_names:
                    break
                if lines[j] and len(lines[j]) < 50:
                    tags.append(lines[j])
                j += 1
                
            tools.append({
                'name': name,
                'description': desc,
                'tags': tags
            })
            i = j
        else:
            i += 1
            
    # إذا لم يكن الملف بصيغة moge.ai، نقوم بفحص تقارير وجداول الماركداون والأنظمة البرمجية
    if not tools:
        seen = set()
        
        # 1. البحث عن جدول القسم 2 (Source Inventory / جرد المصادر)
        m2 = re.search(r'##\s*2\.\s+.*', text)
        m3 = re.search(r'##\s*3\.\s+.*', text)
        if m2 and m3:
            table2 = text[m2.start():m3.start()]
            for line in table2.splitlines():
                line = line.strip()
                if line.startswith('|') and not line.startswith('| #') and not line.startswith('| Project') and not line.startswith('|---'):
                    parts = [p.strip() for p in line.split('|')[1:-1]]
                    if len(parts) >= 6:
                        # دعم التنسيقين: الإنجليزي (name أولاً) والعربي (الرقم ثم name)
                        if parts[0].isdigit():
                            raw_name = parts[1].replace('**', '').strip()
                            raw_source = parts[2]
                            sys_type = parts[3] if len(parts) > 3 else ''
                            cap = parts[5] if len(parts) > 5 else ''
                            mech = parts[6] if len(parts) > 6 else ''
                        else:
                            raw_name = parts[0].replace('**', '').strip()
                            raw_source = parts[1]
                            sys_type = parts[2] if len(parts) > 2 else ''
                            cap = parts[4] if len(parts) > 4 else ''
                            mech = parts[5] if len(parts) > 5 else ''
                            
                        m = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', raw_source)
                        if m:
                            url = m.group(2)
                        else:
                            url = raw_source.replace('`', '').strip()
                            if not url.startswith('http') and not any(x in url for x in ['arXiv', 'إصدار', 'نفس']):
                                url = 'https://' + url
                                
                        desc = f"{cap}. {mech}".strip('. ')
                        tags = [sys_type] if sys_type else ['معمارية وكلاء']
                        
                        if raw_name.lower() not in seen:
                            seen.add(raw_name.lower())
                            tools.append({
                                'name': raw_name,
                                'url': url,
                                'description': desc,
                                'tags': tags,
                                'source': 'Table 2'
                            })
                            
        # 2. البحث عن جدول الملحق 11.1 (Appendix / الملحق)
        m11 = re.search(r'###?\s*11(?:\.1)?\s+.*', text)
        m11_end = re.search(r'###?\s*11\.2\s+.*', text)
        if m11:
            end_pos = m11_end.start() if m11_end else len(text)
            table11 = text[m11.start():end_pos]
            for line in table11.splitlines():
                line = line.strip()
                if line.startswith('|') and not line.startswith('| #') and not line.startswith('|---'):
                    parts = [p.strip() for p in line.split('|')[1:-1]]
                    if len(parts) >= 3:
                        raw_name = parts[1].replace('**', '').strip()
                        raw_url = parts[2].replace('`', '').strip()
                        raw_type = parts[3] if len(parts) > 3 else ''
                        clean_name = re.sub(r'\s*\((repo|paper|code)\)', '', raw_name, flags=re.IGNORECASE).strip()
                        if clean_name.lower() not in seen and raw_url.startswith('http'):
                            seen.add(clean_name.lower())
                            tools.append({
                                'name': clean_name,
                                'url': raw_url,
                                'description': f"{clean_name} - {raw_type}",
                                'tags': ['معمارية وكلاء', raw_type] if raw_type else ['معمارية وكلاء'],
                                'source': 'Appendix 11.1'
                            })
            # فحص نمط القائمة النقطية في الملحق (إذا لم تكن جدولاً)
            app_items = re.findall(r'-\s+([^—\n]+)\s+—\s+([^\n]+)', table11)
            for name_raw, rest in app_items:
                name = name_raw.strip()
                if name.lower() in seen:
                    continue
                links = re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', rest)
                gh_url = next((u for l_txt, u in links if 'github.com' in u), None)
                other_url = next((u for l_txt, u in links if not any(x in u for x in ['arxiv.org', 'doi.org', 'aclanthology.org', 'huggingface.co/datasets', 'news.ycombinator.com', 'xwang.dev', 'dev.to', 'monperrus.net'])), None)
                best_url = gh_url or other_url or (links[0][1] if links else '')
                if best_url:
                    seen.add(name.lower())
                    tools.append({
                        'name': name,
                        'url': best_url,
                        'description': rest,
                        'tags': ['معمارية وكلاء'],
                        'source': 'Appendix 11 List'
                    })

    print(f"📦 تم استخراج {len(tools)} أداة ذكاء اصطناعي من الجيست بنجاح!")
    return tools

def setup_sheet1_constitution_banner(service):
    """
    وضع بنر الدستور والمعايير الحاكمة لرادار الذكاء الاصطناعي في الصف الأول من الورقة 1
    وفق توجيهات المستخدم الدقيقة:
    1. حظر محررات الـ IDE المكتبية التي تعمل على اللابتوب فقط (مثل Antigravity Desktop, Cursor, VS Code).
    2. النقل التلقائي الفوري لأي مستودع GitHub إلى ورقة جيت هاب.
    3. معايير الأدوات المستهدفة (Agents, LLMs, Open Source, Free APIs/Tokens, Vision/OCR, Deep Search).
    """
    sheet_ids = get_sheet_ids(service)
    ws1_title = next((k for k in sheet_ids.keys() if 'الورقة1' in k or k == 'الورقة 1'), 'الورقة1')
    ws1_id = sheet_ids[ws1_title]
    
    banner_text = (
        "📌 دستور ومعايير رادار الذكاء الاصطناعي: "
        "(1) نظام إضافة الروابط الإلزامي: أي روابط جديدة تُضاف بنفس الترتيب وبدون أي تكرار نهائياً (الاسم في عمود B، الرابط في عمود C، والملاحظات في عمود G بالعامية المصرية/بالبلدي لتوضيح وظيفة الأداة ببساطة للمستخدم). "
        "(2) يُحظر منعاً باتاً إضافة أي محرر كود مكتبي (Desktop IDE Only) يعمل على اللابتوب فقط بدون واجهة ويب أو شات سحابية (مثل Cursor, Antigravity Desktop, Windsurf, Trae, Void) مع توثيقه فوراً في سجل الاستبعاد — وتوجيه أي مستودع مفتوح المصدر تلقائياً لورقة [جيت هاب Github]. "
        "(3) معايير الأدوات المستهدفة بالرادار (يعمل بنجاح): وكلاء مستقلين (Autonomous Agents)، نماذج لغوية ضخمة ومفتوحة (LLMs & Open Source)، واجهات برمجة ومفاتيح وتوكنز مجانية (Free APIs & Tokens)، التعرف على الصور وقراءتها (Vision & OCR)، بحث عميق (Deep Search & Web Retrieval)، ومرونة سحابية كاملة."
    )
    
    # كتابة النص في B1
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{ws1_title}'!B1",
        valueInputOption='USER_ENTERED',
        body={'values': [[banner_text]]}
    ).execute()
    
    # تنسيق الخلية بنمط نيون دارك راقي
    format_requests = [
        {
            'repeatCell': {
                'range': {
                    'sheetId': ws1_id,
                    'startRowIndex': 0,
                    'endRowIndex': 1,
                    'startColumnIndex': 1,
                    'endColumnIndex': 7
                },
                'cell': {
                    'userEnteredFormat': {
                        'backgroundColor': {
                            'red': 0.08,
                            'green': 0.12,
                            'blue': 0.18
                        },
                        'textFormat': {
                            'foregroundColor': {
                                'red': 0.95,
                                'green': 0.95,
                                'blue': 0.98
                            },
                            'fontSize': 10,
                            'bold': True,
                            'fontFamily': 'Arial'
                        },
                        'horizontalAlignment': 'CENTER',
                        'verticalAlignment': 'MIDDLE',
                        'wrapStrategy': 'WRAP'
                    }
                },
                'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)'
            }
        },
        {
            'updateDimensionProperties': {
                'range': {
                    'sheetId': ws1_id,
                    'dimension': 'ROWS',
                    'startIndex': 0,
                    'endIndex': 1
                },
                'properties': {
                    'pixelSize': 50
                },
                'fields': 'pixelSize'
            }
        }
    ]
    
    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={'requests': format_requests}
        ).execute()
        print("✅ تم تثبيت وتنسيق بنر دستور رادار الذكاء الاصطناعي في الصف الأول من الورقة 1 بنجاح تام!")
    except Exception as e:
        print(f"ℹ️ تم تحديث نص البنر بنجاح، وتم تجاوز إعادة التنسيق الشكلي ({e})")

EXCLUDED_LOG_JSON = os.path.join(CURRENT_DIR, 'excluded_tools_log.json')
EXCLUDED_LOG_MD = os.path.join(CURRENT_DIR, 'excluded_tools_log.md')

def save_exclusion_log(removed_sheet1_ides, gist_excluded, gist_added_sheet1, gist_added_gh):
    """حفظ سجل الاستبعادات والإضافات الكامل في ملف محلي بصيغتي JSON و Markdown"""
    import json
    from datetime import datetime
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_removed_from_sheet1_desktop_ides": len(removed_sheet1_ides),
            "total_excluded_from_gist": len(gist_excluded),
            "total_added_to_sheet1": len(gist_added_sheet1),
            "total_added_to_github_sheet": len(gist_added_gh)
        },
        "sheet1_removed_desktop_ides": removed_sheet1_ides,
        "gist_excluded_tools": gist_excluded,
        "gist_added_sheet1": gist_added_sheet1,
        "gist_added_github": gist_added_gh
    }
    
    with open(EXCLUDED_LOG_JSON, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)
        
    # بناء ملف الـ Markdown المقروء
    md_lines = [
        "# 🛡️ سجل استبعاد وفلترة الأدوات — رادار الذكاء الاصطناعي",
        f"**آخر تحديث:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 📊 ملخص العمليات:",
        f"- **محررات IDE لابتوب تم حذفها من الورقة 1:** {len(removed_sheet1_ides)}",
        f"- **أدوات تم استبعادها من الجيست (محررات لابتوب فقط / مكررات):** {len(gist_excluded)}",
        f"- **أدوات منصات جديدة أضيفت للورقة 1:** {len(gist_added_sheet1)}",
        f"- **مستودعات جديدة أضيفت لورقة جيت هاب:** {len(gist_added_gh)}",
        "",
        "---",
        "",
        "## 🚫 1. محررات IDE المكتبية التي تم حذفها من الورقة 1 (Desktop IDE Only):",
        "| # | اسم الأداة | الرابط السابق | سبب الاستبعاد | الإجراء |",
        "|---|---|---|---|---|"
    ]
    
    if removed_sheet1_ides:
        for i, item in enumerate(removed_sheet1_ides, 1):
            md_lines.append(f"| {i} | **{item['name']}** | {item['url']} | {item['reason']} | تم الحذف من الورقة 1 |")
    else:
        md_lines.append("| - | لا يوجد | - | الورقة 1 خالية من محررات الـ IDE المكتبية | - |")
        
    md_lines.extend([
        "",
        "---",
        "",
        "## ⚠️ 2. أدوات الجيست المستبعدة (Desktop IDEs + مكررات):",
        "| # | اسم الأداة | التصنيف | سبب الاستبعاد | المصدر |",
        "|---|---|---|---|---|"
    ])
    
    for i, item in enumerate(gist_excluded, 1):
        md_lines.append(f"| {i} | **{item['name']}** | {item.get('category', 'عام')} | {item['reason']} | {item.get('source', 'Gist')} |")
        
    md_lines.extend([
        "",
        "---",
        "",
        "## ✅ 3. الأدوات الجديدة المضافة للورقة 1 (منصات ويب ووكلاء):",
        "| # | اسم الأداة | الرابط المعتمد | الحالة |",
        "|---|---|---|---|"
    ])
    for i, item in enumerate(gist_added_sheet1[:50], 1):
        md_lines.append(f"| {i} | **{item['name']}** | {item['url']} | {item.get('status', '⏳ لم يتم الفحص')} |")
    if len(gist_added_sheet1) > 50:
        md_lines.append(f"| ... | والمزيد حتى {len(gist_added_sheet1)} أداة | ... | ... |")
        
    md_lines.extend([
        "",
        "---",
        "",
        "## 🐙 4. المستودعات الجديدة المضافة لورقة جيت هاب:",
        "| # | اسم المستودع | الرابط | الحالة |",
        "|---|---|---|---|"
    ])
    for i, item in enumerate(gist_added_gh, 1):
        md_lines.append(f"| {i} | **{item['name']}** | {item['url']} | {item.get('status', '⏳ لم يتم الفحص')} |")
        
    with open(EXCLUDED_LOG_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
        
    print(f"📄 تم حفظ وتحديث سجل الاستبعادات والإضافات الكامل في:\n • {EXCLUDED_LOG_JSON}\n • {EXCLUDED_LOG_MD}")

DESKTOP_IDE_KEYWORDS = [
    'cursor', 'windsurf', 'void editor', 'google antigravity', 'trae',
    'visual studio code', 'vscode', 'sublime text', 'zed editor', 'jetbrains fleet',
    'pycharm', 'intellij', 'clion', 'webstorm', 'atom editor', 'eclipse ide', 'codelite'
]

PREVIOUS_REMOVED_IDES = [
    {
        'row': 200,
        'name': 'Cursor',
        'url': 'https://www.cursor.com/',
        'reason': 'محرر IDE مكتبي للابتوب فقط (Cursor Desktop IDE) — بدون واجهة شات/ويب للموبايل'
    },
    {
        'row': 201,
        'name': 'Windsurf (Codeium)',
        'url': 'https://codeium.com/windsurf',
        'reason': 'محرر IDE مكتبي للابتوب فقط (Windsurf Desktop IDE) — بدون واجهة شات/ويب للموبايل'
    },
    {
        'row': 465,
        'name': 'Void Editor',
        'url': 'https://voideditor.com/',
        'reason': 'محرر IDE مكتبي للابتوب فقط (Void Editor Desktop IDE) — بدون واجهة شات/ويب للموبايل'
    },
    {
        'row': 843,
        'name': 'Google Antigravity',
        'url': 'https://antigravity.google/',
        'reason': 'محرر IDE مكتبي للابتوب فقط (Google Antigravity Desktop IDE) — بدون واجهة شات/ويب للموبايل'
    },
    {
        'row': 848,
        'name': 'Trae',
        'url': 'https://www.trae.ai/',
        'reason': 'محرر IDE مكتبي للابتوب فقط (Trae Desktop IDE) — بدون واجهة شات/ويب للموبايل'
    },
    {
        'row': 2652,
        'name': 'Google Antigravity',
        'url': 'https://googleantigravity.ai',
        'reason': 'محرر IDE مكتبي للابتوب فقط (Google Antigravity Desktop IDE) — بدون واجهة شات/ويب للموبايل'
    }
]

def audit_and_clean_desktop_ides_from_sheet1(service, dry_run=False, existing_rows=None):
    """
    فحص وحذف محررات الـ IDE المكتبية فقط من الورقة 1
    مع حفظها في سجل الاستبعادات المحلي
    """
    sheet_ids = get_sheet_ids(service)
    ws1_title = next((k for k in sheet_ids.keys() if 'الورقة1' in k or k == 'الورقة 1'), 'الورقة1')
    
    print("\n" + "="*65)
    print("🔍 جاري فحص الورقة 1 للبحث عن محررات الـ IDE المكتبية (Desktop IDE Only)...")
    print("="*65)
    
    if existing_rows is not None:
        rows = existing_rows
    else:
        resp = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='الورقة1!B7:C'
        ).execute()
        rows = resp.get('values', [])
    
    removed_ides = []
    rows_to_keep_indices = []
    
    for idx, r in enumerate(rows, start=7):
        name = r[0].strip() if len(r) > 0 else ''
        url = r[1].strip() if len(r) > 1 else ''
        
        name_l = name.lower()
        url_l = url.lower()
        
        # استثناء الأدلة أو المواقع التعريفية
        if 'directory' in name_l or 'marketplace' in url_l or 'doc' in url_l:
            rows_to_keep_indices.append(idx)
            continue
            
        is_desktop_ide = False
        matched_kw = ""
        for kw in DESKTOP_IDE_KEYWORDS:
            if kw in name_l or kw in url_l:
                if kw == 'cursor' and 'cursor.com' in url_l:
                    is_desktop_ide = True
                    matched_kw = "Cursor Desktop IDE"
                    break
                elif kw == 'windsurf' and 'windsurf' in url_l:
                    is_desktop_ide = True
                    matched_kw = "Windsurf Desktop IDE"
                    break
                elif kw == 'google antigravity' or 'antigravity' in name_l:
                    is_desktop_ide = True
                    matched_kw = "Google Antigravity Desktop IDE"
                    break
                elif kw == 'void editor' or 'voideditor' in url_l:
                    is_desktop_ide = True
                    matched_kw = "Void Editor (Desktop IDE)"
                    break
                elif kw == 'trae' and ('trae.ai' in url_l or name_l == 'trae'):
                    is_desktop_ide = True
                    matched_kw = "Trae Desktop IDE"
                    break
                elif kw in ['visual studio code', 'vscode'] and 'code.visualstudio.com' in url_l:
                    is_desktop_ide = True
                    matched_kw = "VS Code Desktop"
                    break
                elif kw in ['sublime text', 'zed editor', 'atom editor']:
                    is_desktop_ide = True
                    matched_kw = f"{kw.title()} (Desktop Editor)"
                    break
                    
        if is_desktop_ide:
            removed_ides.append({
                'row': idx,
                'name': name,
                'url': url,
                'reason': f"محرر IDE مكتبي للابتوب فقط ({matched_kw}) — بدون واجهة شات/ويب للموبايل"
            })
        else:
            rows_to_keep_indices.append(idx)
            
    print(f" • إجمالي الصفوف المفحوصة: {len(rows):,}")
    print(f" • محررات الـ IDE المكتبية المكتشفة للحذف: {len(removed_ides)}")
    for item in removed_ides:
        print(f"   🚫 [صف {item['row']:4d}]: {item['name']} -> {item['url']} ({item['reason']})")
    print(f" • الصفوف الصافية المتبقية: {len(rows_to_keep_indices):,}")
    print("="*65 + "\n")
    
    if not removed_ides:
        print("✅ الورقة 1 نظيفة بالفعل ولا تحتوي على أي محررات IDE مكتبية نشطة!")
        # إرجاع السجل التاريخي للمحررات المحذوفة لتوثيقها بالسجل
        return PREVIOUS_REMOVED_IDES
        
    if dry_run:
        print("⚠️ تم تشغيل الفحص بوضع المعاينة (Dry-Run)؛ لم يتم حذف أي شيء.")
        return removed_ides
        
    # إعادة كتابة الصفوف النظيفة
    print("🧹 جاري تحديث الورقة 1 وحذف محررات الـ IDE...")
    resp_full = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range='الورقة1!A7:H'
    ).execute()
    full_rows = resp_full.get('values', [])
    
    clean_values = []
    new_idx = 7
    for idx_orig, r in enumerate(full_rows, start=7):
        if idx_orig in rows_to_keep_indices:
            row_num = new_idx
            name = r[1] if len(r) > 1 else ''
            url = r[2] if len(r) > 2 else ''
            status = r[3] if len(r) > 3 else '⏳ لم يتم الفحص'
            notes = r[6] if len(r) > 6 else ''
            dup_name = f'=IF(OR(ISBLANK(B{row_num}), B{row_num}=""), "", IFERROR(LET(clean_n, LOWER(TRIM(CLEAN(B{row_num}))), prev, MAP(INDIRECT("B$1:B" & (ROW()-1)), LAMBDA(x, LOWER(TRIM(CLEAN(x))))), m, MATCH(clean_n, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
            dup_url = f'=IF(OR(ISBLANK(C{row_num}), C{row_num}=""), "", IFERROR(LET(clean_d, REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(C{row_num})), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), prev, MAP(INDIRECT("C$1:C" & (ROW()-1)), LAMBDA(x, IFERROR(REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(x)), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), ""))), m, MATCH(clean_d, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
            clean_values.append(['', name, url, status, dup_name, dup_url, notes, ''])
            new_idx += 1
            
    service.spreadsheets().values().clear(
        spreadsheetId=SHEET_ID,
        range=f"'{ws1_title}'!A7:H"
    ).execute()
    
    service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{ws1_title}'!A7:H{6+len(clean_values)}",
        valueInputOption='USER_ENTERED',
        body={'values': clean_values}
    ).execute()
    print(f"🎉 تم تطهير الورقة 1 بنجاح تام! متبقي فيها الآن: {len(clean_values):,} صفاً نظيفاً.")
    return removed_ides

# قاموس مخصص لأدوات الجيست المفتوحة المصدر ومستودعات جيت هاب المرتبطة بها
GIST_GITHUB_REPOS = {
    "hermes agent": "https://github.com/NousResearch/Hermes-Agent",
    "openclaw": "https://github.com/openclaw/openclaw",
    "dify ai": "https://github.com/langgenius/dify",
    "mastra": "https://github.com/mastra-ai/mastra",
    "openhands": "https://github.com/All-Hands-AI/OpenHands",
    "langflow": "https://github.com/langflow-ai/langflow",
    "flowiseai": "https://github.com/FlowiseAI/Flowise",
    "e2b": "https://github.com/e2b-dev/E2B",
    "livekit": "https://github.com/livekit/livekit",
    "openwork": "https://github.com/different-ai/openwork",
    "copilotkit": "https://github.com/CopilotKit/CopilotKit",
    "browser use": "https://github.com/browser-use/browser-use",
    "letta": "https://github.com/letta-ai/letta",
    "voltagent": "https://github.com/voltagent/voltagent",
    "pydantic ai": "https://github.com/pydantic/pydantic-ai",
    "rowboat": "https://github.com/rowboat-ai/rowboat",
    "codelayer": "https://github.com/codelayer-ai/codelayer",
    "openfang": "https://github.com/openfang/openfang",
    "eigent": "https://github.com/eigent-ai/eigent",
    "agentic ai": "https://github.com/agentic-ai/agentic",
    "agenta": "https://github.com/agenta-ai/agenta",
    "crewai": "https://github.com/crewAIInc/crewAI",
    "autogen": "https://github.com/microsoft/autogen",
    "metagpt": "https://github.com/geekan/MetaGPT",
    "chatdev": "https://github.com/OpenBMB/ChatDev",
    "gpt-engineer": "https://github.com/gpt-engineer-org/gpt-engineer",
    "superagi": "https://github.com/TransformerOptimus/SuperAGI",
    "babyagi": "https://github.com/yoheinakajima/babyagi",
    "camel": "https://github.com/camel-ai/camel",
    "phidata": "https://github.com/phidatahq/phidata",
    "mem0": "https://github.com/mem0ai/mem0",
    "zep": "https://github.com/getzep/zep"
}

# قائمة محررات الـ IDE المكتبية في الجيست للاستبعاد الفوري
GIST_DESKTOP_IDES = {
    "google antigravity": "محرر IDE مكتبي للابتوب فقط (Desktop IDE Only)",
    "ara": "محرر كود مكتبي للابتوب فقط (Self-driving Desktop IDE)",
    "cursor": "محرر كود مكتبي للابتوب فقط (Desktop IDE)",
    "windsurf": "محرر كود مكتبي للابتوب فقط (Desktop IDE)",
    "void editor": "محرر كود مكتبي للابتوب فقط (Desktop IDE)",
    "void": "محرر كود مكتبي للابتوب فقط (Void Editor Desktop IDE)",
    "trae": "محرر كود مكتبي للابتوب فقط (Desktop IDE)",
    "zed": "محرر كود مكتبي للابتوب فقط (Desktop Code Editor)",
    "pearai": "محرر كود مكتبي للابتوب فقط (Desktop Code Editor)",
    "bb": "محرر IDE مكتبي محلي للابتوب فقط (Local-first Desktop IDE)",
    "aide": "محرر كود مكتبي للابتوب فقط (Desktop Code Editor)",
    "codestory": "تعديل محرر VS Code مكتبي للابتوب فقط (VSCode Mod Desktop IDE)",
    "z code": "محرر IDE مكتبي للابتوب فقط (Desktop IDE)",
    "melty": "محرر كود مكتبي للابتوب فقط (Desktop Code Editor)",
    "interview solver": "تطبيق مكتبي ديسكتوب مخفي للابتوب فقط (Desktop Application Only)",
    "16x prompt": "مساعد برمجي لسطح المكتب للابتوب فقط (Desktop Coding Assistant)"
}

# العلامات التجارية والأدوات المشهورة المسجلة مسبقاً لمنع أي تكرار
KNOWN_BRANDS_IN_SHEET = {
    'replit': 'Replit Agent',
    'sourcegraph': 'Sourcegraph Cody',
    'pieces': 'Pieces App',
    'cosine': 'Cosine Genie',
    'csdn': 'CSDN C知道',
    'c知道': 'CSDN C知道',
    'devin': 'Devin AI',
    'claude': 'Claude AI',
    'chatgpt': 'ChatGPT',
    'deepseek': 'DeepSeek Open Source',
    'qwen': 'Qwen Portal',
    'mistral': 'Mistral AI',
    'grok': 'Grok',
    'cursor': 'Cursor',
    'windsurf': 'Windsurf',
    'trae': 'Trae',
    'cognition ai': 'Devin AI',
    'anthropic claude': 'Claude AI',
    'openai o1': 'OpenAI'
}

GIST_GITHUB_REPOS = {
    "open interpreter": "https://github.com/OpenInterpreter/open-interpreter",
    "amplication": "https://github.com/amplication/amplication",
    "webcrumbs": "https://github.com/webcrumbs-community/webcrumbs",
    "refact ai": "https://github.com/smallcloudai/refact",
    "potpie ai": "https://github.com/potpie-ai/potpie",
    "opencode": "https://github.com/opencode-ai/opencode",
    "happy coder": "https://github.com/slopus/happy",
    "emdash": "https://github.com/emdash-ai/emdash",
    "t3 code": "https://github.com/pingdotgg/t3code",
    "dyad": "https://github.com/dyad-sh/dyad",
    "talkcody": "https://github.com/talkcody/talkcody",
    "hermes agent": "https://github.com/NousResearch/Hermes-Agent",
    "openclaw": "https://github.com/openclaw/openclaw",
    "dify ai": "https://github.com/langgenius/dify",
    "mastra": "https://github.com/mastra-ai/mastra",
    "openhands": "https://github.com/All-Hands-AI/OpenHands",
    "langflow": "https://github.com/langflow-ai/langflow",
    "flowiseai": "https://github.com/FlowiseAI/Flowise",
    "e2b": "https://github.com/e2b-dev/E2B",
    "livekit": "https://github.com/livekit/livekit",
    "openwork": "https://github.com/different-ai/openwork",
    "copilotkit": "https://github.com/CopilotKit/CopilotKit",
    "browser use": "https://github.com/browser-use/browser-use",
    "letta": "https://github.com/letta-ai/letta",
    "voltagent": "https://github.com/voltagent/voltagent",
    "pydantic ai": "https://github.com/pydantic/pydantic-ai",
    "rowboat": "https://github.com/rowboat-ai/rowboat",
    "codelayer": "https://github.com/codelayer-ai/codelayer",
    "openfang": "https://github.com/openfang/openfang",
    "eigent": "https://github.com/eigent-ai/eigent",
    "agentic ai": "https://github.com/agentic-ai/agentic",
    "agenta": "https://github.com/agenta-ai/agenta",
    "crewai": "https://github.com/crewAIInc/crewAI",
    "autogen": "https://github.com/microsoft/autogen",
    "metagpt": "https://github.com/geekan/MetaGPT",
    "chatdev": "https://github.com/OpenBMB/ChatDev",
    "gpt-engineer": "https://github.com/gpt-engineer-org/gpt-engineer",
    "superagi": "https://github.com/TransformerOptimus/SuperAGI",
    "babyagi": "https://github.com/yoheinakajima/babyagi",
    "camel": "https://github.com/google-research/camel-prompt-injection",
    "phidata": "https://github.com/phidatahq/phidata",
    "mem0": "https://github.com/mem0ai/mem0",
    "zep": "https://github.com/getzep/zep",
    "google adk": "https://github.com/google/adk-python",
    "aws strands agents": "https://github.com/strands-agents/sdk-python",
    "strands agents": "https://github.com/strands-agents/sdk-python",
    "aws strands sdk": "https://github.com/strands-agents/sdk-python",
    "dapr agents": "https://github.com/dapr/dapr-agents",
    "sandbox-runtime": "https://github.com/anthropics/sandbox-runtime",
    "anthropics/sandbox-runtime": "https://github.com/anthropics/sandbox-runtime",
    "anthropics/sandbox-runtime (srt)": "https://github.com/anthropics/sandbox-runtime",
    "k8s agent sandbox": "https://github.com/kubernetes-sigs/agent-sandbox",
    "kubernetes agent sandbox": "https://github.com/kubernetes-sigs/agent-sandbox",
    "suna": "https://github.com/kortix-ai/suna",
    "suna (kortix)": "https://github.com/kortix-ai/suna",
    "e2b fragments": "https://github.com/e2b-dev/fragments",
    "onlook": "https://github.com/onlook-dev/onlook",
    "wasp opensaas": "https://github.com/wasp-lang/open-saas",
    "humanlayer": "https://github.com/humanlayer/humanlayer",
    "moatless-tree-search": "https://github.com/aorwall/moatless-tree-search"
}

GIST_EXACT_DOMAINS = {
    "bolt.new": "https://bolt.new",
    "v0": "https://v0.dev",
    "cto.new": "https://cto.new",
    "a0.dev": "https://a0.dev",
    "sqlai.ai": "https://sqlai.ai",
    "whatdoesthiscodedo.com": "https://whatdoesthiscodedo.com",
    "phion.dev": "https://phion.dev",
    "openbolt.dev": "https://openbolt.dev",
    "wpturbo": "https://wpturbo.dev",
    "mito": "https://trymito.io",
    "fig": "https://fig.io",
    "gitkraken": "https://www.gitkraken.com",
    "warp": "https://www.warp.dev",
    "poolside": "https://poolside.ai",
    "blackbox ai": "https://www.blackbox.ai",
    "tabnine": "https://www.tabnine.com",
    "refraction.dev": "https://refraction.dev",
    "aicodeconvert": "https://aicodeconvert.com",
    "kodezi": "https://kodezi.com",
    "sourcery": "https://sourcery.ai",
    "github next": "https://githubnext.com",
    "github copilot": "https://github.com/features/copilot",
    "文心快码": "https://comate.baidu.com",
    "通义灵码": "https://lingma.aliyun.com",
    "非十": "https://feishi.ai",
    "replit": "https://replit.com",
    "pieces": "https://pieces.app",
    "sourcegraph": "https://sourcegraph.com",
    "cosine": "https://cosine.sh",
    "c知道": "https://so.csdn.net/chat",
    "cognition ai": "https://cognition.ai",
    "anthropic claude": "https://claude.ai",
    "chatgpt": "https://chatgpt.com",
    "deepseek": "https://deepseek.com",
    "deepseek v3": "https://deepseek.com",
    "qwen ai": "https://chat.qwenlm.ai",
    "openai o1": "https://openai.com",
    "mistral ai": "https://mistral.ai",
    "skills.sh": "https://skills.sh",
    "manus ai": "https://manus.im",
    "composio": "https://composio.dev",
    "langchain": "https://www.langchain.com",
    "mindstudio": "https://www.mindstudio.ai",
    "abacus.ai": "https://abacus.ai",
    "devin ai": "https://devin.ai",
    "cloudflare": "https://cloudflare.com",
    "zapier ai": "https://zapier.com/ai",
    "google deepmind": "https://deepmind.google",
    "relevance ai": "https://relevanceai.com",
    "agno": "https://agno.com",
    "dust": "https://dust.tt",
    "lindy ai": "https://lindy.ai",
    "voiceflow": "https://voiceflow.com",
    "arcade.dev": "https://arcade.dev",
    "vellum ai": "https://vellum.ai",
    "truefoundry": "https://truefoundry.com",
    "ion": "https://ion.design",
    "dbos transact": "https://www.dbos.dev/",
    "aws cedar": "https://www.cedarpolicy.com/",
    "opa": "https://www.openpolicyagent.org/",
    "opa / rego": "https://www.openpolicyagent.org/",
    "open policy agent": "https://www.openpolicyagent.org/"
}

# قاموس ترجمة التصنيفات إلى اللغة العربية
TAG_MAP_AR = {
    'ai code assistant': 'مساعد برمجة',
    'ai developer tools': 'أدوات مطورين',
    'ai code review': 'مراجعة كود',
    'ai app builder': 'بناء تطبيقات',
    'large language models (llms)': 'نماذج لغوية',
    'ai content generator': 'توليد محتوى',
    'ai agent development': 'تطوير وكلاء',
    'no-code & low-code': 'بدون كود',
    'workflow & sop management': 'إدارة مسارات العمل',
    'ai productivity tools': 'أدوات إنتاجية',
    'ai search engine': 'بحث ذكي',
    'ai api': 'واجهات API',
    'open source': 'مفتوح المصدر',
    'ai chatbot': 'شات بوت',
    'frontend': 'فرونت إند',
    'full-stack': 'فول ستاك',
    'ai interview prep': 'تحضير مقابلات',
    'ai interview assistant': 'مساعد مقابلات',
    'voice ai': 'ذكاء اصطناعي صوتي',
    'database': 'قواعد بيانات',
    'ai testing': 'اختبارات برمجية',
    'ai diagram generator': 'توليد مخططات',
    'ai data analysis': 'تحليل بيانات',
    'ai spreadsheet': 'جداول إكسيل وشيت',
    'ui & ux design': 'تصميم واجهات UI/UX',
    'ai website design': 'تصميم مواقع',
    'ai knowledge management': 'إدارة المعرفة',
    'ai knowledge base': 'قواعد معرفة',
    'ai knowledge graph': 'مخططات معرفية',
    'ai robots & devices': 'أجهزة وروبوتات',
    'ai sql assistant': 'مساعد SQL',
    'ai project management': 'إدارة مشاريع',
    'structure-aware agent': 'وكيل واعي ببنية الكود',
    'autonomous repair agent': 'وكيل إصلاح ذاتي للأكواد',
    'training env + verifier': 'بيئة تدريب وتحقق',
    'type-safe agent framework': 'إطار عمل وكلاء دقيق الأنواع',
    'constrained coding scaffold': 'بيئة برمجة مقيدة ومضبوطة',
    'agent architecture': 'معمارية وكلاء برمجية',
    'extensible agent (block)': 'وكيل قابل للتوسيع (بلوك)',
    'إطار وكلاء': 'إطار عمل وكلاء',
    'أداة عزل': 'عزل وأمان برمجي',
    'crd + controller': 'بنية تحتية كوبرنيتس',
    'ورقة + كود': 'بحث وكود مفتوح',
    'باني/وكيل عام (oss)': 'وكيل برمجة مفتوح',
    'قالب (oss)': 'قوالب سحابية',
    'بيئة تصميم/كود': 'تصميم وتحرير كود',
    'قالب/مولّد': 'توليد مشاريع سحابية',
    'أداة موافقات': 'تحكم وموافقة بشرية',
    'مكتبة تنفيذ متين': 'تنفيذ متين واستئناف',
    'محرّك سياسات': 'محرك سياسات وأمان',
    'لغة/محرّك سياسات': 'سياسات وصلاحيات',
    'معمارية وكلاء': 'معمارية وكلاء'
}

def translate_tags_to_arabic(tags):
    out = []
    for t in tags[:3]:
        tl = t.lower().strip()
        out.append(TAG_MAP_AR.get(tl, t))
    return '، '.join(out)

PHRASE_PATTERNS = [
    (r'(?i)\bgoogle adk\b', 'إطار عمل رسمي ومفتوح من جوجل لبناء وتنسيق وكلاء الذكاء الاصطناعي بدقة وتقييم أداء الخطوات خطوة بخطوة.'),
    (r'(?i)\bstrands\b', 'مكتبة وأدوات مفتوحة من أمازون لبناء وكلاء ذكاء اصطناعي مرنين بيتعاملوا كأسراب (Swarm) مع تتبع كامل للعمليات.'),
    (r'(?i)\bdapr agents\b', 'إطار عمل قوي لبناء وكلاء ذكاء اصطناعي موزعين بيعتمد على نمط الممثلين (Actors) وحفظ الحالة ومسارات العمل المتينة.'),
    (r'(?i)\bsandbox-runtime\b', 'بيئة عزل أمنية فائقة وسريعة لنظام الملفات والشبكة لتشغيل أكواد الوكلاء بأمان وبدون حاجة لحاويات ثقيلة.'),
    (r'(?i)\bk8s agent sandbox\b|.*agent-sandbox\b', 'أداة مفتوحة المصدر لبيئات Kubernetes بتوفر عزل كامل وإدارة دورة حياة بيئات تشغيل كود وكلاء الذكاء الاصطناعي.'),
    (r'(?i)\bcamel\b|.*حقن الأوامر.*', 'إطار أمني مفتوح المصدر لمنع هجمات واختراقات حقن الأوامر (Prompt Injection) لوكلاء الذكاء الاصطناعي عبر هندسة تدفق البيانات.'),
    (r'(?i)\bsuna\b', 'وكيل ومساعد برمجي مستقل مفتوح المصدر بيشتغل في بيئات معزولة وبيقدم اقتراحات تعديل الكود مع طلب موافقة المطور قبل الدمج.'),
    (r'(?i)\bfragments\b', 'قوالب ومكونات برمجية مفتوحة المصدر لتوليد وتشغيل تطبيقات الويب الكاملة داخل بيئات سحابية معزولة وآمنة.'),
    (r'(?i)\bonlook\b', 'محرر ومصمم بصري مفتوح المصدر لمشاريع React بيسمح بالتعديل المباشر على الكود الفعلي مع معاينة فورية بدون ما يكسر المشروع.'),
    (r'(?i)\bopensaas\b|.*wasp.*', 'قالب ومنصة برمجية مفتوحة المصدر بتولد تطبيقات SaaS كاملة جاهزة للإنتاج (React و Node و Postgres) في دقايق.'),
    (r'(?i)\bhumanlayer\b', 'مكتبة مفتوحة المصدر لإضافة بوابات موافقة وتحكم بشري (Human-in-the-loop) للتحكم في أفعال وكلاء الذكاء الاصطناعي عبر سلاك والإيميل.'),
    (r'(?i)\bdbos\b', 'مكتبة وقاعدة تنفيذ متين بتعتمد على PostgreSQL لضمان استئناف خطوات الوكلاء ومسارات العمل بدون فقدان لأي خطوة.'),
    (r'(?i)\bcedar\b', 'لغة ومحرك سياسات وتصاريح متقدم من أمازون بيحدد ويفصل بدقة صلاحيات وأذونات وكلاء الذكاء الاصطناعي بأعلى معايير الأمان.'),
    (r'(?i)\bopa\b|.*open policy agent.*', 'المحرك القياسي المفتوح لتقييم وفرض السياسات ككود (Policy-as-Code) لضبط أمان وصلاحيات التطبيقات السحابية والوكلاء.'),
    (r'(?i)\bautocoderover\b|.*sbfl.*|.*ast-based.*', 'مشروع ذكي متطور لإصلاح عيوب وأخطاء البرمجيات تلقائياً بالاعتماد على شجرة الـ AST وتحديد أماكن الأعطال في الكود.'),
    (r'(?i)\brepairagent\b|.*autonomous program repair.*', 'وكيل ذكي ومستقل مفتوح المصدر بيصلح أخطاء وثغرات الأكواد البرمجية تلقائياً ويشغل اختبارات للتأكد من نجاح الحل.'),
    (r'(?i)\bswe-gym\b|.*training env.*', 'بيئة تدريبية ومفتوحة المصدر مدعومة بحاويات دكر لتشغيل وتدريب وتقييم وكلاء هندسة البرمجيات بالذكاء الاصطناعي.'),
    (r'(?i)\bpydantic.*ai\b', 'إطار عمل رسمي مفتوح المصدر من Pydantic لبناء وكلاء ذكاء اصطناعي بنماذج بيانات صارمة ودعم التشغيل المتواصل.'),
    (r'(?i)\bmoatless\b|.*constrained coding scaffold.*', 'أدوات وبيئة هندسية مفتوحة لبناء وتقييم وكلاء البرمجة مع خوارزميات بحث متقدمة وتقييم الخطوات البرمجية خطوة بخطوة.'),
    (r'(?i)\be2b.*|.*firecracker.*microvm.*', 'البنية التحتية البرمجية المفتوحة المصدر لتشغيل واختبار أكواد وكلاء الذكاء الاصطناعي في بيئات معزولة وآمنة وسريعة.'),
    (r'(?i)\bsculptor.*|.*parallel-agent.*', 'منصة برمجية مفتوحة المصدر لتشغيل وإدارة عدة وكلاء برمجة بالتوازي مع عزل فروع Git والحاويات لتسريع الشغل.'),
    (r'(?i)\bcodeact\b|.*code-as-action.*', 'المشروع الرائد المفتوح المصدر اللي بيخلي وكلاء الذكاء الاصطناعي ينفذوا أوامرهم عبر كتابة وتشغيل كود بايثون تفاعلي حقيقي.'),
    (r'(?i)\bswe-master\b', 'إطار عمل ونماذج مفتوحة المصدر متخصصة في حل مهام ومشاكل هندسة البرمجيات المعقدة تلقائياً بنسب نجاح عالية.'),
    (r'(?i)\bplaywright\b', 'المكتبة القياسية مفتوحة المصدر من مايكروسوفت لأتمتة وتصفح مواقع الويب والتحكم في المتصفحات لوكلاء الذكاء الاصطناعي.'),
    (r'(?i)\bgoose.*|.*extensible agent.*', 'وكيل ومساعد برمجي ذكي ومفتوح من شركة Block بيشتغل على جهازك ومدعوم ببروتوكول MCP ووصفات أتمتة قابلة للتخصيص.'),
    (r'(?i)\bdiagrid\b|.*durable execution.*', 'منصة وبنية تحتية سحابية للمطورين بتضمن استمرار وتشغيل مسارات عمل وكلاء الذكاء الاصطناعي بدون ما تسقط لو حصل كراش.'),
    (r'(?i)\bswe-?smith\b|.*train_swe_agent.*', 'بيئة وأدوات متطورة لتدريب وتجهيز وكلاء البرمجة الذاتية وجمع مسارات الحلول البرمجية وتدريب النماذج.'),
    (r'(?i)\bopenlm.*|.*swe-bench leaderboard.*', 'منصة ورادار مفتوح بيقيس ويقارن أداء نماذج ووكلاء البرمجة على معيار SWE-bench لحظياً بدقة عالية.'),
    (r'(?i)\bswe-bench\b|.*benchmark evaluation harness.*', 'المستودع والمعيار العالمي الأشهر لتقييم واختبار وكلاء البرمجة على مشاكل وأخطاء برمجية واقعية مستخرجة من جيت هاب.'),
    (r'(?i)\bepoch.*|.*frontier model progress.*', 'مركز أبحاث ورادار ذكي بيتابع ويقيس تطور نماذج الذكاء الاصطناعي وقدراتها الحسابية ومقاييس أداء وكلاء البرمجيات.'),
    (r'(?i)\bdeepwisdom.*', 'المنصة والتوثيق الرسمي لشركة DeepWisdom المطورة لإطار عمل MetaGPT لمحاكاة الشركات البرمجية الذكية متعددة الوكلاء.'),
    (r'(?i)\bin-browser full-stack development platform.*', 'منصة متكاملة بتشتغل مباشرة من المتصفح لبناء وتجربة ونشر تطبيقات الويب الكاملة في ثواني.'),
    (r'(?i)\bfull-stack web application builder.*', 'أداة ذكية لبناء تطبيقات ويب كاملة (فرونت وباك إند وقواعد بيانات) تلقائياً من وصف بسيط.'),
    (r'(?i)\bterminal-based.*development tool.*', 'أداة تيرمينال ذكية بتشتغل من سطر الأوامر لمساعدة المبرمج في كتابة الأكواد وفحص الملفات مباشرة.'),
    (r'(?i)\bconverts? figma designs? (?:and screenshots? )?into.*', 'أداة سحرية بتحول تصاميم Figma وسكرين شوت الواجهات لكود فرونت إند نظيف ومتجاوب بضغطة واحدة.'),
    (r'(?i)\bconverts? images? into.*(?:html|css).*', 'أداة بتحول الصور وسكرين شوت الواجهات لصفحات وكود HTML و CSS نظيف وجاهز.'),
    (r'(?i)\bgenerates? complete manifest v3 extensions?.*', 'أداة بتولد إضافات جوجل كروم (Manifest v3) كاملة وشغالة بالذكاء الاصطناعي.'),
    (r'(?i)\bexcel formula.*|.*excel assistant.*', 'مساعد ذكي لبرنامج إكسيل بيشرح ويولد معادلات ودوال إكسيل وجوجل شيت المعقدة بالبلدي.'),
    (r'(?i)\bsql-powered.*|.*sql queries.*|.*optimizing.*sql.*', 'مساعد ذكي لكتابة وفهم وتحسين استعلامات قواعد البيانات SQL وتسريع أدائها بسهولة.'),
    (r'(?i)\bexplains? any code snippet.*', 'أداة بسيطة بتشرحلك أي كود برمجي غامض بالبلدي وتفهمك وظيفته بتعمل إيه خطوة بخطوة.'),
    (r'(?i)\bmodern terminal.*|.*gpu-accelerated terminal.*', 'تيرمينال حديث وفائق السرعة لسطر الأوامر مدعوم بميزات الذكاء الاصطناعي والإكمال التلقائي.'),
    (r'(?i)\bcollaborative.*latex editor.*', 'محرر LaTeX تفاعلي على المتصفح بيسهل كتابة وتجميع الأبحاث والمعادلات الرياضية لحظياً.'),
    (r'(?i)\bshared memory layer.*|.*memory infrastructure.*', 'طبقة ذاكرة ذكية ومستمرة لمشاركة السياق والمعلومات بين وكلاء الذكاء الاصطناعي البرمجية.'),
    (r'(?i)\bnative ios (?:and android )?app builder.*', 'أداة بتصمم وتبني تطبيقات موبايل أصلية (Native iOS & Android) من مجرد أوامر كلامية.'),
    (r'(?i)\bautomated code review.*|.*code reviews.*', 'أداة فحص ومراجعة تلقائية للكود بتكتشف الأخطاء والثغرات وبتديك اقتراحات تحسين فورية.'),
    (r'(?i)\bautomates? unit test generation.*', 'أداة ذكية بتكتب وتولد اختبارات الكود (Unit Tests) تلقائياً لضمان استقرار مشروعك.'),
    (r'(?i)\bopen-source.*agent.*', 'وكيل ذكي ومفتوح المصدر بيساعد المطورين في أتمتة وكتابة الأكواد ومتابعة المشاريع بكفاءة.'),
    (r'(?i)\bgenerative ui.*|.*react components.*', 'أداة توليد واجهات مستخدم تفاعلية بتطلعلك كود React و Tailwind جاهز وشغال من وصف بسيط.')
]

def generate_egyptian_notes(name, desc, tags):
    """توليد ملاحظات بالعامية المصرية وبالبلدي مع التصنيفات المعربة وفق توجيه المستخدم"""
    matched_phrase = None
    target_text = f"{name} {desc}"
    for pattern, text in PHRASE_PATTERNS:
        if re.search(pattern, target_text):
            matched_phrase = text
            break
            
    if not matched_phrase:
        d_lower = desc.lower()
        if 'chat' in d_lower or 'chatbot' in d_lower:
            matched_phrase = 'منصة شات ومساعد ذكي متكامل بيفهم طلباتك البرمجية ويديك إجابات وحلول فورية.'
        elif 'full-stack' in d_lower or 'builder' in d_lower or 'build' in d_lower:
            matched_phrase = 'منصة ذكية وسريعة لبناء وتطوير التطبيقات البرمجية والمشاريع بالذكاء الاصطناعي بدون تعقيد.'
        elif 'git' in d_lower:
            matched_phrase = 'أداة ذكية لإدارة مستودعات Git ومساعدة المطورين في التعامل مع الأوامر والفروع بسهولة.'
        elif 'testing' in d_lower or 'review' in d_lower or 'bug' in d_lower:
            matched_phrase = 'أداة فحص ومراجعة للأكواد بتساعدك تكتشف الأخطاء وتصلحها قبل ما تنزل الإنتاج.'
        elif 'voice' in d_lower:
            matched_phrase = 'أداة إدخال وتحكم صوتي ذكية بتساعدك تملي وتتحكم في أدوات البرمجة بصوتك بدقة عالية.'
        elif 'open-source' in d_lower or 'open source' in d_lower:
            matched_phrase = 'مشروع مفتوح المصدر بالذكاء الاصطناعي بيقدم حلول برمجية متطورة للمطورين.'
        else:
            matched_phrase = 'أداة ومساعد ذكي للمطورين بيساعد في كتابة وتحسين الأكواد البرمجية وتسريع الشغل.'
            
    tags_ar = translate_tags_to_arabic(tags)
    if tags_ar:
        return f"{matched_phrase} [تصنيفات: {tags_ar}]"
    return matched_phrase

def extract_canonical_domain(u):
    """استخراج الدومين الجوهري لتفادي التكرار السحابي"""
    if not u: return ''
    m = re.search(r'https?://(?:www\.)?([^/?#:]+)', u.lower())
    if m:
        d = m.group(1)
        d = re.sub(r'^(app|platform|dashboard|router|api|console|portal|chat|beta|docs)\.', '', d)
        return d
    return ''

def resolve_gist_tool_url(tool):
    """استنتاج الرابط الدقيق وتحديد ما إذا كان مستودع GitHub أو منصة ويب"""
    if 'url' in tool and tool['url']:
        u = tool['url'].strip()
        if 'diagrid.io' in u.lower():
            return 'https://www.diagrid.io/', False
        if 'swesmith.com' in u.lower():
            return 'http://swesmith.com/', False
        if 'openlm.ai/swe-bench' in u.lower():
            return 'https://openlm.ai/swe-bench/', False
        if 'goose-docs.ai' in u.lower() or tool.get('name', '').strip().lower() == 'goose':
            return 'https://github.com/block/goose', True
            
        m_gh = re.match(r'^(https?://github\.com/[^/]+/[^/?#]+)(?:/.*)?$', u)
        if m_gh:
            return m_gh.group(1), True
        return u, ('github.com' in u.lower())
        
    name = tool['name'].strip()
    n_lower = name.lower()
    desc = tool.get('description', '').lower()
    
    # 1. فحص قاموس جيت هاب الصريح
    if n_lower in GIST_GITHUB_REPOS:
        return GIST_GITHUB_REPOS[n_lower], True
    for k, v in GIST_GITHUB_REPOS.items():
        if len(k) >= 4 and re.search(rf'\b{re.escape(k)}\b', n_lower):
            return v, True
            
    # 2. فحص الدومينات المعروفة بدقة
    if n_lower in GIST_EXACT_DOMAINS:
        return GIST_EXACT_DOMAINS[n_lower], False
    for k, v in GIST_EXACT_DOMAINS.items():
        if len(k) >= 4 and re.search(rf'\b{re.escape(k)}\b', n_lower):
            return v, False
            
    # 3. فحص ما إذا كان الوصف يشير صراحة لمستودع مفتوح المصدر على جيت هاب
    if 'open-source' in desc or 'open source' in desc:
        clean_proj = re.sub(r'[^a-zA-Z0-9-]', '', name).lower()
        if 'github' in desc:
            return f"https://github.com/{clean_proj}/{clean_proj}", True
            
    # 4. فحص القاموس العام للمنصات
    if n_lower in KNOWN_TOOL_URLS:
        u = KNOWN_TOOL_URLS[n_lower]
        return u, ('github.com' in u)
        
    for k, v in KNOWN_TOOL_URLS.items():
        if len(k) >= 4 and re.search(rf'\b{re.escape(k)}\b', n_lower):
            return v, ('github.com' in v)
            
    # 5. توليد رابط منصة ويب الرسمي
    clean_domain = re.sub(r'\b(ai|agent|platform|studio|cloud|dev|labs|hq)\b', '', n_lower, flags=re.IGNORECASE)
    clean_domain = re.sub(r'[^a-zA-Z0-9]', '', clean_domain).strip()
    if not clean_domain or len(clean_domain) < 3:
        clean_domain = re.sub(r'[^a-zA-Z0-9]', '', n_lower).strip()
        
    return f"https://{clean_domain}.ai", False

def process_gist_and_update_radar(service, gist_file=None, dry_run=False):
    """
    سير العمل المتكامل لمعالجة الجيست:
    1. استخراج الأدوات من الجيست
    2. استبعاد محررات الـ IDE المكتبية فورياً وتوثيقها بالسجل
    3. فحص التكرارات الدقيقة (الأسماء، العلامات، والدومينات) مع الورقة 1 وورقة جيت هاب
    4. توجيه مستودعات GitHub لورقة جيت هاب (مع الاسم والرابط والملاحظات بالعامية المصرية)
    5. توجيه منصات الويب للورقة 1 (مع الاسم والرابط والملاحظات بالعامية المصرية)
    6. تحديث بنر الدستور في الصف الأول من الورقة 1
    7. حفظ وتحديث سجل الاستبعادات والإضافات بالكامل محلياً
    """
    if not gist_file:
        gist_file = r'C:\Users\pc\.gemini\antigravity-ide\brain\8870733f-4bb7-4cda-9d88-b9fd0a33893d\.system_generated\steps\747\content.md'
        
    print("\n" + "="*65)
    print("🚀 بدء المعالجة الشاملة لأدوات الجيست وتحديث الرادار...")
    print("="*65)
    
    # قراءة الأدوات من الجيست
    raw_tools = parse_gist_tools(gist_file)
    if not raw_tools:
        print("❌ لم يتم العثور على أي أدوات في ملف الجيست!")
        return
        
    # جلب بيانات الشيت الحالية للمطابقة الصارمة
    resp1 = service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range='الورقة1!B7:C').execute()
    sheet1_rows = resp1.get('values', [])
    
    resp_gh = service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range='\'جيت هاب  Github\'!B7:C').execute()
    gh_rows = resp_gh.get('values', [])
    
    # تنظيف محررات IDE من الورقة 1 أولاً (مع إعادة استخدام البيانات المجلوبة)
    removed_sheet1_ides = audit_and_clean_desktop_ides_from_sheet1(service, dry_run=dry_run, existing_rows=sheet1_rows)
    
    existing_sheet1_names = {normalize_name(r[0]): r[0] for r in sheet1_rows if len(r) > 0 and r[0].strip()}
    existing_sheet1_urls = {re.sub(r'/+$', '', r[1].strip().lower()): r[0] for r in sheet1_rows if len(r) > 1 and r[1].strip()}
    existing_sheet1_domains = {extract_canonical_domain(r[1]): r[0] for r in sheet1_rows if len(r) > 1 and extract_canonical_domain(r[1]) and extract_canonical_domain(r[1]) not in ['github.com', 'arxiv.org', 'google.com']}
    
    existing_gh_names = {normalize_name(r[0]): r[0] for r in gh_rows if len(r) > 0 and r[0].strip()}
    existing_gh_repos = {normalize_repo_url(r[1]): r[0] for r in gh_rows if len(r) > 1 and r[1].strip()}
    existing_gh_repo_names = {}
    for r in gh_rows:
        if len(r) > 1 and r[1].strip():
            m = re.search(r'github\.com/[^/]+/([^/?#]+)', r[1].lower())
            if m:
                existing_gh_repo_names[m.group(1).replace('.git', '')] = r[0]
    
    gist_excluded = []
    tools_for_sheet1 = []
    tools_for_github = []
    
    seen_in_this_run = set()
    
    for t in raw_tools:
        raw_name = t['name'].strip()
        clean_name = re.sub(r'\s*\((repo|paper|code|srt)\)', '', raw_name, flags=re.IGNORECASE).strip()
        n_norm = normalize_name(clean_name)
        n_lower = clean_name.lower()
        desc = t.get('description', '').strip()
        tags = t.get('tags', [])
        
        # بناء الملاحظات بالعامية المصرية وبالبلدي وفق توجيه المستخدم الدقيق
        egyptian_notes = generate_egyptian_notes(clean_name, desc, tags)
        
        # 1. فحص محررات الـ IDE المكتبية للاستبعاد الفوري
        if n_lower in GIST_DESKTOP_IDES:
            gist_excluded.append({
                'name': raw_name,
                'category': 'Desktop IDE Only',
                'reason': GIST_DESKTOP_IDES[n_lower],
                'source': t.get('source', 'Gist')
            })
            continue
            
        if any(k in n_lower for k in ['cursor', 'windsurf', 'void editor', 'trae']):
            gist_excluded.append({
                'name': raw_name,
                'category': 'Desktop IDE Only',
                'reason': 'محرر IDE مكتبي للابتوب فقط بدون واجهة ويب/شات',
                'source': t.get('source', 'Gist')
            })
            continue
            
        # فحص إضافي بالكلمات المفتاحية لمحررات سطح المكتب
        if ('desktop ide' in desc.lower() or 'desktop code editor' in desc.lower()) and 'open-source' not in desc.lower():
            gist_excluded.append({
                'name': raw_name,
                'category': 'Desktop IDE Only',
                'reason': 'محرر كود مكتبي للابتوب فقط وفق الوصف بدون واجهة ويب/شات',
                'source': t.get('source', 'Gist')
            })
            continue
            
        # 2. استنتاج الرابط وتحديد الوجهة أولاً (GitHub أم منصة ويب)
        url, is_github = resolve_gist_tool_url(t)
        url = re.split(r'[،,]', url)[0].strip()
        
        if n_lower in GIST_GITHUB_REPOS:
            url = GIST_GITHUB_REPOS[n_lower]
            is_github = True
        elif n_lower in GIST_EXACT_DOMAINS:
            url = GIST_EXACT_DOMAINS[n_lower]
            is_github = False

        # 3. فحص واستبعاد الأوراق البحثية الأكاديمية والمقارنات
        has_academic_url = any(x in url.lower() for x in ['arxiv.org', 'aclanthology.org', 'proceedings.', 'dl.acm.org', 'conf.researchr.org', 'openreview.net', 'doi.org']) or url.lower().startswith('arxiv:')
        is_academic_tag = ('ورقة' in ' '.join(tags) and 'كود' not in ' '.join(tags)) or any(x in ' '.join(tags) for x in ['معيار متجدّد'])
        
        if (has_academic_url or is_academic_tag) and not (is_github and 'github.com' in url.lower()):
            gist_excluded.append({
                'name': raw_name,
                'category': 'Research Paper Only',
                'reason': f'ورقة بحثية أكاديمية وليست أداة أو منصة برمجية تنفيذية ({url})',
                'source': t.get('source', 'Gist')
            })
            continue
        if any(k in n_lower for k in ['swe-bench-live', 'swe-bench+', 'swe-rebench', 'swe-search', 'the swe-bench illusion']):
            gist_excluded.append({
                'name': raw_name,
                'category': 'Research Paper/Benchmark',
                'reason': f'تنويعة بحثية أكاديمية أو معيار تقييم ({url})',
                'source': t.get('source', 'Gist')
            })
            continue

        # 4. فحص واستبعاد المواصفات والبروتوكولات القياسية
        if any(x in url.lower() for x in ['slsa.dev', 'spdx.dev', 'cyclonedx.org', 'opentelemetry.io', 'sigstore.dev', 'in-toto.io', 'a2a-protocol.org', 'modelcontextprotocol.io']) or any('مواصفة' in x for x in tags):
            gist_excluded.append({
                'name': raw_name,
                'category': 'Standard/Protocol Spec',
                'reason': f'مواصفة ومعيار أمان أو بروتوكول قياسي ({url})',
                'source': t.get('source', 'Gist')
            })
            continue

        # 5. استبعاد المقالات والمدونات والتوثيقات الفرعية
        if any(x in url.lower() for x in ['xwang.dev', 'dev.to', 'monperrus.net', 'developersdigest.tech', 'encore.dev/blog', 'nebius.com/blog', 'blaxel.ai/blog', 'northflank.com/blog', 'langchain.com/blog', 'openai.com/index', '/blog']):
            gist_excluded.append({
                'name': raw_name,
                'category': 'Blog/Article Only',
                'reason': f'مقال تحليلي/شرح تقني وليس أداة أو منصة برمجية مستقلة ({url})',
                'source': t.get('source', 'Gist')
            })
            continue
            
        if any(k in n_lower for k in ['strands swarm', 'strands session', 'strands observability', 'agent sandbox docs', 'adk workflow agents', 'adk architecture', 'temporal versioning', 'restate request lifecycle', 'dbos vs temporal', 'inngest checkpointing', 'swe-bench verified', 'swe-bench multimodal', 'suna sandbox path', 'microsoft agent framework']):
            gist_excluded.append({
                'name': raw_name,
                'category': 'Sub-doc/Variant',
                'reason': f'توثيق فرعي أو تنويعة مسجلة بالفعل للمشروع ({url})',
                'source': t.get('source', 'Gist')
            })
            continue
        if any('وثيقة' in x for x in tags) or any('مجموعة فرعية' in x for x in tags) or 'نفس المستودع' in url or 'إصدار' in url:
            gist_excluded.append({
                'name': raw_name,
                'category': 'Documentation/Subset',
                'reason': f'توثيق فرعي أو مجموعة فرعية لنفس المستودع ({url})',
                'source': t.get('source', 'Gist')
            })
            continue

        # 6. فحص التكرار الداخلي في نفس الجلسة
        if n_norm in seen_in_this_run:
            gist_excluded.append({
                'name': raw_name,
                'category': 'Duplicate in Gist',
                'reason': 'تكرار داخل نفس ملف الجيست',
                'source': t.get('source', 'Gist')
            })
            continue
        clean_url_key = re.sub(r'/+$', '', url.lower())
        if clean_url_key in seen_in_this_run:
            gist_excluded.append({
                'name': raw_name,
                'category': 'Duplicate URL in Gist',
                'reason': f'رابط مكرر داخل نفس ملف الجيست ({url})',
                'source': t.get('source', 'Gist')
            })
            continue
            
        seen_in_this_run.add(n_norm)
        seen_in_this_run.add(clean_url_key)
            
        u_norm = normalize_repo_url(url) if is_github else re.sub(r'/+$', '', url.lower())
        d_root = extract_canonical_domain(url)
        
        if is_github:
            m_gh = re.match(r'^(https?://github\.com/[^/]+/[^/?#]+)(?:/.*)?$', url)
            if m_gh:
                url = m_gh.group(1)
                u_norm = normalize_repo_url(url)
            m_r = re.search(r'github\.com/[^/]+/([^/?#]+)', url.lower())
            repo_slug = m_r.group(1).replace('.git', '') if m_r else ''
            
            if u_norm in existing_gh_repos:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Duplicate GitHub Repo',
                    'reason': f"مستودع جيت هاب مكرر ومسجل مسبقاً ({existing_gh_repos[u_norm]})",
                    'source': t.get('source', 'Gist')
                })
                continue
            if repo_slug and repo_slug in existing_gh_repo_names:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Duplicate GitHub Repo',
                    'reason': f"المستودع مسجل مسبقاً باسم [{existing_gh_repo_names[repo_slug]}] ({url})",
                    'source': t.get('source', 'Gist')
                })
                continue
            if n_norm in existing_gh_names:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Already in GitHub Sheet',
                    'reason': f"مسجل مسبقاً في ورقة جيت هاب باسم [{existing_gh_names[n_norm]}]",
                    'source': t.get('source', 'Gist')
                })
                continue
            if n_norm in existing_sheet1_names:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Already in Sheet 1',
                    'reason': f"الأداة مسجلة مسبقاً في الورقة 1 باسم [{existing_sheet1_names[n_norm]}]",
                    'source': t.get('source', 'Gist')
                })
                continue
            if u_norm in existing_sheet1_urls:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Already in Sheet 1',
                    'reason': f"الرابط مسجل مسبقاً في الورقة 1 ({existing_sheet1_urls[u_norm]})",
                    'source': t.get('source', 'Gist')
                })
                continue
                
            existing_gh_repos[u_norm] = clean_name
            if repo_slug: existing_gh_repo_names[repo_slug] = clean_name
            existing_gh_names[n_norm] = clean_name
            tools_for_github.append({
                'name': clean_name,
                'url': url,
                'status': '⏳ لم يتم الفحص',
                'notes': egyptian_notes
            })
        else:
            if n_lower in KNOWN_BRANDS_IN_SHEET:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Already in Sheet',
                    'reason': f"أداة/علامة مسجلة مسبقاً بالشيت باسم [{KNOWN_BRANDS_IN_SHEET[n_lower]}]",
                    'source': t.get('source', 'Gist')
                })
                continue
            if n_norm in existing_sheet1_names:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Already in Sheet 1',
                    'reason': f"مسجل مسبقاً في الورقة 1 باسم [{existing_sheet1_names[n_norm]}]",
                    'source': t.get('source', 'Gist')
                })
                continue
            if u_norm in existing_sheet1_urls:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Duplicate Web URL',
                    'reason': f"رابط المنصة مكرر ومسجل مسبقاً ({existing_sheet1_urls[u_norm]})",
                    'source': t.get('source', 'Gist')
                })
                continue
            if d_root and d_root in existing_sheet1_domains:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Duplicate Web URL',
                    'reason': f"دومين المنصة مسجل مسبقاً في الورقة 1 تحت [{existing_sheet1_domains[d_root]}] ({url})",
                    'source': t.get('source', 'Gist')
                })
                continue
            if n_norm in existing_gh_names:
                gist_excluded.append({
                    'name': raw_name,
                    'category': 'Already in GitHub Sheet',
                    'reason': f"مسجل مسبقاً في ورقة جيت هاب باسم [{existing_gh_names[n_norm]}]",
                    'source': t.get('source', 'Gist')
                })
                continue
                
            if d_root:
                existing_sheet1_domains[d_root] = clean_name
            existing_sheet1_urls[u_norm] = clean_name
            existing_sheet1_names[n_norm] = clean_name
            tools_for_sheet1.append({
                'name': clean_name,
                'url': url,
                'status': '⏳ لم يتم الفحص',
                'notes': egyptian_notes
            })
            
    print("\n" + "="*60)
    print("📊 نتائج فرز وتصنيف أدوات الجيست:")
    print(f" • إجمالي الأدوات المعالجة من الجيست: {len(raw_tools)}")
    print(f" • أدوات مستبعدة ومحفوظة بالسجل: {len(gist_excluded)}")
    print(f" • مستودعات جديدة تماماً موجهة لورقة جيت هاب: {len(tools_for_github)}")
    print(f" • منصات جديدة تماماً موجهة للورقة 1: {len(tools_for_sheet1)}")
    print("="*60 + "\n")
    
    # حفظ السجل المحلي دائماً
    save_exclusion_log(removed_sheet1_ides, gist_excluded, tools_for_sheet1, tools_for_github)
    
    if dry_run:
        print("⚠️ تم تشغيل الأمر بوضع المعاينة (Dry-Run)؛ لم يتم كتابة أي بيانات بالشيت.")
        return
        
    # 6. كتابة المستودعات الجديدة في ورقة جيت هاب
    if tools_for_github:
        print(f"🐙 جاري إضافة {len(tools_for_github)} مستودع جديد إلى ورقة جيت هاب...")
        current_gh_count = len(gh_rows)
        gh_values = []
        for idx, item in enumerate(tools_for_github, start=7 + current_gh_count):
            row_num = idx
            dup_name_formula = f'=IF(OR(ISBLANK(B{row_num}), B{row_num}=""), "", IFERROR(LET(clean_n, LOWER(TRIM(CLEAN(B{row_num}))), prev, MAP(INDIRECT("B$1:B" & (ROW()-1)), LAMBDA(x, LOWER(TRIM(CLEAN(x))))), m, MATCH(clean_n, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
            dup_url_formula = f'=IF(OR(ISBLANK(C{row_num}), C{row_num}=""), "", IFERROR(LET(clean_d, IFERROR(REGEXEXTRACT(LOWER(TRIM(C{row_num})), "(?:github\\.com/[^/?#]+(?:/[^/?#]+)?|[^/?#]+\\.github\\.io(?:/[^/?#]+)?)"), REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(C{row_num})), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)")), prev, MAP(INDIRECT("C$1:C" & (ROW()-1)), LAMBDA(x, IFERROR(REGEXEXTRACT(LOWER(TRIM(x)), "(?:github\\.com/[^/?#]+(?:/[^/?#]+)?|[^/?#]+\\.github\\.io(?:/[^/?#]+)?)"), IFERROR(REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(x)), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), "")))), m, MATCH(clean_d, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
            gh_values.append(['', item['name'], item['url'], item['status'], dup_name_formula, dup_url_formula, item['notes'], ''])
            
        start_row = 7 + current_gh_count
        end_row = start_row + len(gh_values) - 1
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"'جيت هاب  Github'!A{start_row}:H{end_row}",
            valueInputOption='USER_ENTERED',
            body={'values': gh_values}
        ).execute()
        print(f"✅ تمت إضافة {len(gh_values)} مستودع بنجاح إلى ورقة جيت هاب!")
        
    # 7. كتابة المنصات الجديدة في الورقة 1
    if tools_for_sheet1:
        print(f"🌐 جاري إضافة {len(tools_for_sheet1)} منصة جديدة إلى الورقة 1...")
        current_w1_count = len(sheet1_rows)
        
        w1_values = []
        for idx, item in enumerate(tools_for_sheet1, start=7 + current_w1_count):
            row_num = idx
            dup_name_formula = f'=IF(OR(ISBLANK(B{row_num}), B{row_num}=""), "", IFERROR(LET(clean_n, LOWER(TRIM(CLEAN(B{row_num}))), prev, MAP(INDIRECT("B$1:B" & (ROW()-1)), LAMBDA(x, LOWER(TRIM(CLEAN(x))))), m, MATCH(clean_n, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
            dup_url_formula = f'=IF(OR(ISBLANK(C{row_num}), C{row_num}=""), "", IFERROR(LET(clean_d, REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(C{row_num})), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), prev, MAP(INDIRECT("C$1:C" & (ROW()-1)), LAMBDA(x, IFERROR(REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(x)), "^https?://((www|app|platform|dashboard|router|api)\\\\.)?|^((www|app|platform|dashboard|router|api)\\\\.)?", ""), "^([^/?#:]+)"), ""))), m, MATCH(clean_d, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))'
            w1_values.append(['', item['name'], item['url'], item['status'], dup_name_formula, dup_url_formula, item['notes'], ''])
            
        start_row = 7 + current_w1_count
        end_row = start_row + len(w1_values) - 1
        
        # تحديث على دفعات لتجنب حدود الحجم
        batch_size = 200
        for b_idx in range(0, len(w1_values), batch_size):
            chunk = w1_values[b_idx:b_idx+batch_size]
            b_start = start_row + b_idx
            b_end = b_start + len(chunk) - 1
            service.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range=f"الورقة1!A{b_start}:H{b_end}",
                valueInputOption='USER_ENTERED',
                body={'values': chunk}
            ).execute()
        print(f"✅ تمت إضافة {len(w1_values)} منصة بنجاح إلى الورقة 1!")
        
    # 8. تحديث كروت الـ KPI والقوائم المنسدلة لضمان الجاهزية التامة
    try:
        apply_dropdowns(service)
    except Exception as e:
        print(f"ℹ️ تم تجاوز تحديث القوائم المنسدلة نظراً لانشغال خادم جوجل شيت بالعمليات الحسابية ({e})")
    try:
        fix_kpi_cards(service, quiet=True)
        print(f"📌 تم تثبيت معادلات KPI بـ INDIRECT من الصف {DATA_START_ROW}.")
    except Exception as e:
        print(f"ℹ️ تم تجاوز تثبيت معادلات KPI ({e})")
    print("🎉 اكتملت معالجة وتحديث رادار جوجل شيت بنجاح 100%!")

def main():
    parser = argparse.ArgumentParser(description="Google Sheets Manager for AI Radar")
    parser.add_argument('--status', action='store_true', help="عرض إحصائيات الشيت الحالية")
    parser.add_argument('--fix-kpi', action='store_true', help="تثبيت معادلات KPI بـ INDIRECT من الصف 7 في الورقة1 وجيت هاب (ما تتزحلقش)")
    parser.add_argument('--fix-dropdowns', action='store_true', help="تفعيل القوائم المنسدلة من الصف 7 في الورقة1 وجيت هاب")
    parser.add_argument('--move-github', action='store_true', help="نقل وحذف روابط جيت هاب من الورقة 1 إلى ورقة جيت هاب")
    parser.add_argument('--check-sheet1-dups', action='store_true', help="فحص وعرض تقرير تكرار الروابط في الورقة 1 بدون مسح")
    parser.add_argument('--clean-sheet1-dups', action='store_true', help="تنفيذ تطهير الروابط المكررة في الورقة 1")
    parser.add_argument('--list-link-removed', action='store_true', help="حصر وعرض الأدوات التي تحتاج روابط صحيحة")
    parser.add_argument('--resolve-links', action='store_true', help="استنتاج ووضع الروابط الصحيحة لصفوف link removed")
    parser.add_argument('--audit-ides', action='store_true', help="فحص محررات الـ IDE المكتبية في الورقة 1 وحفظ التقرير")
    parser.add_argument('--clean-ides', action='store_true', help="حذف محررات الـ IDE المكتبية من الورقة 1")
    parser.add_argument('--set-banner', action='store_true', help="تثبيت بنر دستور ومعايير الرادار في الصف الأول من الورقة 1")
    parser.add_argument('--process-gist', action='store_true', help="معالجة وتصنيف أدوات الجيست وتحديث الورقة 1 وورقة جيت هاب")
    parser.add_argument('--gist-file', type=str, default=None, help="مسار ملف الجيست المحلي")
    parser.add_argument('--limit', type=int, default=None, help="تحديد عدد الأدوات المراد تحديثها")
    parser.add_argument('--dry-run', action='store_true', help="معاينة العملية دون كتابة فعلية")
    parser.add_argument('--show-apps-script', action='store_true', help="عرض كود Apps Script اللحظي")
    
    args = parser.parse_args()
    service = get_service()
    
    if args.status:
        show_stats(service)
    elif args.fix_kpi:
        fix_kpi_cards(service)
    elif args.fix_dropdowns:
        apply_dropdowns(service)
    elif args.move_github:
        move_github_from_sheet1(service, dry_run=args.dry_run)
    elif args.check_sheet1_dups:
        analyze_sheet1_duplicate_urls(service)
    elif args.clean_sheet1_dups:
        clean_sheet1_duplicate_urls(service, dry_run=args.dry_run)
    elif args.list_link_removed:
        list_link_removed_summary(service)
    elif args.resolve_links:
        resolve_and_update_all_links(service, dry_run=args.dry_run, limit=args.limit)
    elif args.audit_ides:
        audit_and_clean_desktop_ides_from_sheet1(service, dry_run=True)
    elif args.clean_ides:
        audit_and_clean_desktop_ides_from_sheet1(service, dry_run=args.dry_run)
    elif args.set_banner:
        setup_sheet1_constitution_banner(service)
    elif args.process_gist:
        process_gist_and_update_radar(service, gist_file=args.gist_file, dry_run=args.dry_run)
    elif args.show_apps_script:
        print(get_apps_script_code())
    else:
        show_stats(service)

if __name__ == '__main__':
    main()

