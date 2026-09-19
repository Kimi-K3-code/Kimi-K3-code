/**
 * =============================================================================
 * ⚡ المنظومة الذكية المتكاملة لجوجل شيت — Apps Script v2.4 (الإصلاح النهائي)
 * =============================================================================
 *
 * 🧠 السبب الحقيقي لمشكلة "أعملها 7 ترجع تاني 8 / 9 / 10":
 *
 *    الكود بيرفع أي صف حالته "🔄 قيد التجربة" للصف 7 بـ moveRows / insertRowBefore(7).
 *    جوجل شيتس بيعتبر ده "إدراج صف فوق الصف 7"، فأي نطاق بيبدأ من الصف 7 بالظبط
 *    (تنسيق شرطي D7:D / B7:B — أو معادلات الإحصائيات COUNTIF(D7:D…))
 *    بيتزحلق لتحت صف واحد كل مرة:  D7:D → D8:D → D9:D → D10:D …
 *    يعني المشكلة مش في جوجل ولا فيك — دي نتيجة طبيعية لطريقة الترتيب.
 *
 * ✅ الحل الجذري في v2.4 (3 حاجات):
 *    1. معادلات الإحصائيات (B3:F3) بقت INDIRECT("D7:D") = نص ثابت جوجل ما يقدرش يزحلقه.
 *       وبتتثبت أوتوماتيك بعد أي نقل صف.
 *    2. نطاقات التنسيق الشرطي بتتربط بصف العنوان (الصف 6) بدل الصف 7:
 *       الإدراج عند الصف 7 بيبقى "جوه" النطاق فبيتمدد بدل ما يتزحلق — مناعة كاملة.
 *       (المعادلات المخصصة بتتعدل تلقائياً وبتتحمي بـ ROW()>=7 فصف العنوان ما يتلونش).
 *    3. الترتيب التلقائي بيشتغل فقط لما تغيّر خلية الحالة (D) نفسها بإيدك —
 *       سحب صف بالماوس أو لصق جماعي ما بيحرّكش حاجة.
 *
 * 📦 طريقة التركيب (مرة واحدة):
 *    1. Extensions → Apps Script → امسح كل الكود القديم والصق الملف ده كامل → Ctrl+S
 *    2. ارجع للشيت واعمل Refresh (F5) → هتلاقي قائمة "⚡ أدوات الترتيب الذكي"
 *    3. اضغط "🚀 تفعيل الترتيب التلقائي" → اقبل الصلاحيات
 *    4. اضغط "🧹 إصلاح كل النطاقات والمعادلات" → هيظهرلك تقرير بالتعديلات
 *    5. خلاص — النطاقات مش هترجع تاني أبداً.
 * =============================================================================
 */

// -----------------------------------------------------------------------------
// 0) الإعدادات المركزية
// -----------------------------------------------------------------------------
var CONFIG = {
  DATA_START_ROW: 7,                 // أول صف بيانات
  HEADER_ROW: 6,                     // صف العنوان (اسم الموقع / الرابط / حالة الاختبار …)
  KPI_ROW: 3,                        // صف أرقام الإحصائيات (B3:F3)
  STATUS_COL: 4,                     // D = حالة الاختبار
  URL_COL: 3,                        // C = الرابط
  NAME_COL: 2,                       // B = اسم الموقع
  NOTES_COL: 7,                      // G = الملاحظات
  NUM_COLS: 8,                       // A..H
  PIN_RANK1_AT_TOP: true,            // "🔄 قيد التجربة" يقفز دايماً للصف 7
  AUTO_GITHUB_TRANSFER: true,        // نقل روابط جيت هاب تلقائياً لورقة جيت هاب
  FIX_AFTER_EVERY_MOVE: true         // تثبيت معادلات الإحصائيات بعد كل نقل (5 خلايا فقط — سريع)
};

var _scriptLock = null;

