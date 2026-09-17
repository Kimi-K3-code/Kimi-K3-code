/**
 * =============================================================================
 * ⚡ المنظومة الذكية المتكاملة لجوجل شيت (Apps Script v2.2 - المشغل المعتمد)
 * =============================================================================
 * 1. 🎯 الترتيب والنقل الفوري للصفوف حسب أولوية الحالة (العمود D):
 *    - 🔄 قيد التجربة  -> يقفز فوراً لأعلى الشيت (الصف 7)
 *    - ✅ يعمل بنجاح  -> يتجمع تحت "قيد التجربة" مباشرة
 *    - ❌ لا تعمل    -> يتجمع تحت "يعمل بنجاح" مباشرة
 *    - مرفوض         -> يتجمع تحت "لا تعمل" مباشرة
 *    - ⏳ لم يتم الفحص -> في ذيل الشيت تحت "مرفوض"
 * 
 * 2. 🐙 النقل اللحظي لمستودعات جيت هاب (العمود C) لورقة جيت هاب تلقائياً.
 * 3. ⚡ تفعيل المشغل المعتمد (Installable Trigger) لتجاوز قيود الصلاحيات نهائياً.
 * =============================================================================
 */

// -----------------------------------------------------------------------------
// 1. القائمة العلوية التلقائية عند فتح الشيت
// -----------------------------------------------------------------------------
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu("⚡ أدوات الترتيب الذكي")
    .addItem("🚀 تفعيل الترتيب التلقائي الفوري (مرة واحدة)", "تفعيل_الترتيب_التلقائي")
    .addSeparator()
    .addItem("🔄 ترتيب الشيت بالكامل حسب الأولوية", "sortActiveSheetByPriority")
    .addItem("📋 ترتيب 'الورقة1' حسب الأولوية", "sortSheet1ByPriority")
    .addItem("🐙 ترتيب 'جيت هاب Github' حسب الأولوية", "sortGitHubSheetByPriority")
    .addToUi();
}

// -----------------------------------------------------------------------------
// 2. دالة التفعيل الفوري للمشغل المصرح له (شغلها مرة واحدة من زر تنفيذ!)
// -----------------------------------------------------------------------------
function تفعيل_الترتيب_التلقائي() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // مسح أي مشغلات قديمة منعاً للتكرار
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    ScriptApp.deleteTrigger(triggers[i]);
  }
  
  // إنشاء المشغل التلقائي المعتمد بصلاحيات كاملة
  ScriptApp.newTrigger("installedOnEdit")
    .forSpreadsheet(ss)
    .onEdit()
    .create();
    
  ss.toast("🎉 تم تفعيل الترتيب التلقائي الفوري بصلاحيات كاملة بنجاح! من الآن كل تعديل سيتحرك فورا!", "⚡ تم التفعيل", 6);
  Logger.log("✅ تم تثبيت المشغل التلقائي المعتمد بنجاح!");
}

// -----------------------------------------------------------------------------
// 3. دالة المعالجة الرئيسية (تشتغل بصلاحيات المشغل المعتمد)
// -----------------------------------------------------------------------------
function installedOnEdit(e) {
  processSheetEdit(e);
}

// دالة احتياطية للمشغل البسيط
function onEdit(e) {
  var triggers = ScriptApp.getProjectTriggers();
  if (triggers.length > 0) return; // منع التكرار إذا كان المشغل المعتمد مفعلاً
  processSheetEdit(e);
}

// -----------------------------------------------------------------------------
// 4. المنطق المركزي لمعالجة أي تعديل في الشيت
// -----------------------------------------------------------------------------
function processSheetEdit(e) {
  if (!e || !e.range) return;
  
  var range = e.range;
  var sheet = range.getSheet();
  var sheetName = sheet.getName().trim();
  
  var startRow = range.getRow();
  var numRows = range.getNumRows();
  var startCol = range.getColumn();
  var numCols = range.getNumColumns();
  
  // تجاهل صفوف العناوين العلوية (صفوف 1 إلى 6)
  if (startRow + numRows - 1 < 7) return;
  
  var ss = e.source;
  
  // أ. فحص روابط جيت هاب في العمود C (رقم 3)
  var isSheet1 = (sheetName.indexOf("ورقة") !== -1 || sheetName.indexOf("الورقة") !== -1 || sheetName.toLowerCase().indexOf("sheet1") !== -1);
  var transferredRows = [];
  if (isSheet1 && startCol <= 3 && (startCol + numCols - 1) >= 3) {
    transferredRows = handleGitHubTransfer(ss, sheet, startRow, numRows);
  }
  
  // ب. فحص تغيير الحالة في العمود D (رقم 4) -> نقل وترتيب فوري
  if (startCol <= 4 && (startCol + numCols - 1) >= 4) {
    if (numRows === 1 && startRow >= 7) {
      if (!transferredRows || transferredRows.indexOf(startRow) === -1) {
        var statusCell = sheet.getRange(startRow, 4).getValue();
        if (statusCell && statusCell.toString().trim() !== "") {
          handleStatusChange(sheet, startRow, statusCell);
        }
      }
    }
  }
}

