# 📊 Google Sheets Automation & Apps Script Suite (زووووود زود)

منظومة ذكية متكاملة لإدارة ومزامنة شيتات رادار الذكاء الاصطناعي مع Google Sheets API و Google Apps Script.

---

## 🌟 الميزات الرئيسية

1. **⚡ محرك الترتيب الذكي الفوري (Real-time Priority Sorter):**
   - سكريبت Apps Script (onEdit_github_transfer.js و Code.gs) يعمل بتريجر مخصص (installedOnEdit) بصلاحيات كاملة.
   - ترتيب هرمي خماسي المستويات فوري للجدول:
     1. 🔄 قيد التجربة (يقفز تلقائياً لأول صفوف الجدول بدءاً من الصف 7).
     2. ✅ يعمل بنجاح (يتجمع مباشرة تحت قيد التجربة).
     3. ❌ لا تعمل / ❌ لا يعمل (يتجمع تحت يعمل بنجاح).
     4. مرفوض (يتجمع تحت لا تعمل).
     5. ⏳ لم يتم الفحص (في نهاية الجدول).
   - قائمة مخصصة ⚡ أدوات الترتيب الذكي لتنفيذ الترتيب اليدوي الشامل بضغطة زر.

2. **🐙 النقل التلقائي الذكي لروابط جيت هاب:**
   - كشف لحظي لروابط github.com و github.io المنشورة في "الورقة1".
   - نقل الصف بالكامل تلقائياً إلى ورقة "جيت هاب Github" لمنع التكرار والحفاظ على هيكل البيانات.

3. **🛠️ أداة الإدارة والتحكم الشاملة (sheets_manager.py):**
   - فحص وتصليح القوائم المنسدلة (Dropdowns / Data Validation) عبر واجهة Sheets API v4.
   - كشف التكرارات وإحصائيات الـ KPI الحية.
   - إزالة وتصفية الأدوات المكررة وتدوين السجلات في excluded_tools_log.json و link_removed_items.json.

---

## 📁 هيكل المشروع

`	ext
├── Code.gs                      # كود Apps Script الأساسي للشيت
├── onEdit_github_transfer.js    # كود الترتيب والنقل التلقائي الفوري
├── sheets_manager.py            # أداة بايثون المركزية للإدارة والمزامنة
├── credentials.example.json     # قالب إعداد مفاتيح Google Cloud Service Account
├── excluded_tools_log.json      # سجل الأدوات المستبعدة
├── link_removed_items.json      # سجل الروابط المحذوفة
├── Root/                        # دفاتر الحوكمة والذاكرة والمهام والتوثيق
└── README.md                    # دليل التشغيل والتوثيق
`

---

## 🚀 البدء السريع

### 1. إعداد متطلبات بايثون
`ash
pip install google-auth google-auth-oauthlib google-api-python-client requests
`

### 2. إعداد بيانات الاعتماد
1. قم بإنشاء Service Account من Google Cloud Console.
2. امنح الإيميل الخاص بالحساب صلاحية Editor على الشيت المطلوب.
3. انسخ ملف المفاتيح وسمّه credentials.json في نفس المجلد.

### 3. تشغيل أداة المزامنة
`ash
python sheets_manager.py --help
`

### 4. تركيب Apps Script على Google Sheets
1. افتح جدول البيانات على Google Sheets.
2. اذهب إلى: **الإضافات (Extensions) > Apps Script**.
3. الصق محتوى onEdit_github_transfer.js داخل محرر الأكواد.
4. اختر دالة تفعيل_الترتيب_التلقائي واضغط **تشغيل (Run)** لمنح الصلاحيات وتفعيل التريجر التلقائي.