// -----------------------------------------------------------------------------
// 1) القائمة العلوية
// -----------------------------------------------------------------------------
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("⚡ أدوات الترتيب الذكي")
    .addItem("🚀 تفعيل الترتيب التلقائي (مرة واحدة)", "تفعيل_الترتيب_التلقائي")
    .addItem("🛑 إيقاف الترتيب التلقائي (تحكم يدوي)", "إيقاف_الترتيب_التلقائي")
    .addSeparator()
    .addItem("🧹 إصلاح كل النطاقات والمعادلات (تبدأ من الصف 7)", "إصلاح_كل_النطاقات")
    .addItem("📌 تثبيت معادلات الإحصائيات فقط", "fixAllKpiCards")
    .addItem("🔍 فحص سريع", "فحص_سريع")
    .addSeparator()
    .addItem("🔄 ترتيب الورقة الحالية حسب الأولوية", "sortActiveSheetByPriority")
    .addItem("📋 ترتيب 'الورقة1' حسب الأولوية", "sortSheet1ByPriority")
    .addItem("🐙 ترتيب 'جيت هاب Github' حسب الأولوية", "sortGitHubSheetByPriority")
    .addSeparator()
    .addItem("⬆️ انقُل الصف المحدد إلى الصف 7", "نقل_الصف_المحدد_إلى_الصف_7")
    .addToUi();
}

// -----------------------------------------------------------------------------
// 2) تفعيل / إيقاف المشغل المعتمد (Installable Trigger)
// -----------------------------------------------------------------------------
function تفعيل_الترتيب_التلقائي() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) ScriptApp.deleteTrigger(triggers[i]);

  ScriptApp.newTrigger("installedOnEdit").forSpreadsheet(ss).onEdit().create();

  var fixed = fixAllKpiCards_(ss);
  ss.toast("🎉 تم التفعيل. الترتيب هيشتغل فقط لما تغيّر خلية الحالة (D) بنفسك. تم تثبيت الإحصائيات في " + fixed + " ورقة.", "⚡ تم التفعيل", 7);
}

function إيقاف_الترتيب_التلقائي() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) ScriptApp.deleteTrigger(triggers[i]);
  ss.toast("🛑 تم إيقاف " + triggers.length + " مشغل. الشيت تحت تحكمك اليدوي بالكامل.", "🛑 تم الإيقاف", 6);
}

// المشغل المعتمد — هو الوحيد اللي بيشتغل
function installedOnEdit(e) {
  processSheetEdit(e);
}

// المشغل البسيط معطّل عن قصد: ما بيقدرش يستخدم LockService/ScriptApp،
// ولو اشتغل مع المعتمد هيعمل تشغيل مزدوج. استخدم زر "🚀 تفعيل" مرة واحدة.
function onEdit(e) {
  return;
}

// -----------------------------------------------------------------------------
// 3) القفل
// -----------------------------------------------------------------------------
function _acquireLock() {
  try {
    _scriptLock = LockService.getScriptLock();
    return _scriptLock.tryLock(8000);
  } catch (err) {
    _scriptLock = null;
    return true;
  }
}

function _releaseLock() {
  if (_scriptLock) {
    try { _scriptLock.releaseLock(); } catch (err) { }
    _scriptLock = null;
  }
}

// -----------------------------------------------------------------------------
// 4) التعرف على الأوراق
// -----------------------------------------------------------------------------
function _isMainSheet(sheetName) {
  var n = String(sheetName).trim().toLowerCase();
  return n.indexOf("ورقة") !== -1 || n.indexOf("sheet1") !== -1 || n.indexOf("sheet 1") !== -1;
}

function _isGitHubSheet(sheetName) {
  var n = String(sheetName).trim().toLowerCase();
  return n.indexOf("جيت هاب") !== -1 || n.indexOf("github") !== -1;
}