// -----------------------------------------------------------------------------
// 5. تحديد رتبة الحالة بدقة (1 إلى 5)
// -----------------------------------------------------------------------------
function getStatusRank(status) {
  if (!status) return 5;
  var s = status.toString().trim();
  if (s.indexOf("قيد التجربة") !== -1) return 1;
  if (s.indexOf("يعمل بنجاح") !== -1) return 2;
  if (s.indexOf("لا تعمل") !== -1 || s.indexOf("لا يعمل") !== -1) return 3;
  if (s.indexOf("مرفوض") !== -1) return 4;
  return 5;
}

// -----------------------------------------------------------------------------
// 6. تحديد الوجهة المستهدفة للصف ونقله
// -----------------------------------------------------------------------------
function handleStatusChange(sheet, editedRow, newStatus) {
  if (editedRow < 7) return;
  var targetRank = getStatusRank(newStatus);
  var lastRow = sheet.getLastRow();
  if (lastRow < 7) return;
  
  var destRow;
  if (targetRank === 1) {
    // 🔄 قيد التجربة: يقفز دائماً إلى أعلى الجدول في الصف 7
    destRow = 7;
  } else {
    var statuses = sheet.getRange(7, 4, lastRow - 6, 1).getValues();
    var firstGreater = null;
    for (var i = 0; i < statuses.length; i++) {
      var r = i + 7;
      if (r === editedRow) continue;
      var rk = getStatusRank(statuses[i][0]);
      if (rk > targetRank) {
        firstGreater = r;
        break;
      }
    }
    if (firstGreater !== null) {
      destRow = firstGreater;
    } else {
      destRow = lastRow + 1;
    }
  }
  
  if (editedRow === destRow) return;
  if (editedRow < destRow && destRow === editedRow + 1) return;
  
  moveRowToDestination(sheet, editedRow, destRow);
}

// -----------------------------------------------------------------------------
// 7. محرك النقل الآمن متعدد الطبقات
// -----------------------------------------------------------------------------
function moveRowToDestination(sheet, sourceRow, destRow) {
  // المحاولة 1: النقل المباشر بنطاق الصف الكامل A1
  try {
    var rowRange = sheet.getRange(sourceRow + ":" + sourceRow);
    sheet.moveRows(rowRange, destRow);
    return;
  } catch (e1) {
    Logger.log("moveRows A1 error: " + e1);
  }
  
  // المحاولة 2: النقل بنطاق الأعمدة الكامل
  try {
    var maxCols = sheet.getMaxColumns();
    var fullRange = sheet.getRange(sourceRow, 1, 1, maxCols);
    sheet.moveRows(fullRange, destRow);
    return;
  } catch (e2) {
    Logger.log("moveRows full-width error: " + e2);
  }
  
  // المحاولة 3: النقل المضمون 100% (Insert -> MoveTo -> Delete)
  try {
    var lastCol = Math.max(sheet.getLastColumn(), 8);
    if (destRow < sourceRow) {
      sheet.insertRowBefore(destRow);
      var src = sheet.getRange(sourceRow + 1, 1, 1, lastCol);
      var dst = sheet.getRange(destRow, 1);
      src.moveTo(dst);
      sheet.deleteRow(sourceRow + 1);
    } else {
      sheet.insertRowAfter(destRow);
      var src = sheet.getRange(sourceRow, 1, 1, lastCol);
      var dst = sheet.getRange(destRow + 1, 1);
      src.moveTo(dst);
      sheet.deleteRow(sourceRow);
    }
  } catch (e3) {
    Logger.log("moveTo fallback error: " + e3);
  }
}