// ورقة "رادار" = فيها صف عنوان (اسم الموقع في B6) أو كروت إحصائيات (B2 فيها "إجمالي")
function _isRadarSheet(sheet) {
  try {
    if (sheet.getMaxRows() < CONFIG.DATA_START_ROW) return false;
    var b6 = String(sheet.getRange(CONFIG.HEADER_ROW, CONFIG.NAME_COL).getValue());
    var b2 = String(sheet.getRange(2, CONFIG.NAME_COL).getValue());
    var d6 = String(sheet.getRange(CONFIG.HEADER_ROW, CONFIG.STATUS_COL).getValue());
    return b6.indexOf("اسم الموقع") !== -1 || d6.indexOf("حالة") !== -1 || b2.indexOf("إجمالي") !== -1;
  } catch (err) {
    return false;
  }
}

function _findGitHubSheet(ss) {
  var t = ss.getSheetByName("جيت هاب  Github") || ss.getSheetByName("جيت هاب Github");
  if (t) return t;
  var sheets = ss.getSheets();
  for (var i = 0; i < sheets.length; i++) {
    if (_isGitHubSheet(sheets[i].getName())) return sheets[i];
  }
  return null;
}

// -----------------------------------------------------------------------------
// 5) المنطق المركزي لأي تعديل
// -----------------------------------------------------------------------------
function processSheetEdit(e) {
  if (!e || !e.range || !e.source) return;

  var range = e.range;
  var sheet = range.getSheet();
  var ss = e.source;

  var startRow = range.getRow();
  var numRows = range.getNumRows();
  var startCol = range.getColumn();
  var numCols = range.getNumColumns();
  var endRow = startRow + numRows - 1;
  var endCol = startCol + numCols - 1;

  if (endRow < CONFIG.DATA_START_ROW) return;   // تجاهل الصفوف 1..6

  if (!_acquireLock()) return;
  try {
    var transferred = [];

    // أ) نقل روابط جيت هاب: فقط لو التعديل كله جوه B..C في الورقة الرئيسية
    var insideNameUrl = (startCol >= CONFIG.NAME_COL) && (endCol <= CONFIG.URL_COL);
    if (CONFIG.AUTO_GITHUB_TRANSFER && insideNameUrl && _isMainSheet(sheet.getName())) {
      transferred = handleGitHubTransfer(ss, sheet, startRow, numRows);
    }

    // ب) الترتيب التلقائي: فقط عند تغيير خلية واحدة في العمود D
    //    (سحب صف بالماوس بيبعت نطاق A:H → ما بيتطابقش → الصف بيفضل مكانه)
    var isSingleStatusEdit = (startCol === CONFIG.STATUS_COL) && numCols === 1 && numRows === 1;
    if (!isSingleStatusEdit) return;
    if (startRow < CONFIG.DATA_START_ROW) return;
    if (transferred.indexOf(startRow) !== -1) return;

    var status = sheet.getRange(startRow, CONFIG.STATUS_COL).getValue();
    if (status && String(status).trim() !== "") {
      handleStatusChange(sheet, startRow, status);
    }
  } catch (err) {
    Logger.log("processSheetEdit error: " + err);
  } finally {
    _releaseLock();
  }
}

// -----------------------------------------------------------------------------
// 6) رتبة الحالة (1 = فوق … 5 = آخر الشيت)
// -----------------------------------------------------------------------------
function getStatusRank(status) {
  if (!status) return 5;
  var s = String(status).trim();
  if (s.indexOf("قيد التجربة") !== -1) return 1;
  if (s.indexOf("يعمل بنجاح") !== -1) return 2;
  if (s.indexOf("لا تعمل") !== -1 || s.indexOf("لا يعمل") !== -1) return 3;
  if (s.indexOf("مرفوض") !== -1) return 4;
  return 5;
}

// -----------------------------------------------------------------------------
// 7) حساب الوجهة ونقل الصف
// -----------------------------------------------------------------------------
function handleStatusChange(sheet, editedRow, newStatus) {
  var START = CONFIG.DATA_START_ROW;
  if (editedRow < START) return;

  var targetRank = getStatusRank(newStatus);
  var lastRow = sheet.getLastRow();
  if (lastRow < START) return;

  var destRow = null;
  if (targetRank === 1 && CONFIG.PIN_RANK1_AT_TOP) {
    destRow = START;
  } else {
    var statuses = sheet.getRange(START, CONFIG.STATUS_COL, lastRow - START + 1, 1).getValues();
    for (var i = 0; i < statuses.length; i++) {
      var r = i + START;
      if (r === editedRow) continue;
      if (getStatusRank(statuses[i][0]) > targetRank) { destRow = r; break; }
    }
    if (destRow === null) destRow = lastRow + 1;
  }

  if (destRow < START) destRow = START;
  if (editedRow === destRow) return;
  if (destRow === editedRow + 1) return;   // نفس المكان فعلياً

  moveRowToDestination(sheet, editedRow, destRow);
}

// -----------------------------------------------------------------------------
// 8) محرك النقل (3 طبقات) + تثبيت الإحصائيات بعد النقل
// -----------------------------------------------------------------------------
function moveRowToDestination(sheet, sourceRow, destRow) {
  if (destRow < CONFIG.DATA_START_ROW) destRow = CONFIG.DATA_START_ROW;
  var moved = false;

  try {
    sheet.moveRows(sheet.getRange(sourceRow + ":" + sourceRow), destRow);
    moved = true;
  } catch (e1) {
    Logger.log("moveRows(A1) failed: " + e1);
  }

  if (!moved) {
    try {
      sheet.moveRows(sheet.getRange(sourceRow, 1, 1, sheet.getMaxColumns()), destRow);
      moved = true;
    } catch (e2) {
      Logger.log("moveRows(full) failed: " + e2);
    }
  }

  if (!moved) {
    var lastCol = Math.max(sheet.getLastColumn(), CONFIG.NUM_COLS);
    if (destRow < sourceRow) {
      sheet.insertRowBefore(destRow);
      sheet.getRange(sourceRow + 1, 1, 1, lastCol).moveTo(sheet.getRange(destRow, 1));
      sheet.deleteRow(sourceRow + 1);
    } else {
      sheet.insertRowAfter(destRow);
      sheet.getRange(sourceRow, 1, 1, lastCol).moveTo(sheet.getRange(destRow + 1, 1));
      sheet.deleteRow(sourceRow);
    }
  }

  if (CONFIG.FIX_AFTER_EVERY_MOVE) fixKpiCards_(sheet);
}

// -----------------------------------------------------------------------------
// 9) معادلات الإحصائيات (B3:F3) بـ INDIRECT — ما تتزحلقش أبداً
// -----------------------------------------------------------------------------
function fixKpiCards_(sheet) {
  try {
    if (!sheet || !_isRadarSheet(sheet)) return false;
    var S = CONFIG.DATA_START_ROW;
    var D = 'INDIRECT("D' + S + ':D")';
    var B = 'INDIRECT("B' + S + ':B")';
    sheet.getRange(CONFIG.KPI_ROW, 2, 1, 5).setFormulas([[
      '=COUNTA(' + B + ')',
      '=COUNTIF(' + D + ',"*يعمل بنجاح*")',
      '=COUNTIF(' + D + ',"*قيد التجربة*")',
      '=COUNTIF(' + D + ',"*لا يعمل*")+COUNTIF(' + D + ',"*لا تعمل*")',
      '=COUNTIF(' + D + ',"*لم يتم الفحص*")'
    ]]);
    return true;
  } catch (err) {
    Logger.log("fixKpiCards_ error: " + err);
    return false;
  }
}

function fixAllKpiCards_(ss) {
  var sheets = ss.getSheets(), n = 0;
  for (var i = 0; i < sheets.length; i++) if (fixKpiCards_(sheets[i])) n++;
  return n;
}