// -----------------------------------------------------------------------------
// 8. نقل مستودعات جيت هاب لورقة جيت هاب
// -----------------------------------------------------------------------------
function handleGitHubTransfer(ss, sheet, startRow, numRows) {
  var targetSheet = ss.getSheetByName("جيت هاب  Github") || ss.getSheetByName("جيت هاب Github");
  if (!targetSheet) {
    var sheets = ss.getSheets();
    for (var i = 0; i < sheets.length; i++) {
      var sName = sheets[i].getName();
      if (sName.indexOf("جيت هاب") !== -1 || sName.toLowerCase().indexOf("github") !== -1) {
        targetSheet = sheets[i];
        break;
      }
    }
  }
  if (!targetSheet) return [];
  
  var transferred = [];
  for (var r = startRow + numRows - 1; r >= Math.max(startRow, 7); r--) {
    var urlCell = sheet.getRange(r, 3).getValue();
    var url = urlCell ? urlCell.toString().trim().toLowerCase() : "";
    if (!url) continue;
    
    if (url.indexOf("github.com") !== -1 || url.indexOf("github.io") !== -1) {
      var rowValues = sheet.getRange(r, 1, 1, 8).getValues()[0];
      var name = rowValues[1];
      var origUrl = rowValues[2];
      var status = rowValues[3] || "⏳ لم يتم الفحص";
      var notes = rowValues[6] || "";
      
      var targetUrls = targetSheet.getRange("C7:C").getValues();
      var exists = false;
      for (var i = 0; i < targetUrls.length; i++) {
        var tUrl = targetUrls[i][0].toString().trim().toLowerCase();
        if (tUrl && tUrl === url) {
          exists = true;
          break;
        }
      }
      
      if (!exists) {
        var lastRow = targetSheet.getLastRow();
        var nextRow = Math.max(lastRow + 1, 7);
        var dupName = '=IF(OR(ISBLANK(B' + nextRow + '), B' + nextRow + '=""), "", IFERROR(LET(clean_n, LOWER(TRIM(CLEAN(B' + nextRow + '))), prev, MAP(INDIRECT("B$1:B" & (ROW()-1)), LAMBDA(x, LOWER(TRIM(CLEAN(x))))), m, MATCH(clean_n, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))';
        var dupUrl = '=IF(OR(ISBLANK(C' + nextRow + '), C' + nextRow + '=""), "", IFERROR(LET(clean_d, IFERROR(REGEXEXTRACT(LOWER(TRIM(C' + nextRow + ')), "(?:github\\.com/[^/?#]+(?:/[^/?#]+)?|[^/?#]+\\.github\\.io(?:/[^/?#]+)?)"), REGEXEXTRACT(REGEXREPLACE(LOWER(TRIM(C' + nextRow + ')), "^https?://((www|app|platform|dashboard|router|api)\\.)?|^((www|app|platform|dashboard|router|api)\\.)?", ""), "^([^/?#:]+)"), "")))), m, MATCH(clean_d, prev, 0), IF(AND(m>=7, m<ROW()), "صف " & m, "")), ""))';
        var newRowData = ['', name, origUrl, status, dupName, dupUrl, notes, ''];
        targetSheet.getRange(nextRow, 1, 1, 8).setValues([newRowData]);
      }
      
      sheet.deleteRow(r);
      transferred.push(r);
    }
  }
  return transferred;
}

// -----------------------------------------------------------------------------
// 9. دوال الترتيب الشامل للشيت بالكامل
// -----------------------------------------------------------------------------
function sortSheetByStatusPriority(sheet) {
  if (!sheet) sheet = SpreadsheetApp.getActiveSheet();
  var lastRow = sheet.getLastRow();
  if (lastRow < 8) return;
  
  var numDataRows = lastRow - 6;
  var maxCols = sheet.getMaxColumns();
  var helperCol = sheet.getLastColumn() + 1;
  if (helperCol > maxCols) {
    sheet.insertColumnAfter(maxCols);
  }
  
  try {
    var statuses = sheet.getRange(7, 4, numDataRows, 1).getValues();
    var ranks = [];
    for (var i = 0; i < statuses.length; i++) {
      ranks.push([getStatusRank(statuses[i][0])]);
    }
    sheet.getRange(7, helperCol, numDataRows, 1).setValues(ranks);
    sheet.getRange(7, 1, numDataRows, helperCol).sort({column: helperCol, ascending: true});
  } finally {
    try {
      sheet.deleteColumn(helperCol);
    } catch(e) {}
  }
}

function sortActiveSheetByPriority() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  sortSheetByStatusPriority(sheet);
  ss.toast("✅ تم ترتيب ورقة '" + sheet.getName() + "' بالكامل حسب الأولويات بنجاح!", "⚡ اكتمل الترتيب", 4);
}

function sortSheet1ByPriority() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("الورقة1") || ss.getSheetByName("الورقة 1") || ss.getSheetByName("ورقة 1");
  if (sheet) {
    sortSheetByStatusPriority(sheet);
    ss.toast("✅ تم ترتيب ورقة '" + sheet.getName() + "' بنجاح!", "⚡ اكتمل الترتيب", 4);
  }
}

function sortGitHubSheetByPriority() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("جيت هاب  Github") || ss.getSheetByName("جيت هاب Github");
  if (sheet) {
    sortSheetByStatusPriority(sheet);
    ss.toast("✅ تم ترتيب ورقة '" + sheet.getName() + "' بنجاح!", "⚡ اكتمل الترتيب", 4);
  }
}