function fixAllKpiCards() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var n = fixAllKpiCards_(ss);
  ss.toast("📌 تم تثبيت معادلات الإحصائيات (INDIRECT من الصف " + CONFIG.DATA_START_ROW + ") في " + n + " ورقة.", "تم", 5);
}

// -----------------------------------------------------------------------------
// 10) نقل روابط جيت هاب لورقة "جيت هاب Github"
// -----------------------------------------------------------------------------
function handleGitHubTransfer(ss, sheet, startRow, numRows) {
  var START = CONFIG.DATA_START_ROW;
  var target = _findGitHubSheet(ss);
  if (!target) return [];

  var lastTargetRow = Math.max(target.getLastRow(), START);
  var targetUrls = target.getRange(START, CONFIG.URL_COL, Math.max(lastTargetRow - START + 1, 1), 1).getValues();

  var transferred = [];
  for (var r = startRow + numRows - 1; r >= Math.max(startRow, START); r--) {
    var urlRaw = sheet.getRange(r, CONFIG.URL_COL).getValue();
    var url = urlRaw ? String(urlRaw).trim().toLowerCase() : "";
    if (!url) continue;
    if (url.indexOf("github.com") === -1 && url.indexOf("github.io") === -1) continue;

    var row = sheet.getRange(r, 1, 1, CONFIG.NUM_COLS).getValues()[0];
    var name = row[CONFIG.NAME_COL - 1];
    var origUrl = row[CONFIG.URL_COL - 1];
    var status = row[CONFIG.STATUS_COL - 1] || "⏳ لم يتم الفحص";
    var notes = row[CONFIG.NOTES_COL - 1] || "";

    var exists = false;
    for (var i = 0; i < targetUrls.length; i++) {
      var t = targetUrls[i][0] ? String(targetUrls[i][0]).trim().toLowerCase() : "";
      if (t && t === url) { exists = true; break; }
    }

    if (!exists) {
      var nextRow = Math.max(target.getLastRow() + 1, START);
      var dupName = '=IF(OR(ISBLANK(B' + nextRow + '), B' + nextRow + '=""), "", IFERROR(LET(clean_n, LOWER(TRIM(CLEAN(B' + nextRow + '))), prev, MAP(INDIRECT("B$1:B" & (ROW()-1)), LAMBDA(x, LOWER(TRIM(CLEAN(x))))), m, MATCH(clean_n, prev, 0), IF(AND(m>=' + START + ', m<ROW()), "صف " & m, "")), ""))';
      var dupUrl = '=IF(OR(ISBLANK(C' + nextRow + '), C' + nextRow + '=""), "", IFERROR(LET(clean_d, IFERROR(REGEXEXTRACT(LOWER(TRIM(C' + nextRow + ')), "(?:github\\.com/[^/?#]+(?:/[^/?#]+)?|[^/?#]+\\.github\\.io(?:/[^/?#]+)?)"), REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(C' + nextRow + ')), "^https?://((www|app|platform|dashboard|router|api)\\.)?|^((www|app|platform|dashboard|router|api)\\.)?", ""), "^([^/?#:]+)")), prev, MAP(INDIRECT("C$1:C" & (ROW()-1)), LAMBDA(x, IFERROR(REGEXEXTRACT(LOWER(TRIM(x)), "(?:github\\.com/[^/?#]+(?:/[^/?#]+)?|[^/?#]+\\.github\\.io(?:/[^/?#]+)?)"), IFERROR(REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(x)), "^https?://((www|app|platform|dashboard|router|api)\\.)?|^((www|app|platform|dashboard|router|api)\\.)?", ""), "^([^/?#:]+)"), "")))), m, MATCH(clean_d, prev, 0), IF(AND(m>=' + START + ', m<ROW()), "صف " & m, "")), ""))';

      target.getRange(nextRow, 1, 1, CONFIG.NUM_COLS)
        .setValues([['', name, origUrl, status, dupName, dupUrl, notes, '']]);
      targetUrls.push([origUrl]);
    }

    sheet.deleteRow(r);
    transferred.push(r);
  }

  if (transferred.length && CONFIG.FIX_AFTER_EVERY_MOVE) {
    fixKpiCards_(sheet);
    fixKpiCards_(target);
  }
  return transferred;
}

// -----------------------------------------------------------------------------
// 11) الترتيب الشامل بضغطة زر
// -----------------------------------------------------------------------------
function sortSheetByStatusPriority(sheet) {
  var START = CONFIG.DATA_START_ROW;
  if (!sheet) sheet = SpreadsheetApp.getActiveSheet();
  var lastRow = sheet.getLastRow();
  if (lastRow <= START) return;

  var n = lastRow - START + 1;
  var maxCols = sheet.getMaxColumns();
  var helperCol = Math.max(sheet.getLastColumn() + 1, CONFIG.NUM_COLS + 1);
  if (helperCol > maxCols) sheet.insertColumnAfter(maxCols);

  try {
    var statuses = sheet.getRange(START, CONFIG.STATUS_COL, n, 1).getValues();
    var ranks = [];
    for (var i = 0; i < statuses.length; i++) ranks.push([getStatusRank(statuses[i][0])]);
    sheet.getRange(START, helperCol, n, 1).setValues(ranks);
    sheet.getRange(START, 1, n, helperCol).sort({ column: helperCol, ascending: true });
  } finally {
    try { sheet.deleteColumn(helperCol); } catch (err) { }
  }
  fixKpiCards_(sheet);
}

function sortActiveSheetByPriority() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  sortSheetByStatusPriority(sheet);
  ss.toast("✅ تم ترتيب '" + sheet.getName() + "' حسب الأولوية.", "⚡ اكتمل", 4);
}

function sortSheet1ByPriority() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("الورقة1") || ss.getSheetByName("الورقة 1") || ss.getSheetByName("ورقة 1");
  if (!sheet) { ss.toast("⚠️ مفيش ورقة اسمها 'الورقة1'.", "تنبيه", 5); return; }
  sortSheetByStatusPriority(sheet);
  ss.toast("✅ تم ترتيب '" + sheet.getName() + "'.", "⚡ اكتمل", 4);
}

function sortGitHubSheetByPriority() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = _findGitHubSheet(ss);
  if (!sheet) { ss.toast("⚠️ مفيش ورقة 'جيت هاب Github'.", "تنبيه", 5); return; }
  sortSheetByStatusPriority(sheet);
  ss.toast("✅ تم ترتيب '" + sheet.getName() + "'.", "⚡ اكتمل", 4);
}

// -----------------------------------------------------------------------------
// 12) نقل الصف المحدد يدوياً للصف 7
// -----------------------------------------------------------------------------
function نقل_الصف_المحدد_إلى_الصف_7() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var row = sheet.getActiveRange().getRow();
  var START = CONFIG.DATA_START_ROW;
  var ui = SpreadsheetApp.getUi();

  if (row < START) { ui.alert("اختار صف بيانات (من الصف " + START + " وطالع)."); return; }
  if (row === START) { ui.alert("الصف ده أصلاً في الصف " + START + " ✅"); return; }

  moveRowToDestination(sheet, row, START);
  SpreadsheetApp.flush();
  SpreadsheetApp.getActiveSpreadsheet().toast("⬆️ تم نقل الصف للصف " + START + ".", "تم", 5);
}

// -----------------------------------------------------------------------------
// 13) 🧹 الإصلاح الشامل: إحصائيات + تنسيق شرطي + قوائم منسدلة
// -----------------------------------------------------------------------------
function إصلاح_كل_النطاقات() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheets = ss.getSheets();
  var log = [];

  for (var s = 0; s < sheets.length; s++) {
    var sheet = sheets[s];
    if (!_isRadarSheet(sheet)) continue;
    var name = sheet.getName();

    if (fixKpiCards_(sheet)) log.push("✅ " + name + ": معادلات الإحصائيات ثُبتت بـ INDIRECT");

    var cf = _fixConditionalFormats_(sheet);
    if (cf.fixed > 0) log.push("✅ " + name + ": " + cf.fixed + " نطاق تنسيق شرطي اتربط بصف العنوان (" + cf.details.join("، ") + ")");
    else log.push("• " + name + ": التنسيق الشرطي سليم");

    var dv = _fixStatusDropdown_(sheet);
    if (dv) log.push("✅ " + name + ": القائمة المنسدلة في D امتدت من الصف " + CONFIG.DATA_START_ROW);
  }

  SpreadsheetApp.flush();
  var msg = log.length ? log.join("\n") : "مفيش أوراق بنفس تنسيق الرادار.";
  SpreadsheetApp.getUi().alert("🧹 تقرير الإصلاح\n\n" + msg);
  Logger.log(msg);
}

/**
 * يربط أي نطاق تنسيق شرطي بيبدأ من الصف 7 أو أبعد (D8:D, D10:D, D78:D, B8:B …)
 * بصف العنوان (الصف 6). الإدراج عند الصف 7 بيبقى داخل النطاق فبيتمدد ولا يتزحلق.
 * المعادلات المخصصة بتتعدل بنفس الإزاحة وبتتحمي بـ ROW()>=7.
 */
function _fixConditionalFormats_(sheet) {
  var ANCHOR = CONFIG.HEADER_ROW;
  var START = CONFIG.DATA_START_ROW;
  var maxRows = sheet.getMaxRows();
  var rules = sheet.getConditionalFormatRules();
  var out = [], fixed = 0, details = [];

  for (var i = 0; i < rules.length; i++) {
    var rule = rules[i];
    var ranges = rule.getRanges();
    var newRanges = [];
    var shift = null;           // بكام صف هنمد النطاق لفوق
    var touched = false;

    for (var j = 0; j < ranges.length; j++) {
      var r = ranges[j];
      var rs = r.getRow(), rn = r.getNumRows();
      var isColumnStyle = rn > 1;                     // نطاق عمودي زي D8:D
      if (isColumnStyle && rs >= START && rs <= maxRows) {
        var k = rs - ANCHOR;
        if (shift === null || k < shift) shift = k;
        var grown = Math.min(rn + k, maxRows - ANCHOR + 1);
        newRanges.push(sheet.getRange(ANCHOR, r.getColumn(), grown, r.getNumColumns()));
        details.push(r.getA1Notation() + "→" + newRanges[newRanges.length - 1].getA1Notation());
        touched = true;
      } else {
        newRanges.push(r);
      }
    }

    if (!touched) { out.push(rule); continue; }

    try {
      var builder = rule.copy();
      var bc = rule.getBooleanCondition();
      if (bc && bc.getCriteriaType() === SpreadsheetApp.BooleanCriteria.CUSTOM_FORMULA) {
        var f = String(bc.getCriteriaValues()[0] || "");
        f = _shiftFormulaRows_(f, -shift);
        f = _guardFormula_(f, START);
        builder = builder.whenFormulaSatisfied(f);
      }
      out.push(builder.setRanges(newRanges).build());
      fixed++;
    } catch (err) {
      Logger.log("CF rule rebuild failed: " + err);
      out.push(rule);
    }
  }

  if (fixed > 0) sheet.setConditionalFormatRules(out);
  return { fixed: fixed, details: details };
}

// يزحلق أرقام الصفوف النسبية (مش المثبتة بـ $) في معادلة بمقدار delta — بره النصوص بين علامات التنصيص
function _shiftFormulaRows_(formula, delta) {
  if (!formula || delta === 0) return formula;
  var out = "", inStr = false;
  var i = 0;
  while (i < formula.length) {
    var ch = formula[i];
    if (ch === '"') { inStr = !inStr; out += ch; i++; continue; }
    if (inStr) { out += ch; i++; continue; }
    var m = /^(\$?)([A-Za-z]{1,3})(\$?)(\d+)(?![\w(])/.exec(formula.substr(i));
    var prev = i > 0 ? formula[i - 1] : "";
    if (m && !/[\w.]/.test(prev)) {
      var newRow = m[3] === "$" ? m[4] : String(Math.max(1, parseInt(m[4], 10) + delta));
      out += m[1] + m[2] + m[3] + newRow;
      i += m[0].length;
      continue;
    }
    out += ch; i++;
  }
  return out;
}

// يغلف المعادلة بـ AND(ROW()>=7, …) علشان صف العنوان ما يتلونش
function _guardFormula_(formula, startRow) {
  var body = String(formula).trim();
  if (body.indexOf("ROW()>=") !== -1) return body;
  if (body.charAt(0) === "=") body = body.substring(1);
  return "=AND(ROW()>=" + startRow + "," + body + ")";
}

// يمد القائمة المنسدلة الموجودة في D لكل الصفوف من 7 لآخر الشيت
function _fixStatusDropdown_(sheet) {
  var START = CONFIG.DATA_START_ROW;
  var maxRows = sheet.getMaxRows();
  var lastRow = Math.max(sheet.getLastRow(), START);
  if (maxRows < START) return false;

  var existing = sheet.getRange(START, CONFIG.STATUS_COL, lastRow - START + 1, 1).getDataValidations();
  var template = null;
  for (var v = 0; v < existing.length; v++) {
    if (existing[v][0]) { template = existing[v][0]; break; }
  }
  if (!template) return false;

  var n = maxRows - START + 1;
  var filled = [];
  for (var k = 0; k < n; k++) filled.push([template]);
  sheet.getRange(START, CONFIG.STATUS_COL, n, 1).setDataValidations(filled);
  return true;
}

// -----------------------------------------------------------------------------
// 14) 🔍 فحص سريع
// -----------------------------------------------------------------------------
function فحص_سريع() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  var START = CONFIG.DATA_START_ROW;

  var triggers = ScriptApp.getProjectTriggers();
  var names = [];
  for (var i = 0; i < triggers.length; i++) names.push(triggers[i].getHandlerFunction());

  var bad = [];
  var rules = sheet.getConditionalFormatRules();
  for (var r = 0; r < rules.length; r++) {
    var rs = rules[r].getRanges();
    for (var j = 0; j < rs.length; j++) {
      if (rs[j].getRow() >= START && rs[j].getNumRows() > 1) bad.push(rs[j].getA1Notation());
    }
  }

  var kpi = sheet.getRange(CONFIG.KPI_ROW, 2, 1, 5).getFormulas()[0];
  var kpiOk = kpi.join("").indexOf("INDIRECT") !== -1;

  var msg = [
    "🔎 تقرير الفحص — " + sheet.getName(),
    "──────────────────────",
    "1) المشغل التلقائي: " + (triggers.length ? "مفعّل ✅ (" + names.join(", ") + ")" : "غير مفعّل ⚠️ — اضغط 🚀 تفعيل"),
    "",
    "2) معادلات الإحصائيات B3:F3: " + (kpiOk ? "محمية بـ INDIRECT ✅" : "غير محمية ⚠️ — اضغط 🧹 إصلاح"),
    "",
    "3) نطاقات تنسيق شرطي معرضة للتزحلق (بتبدأ من الصف " + START + " أو بعده):",
    bad.length ? "   • " + bad.join("\n   • ") + "\n   ⚠️ اضغط 🧹 إصلاح كل النطاقات" : "   • لا يوجد ✅ (كلها مربوطة بصف العنوان)",
    "",
    "💡 القاعدة: 🔄 قيد التجربة = الصف 7 دايماً | ✅ يعمل | ❌ لا تعمل | مرفوض | ⏳ لم يتم الفحص = الآخر."
  ].join("\n");

  SpreadsheetApp.getUi().alert(msg);
  Logger.log(msg);
}
