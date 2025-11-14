function doGet(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Sheet1");
  var timestamp = new Date();
  var pump = e.parameter['pump'];
  var heater = e.parameter['heater']; // 🟢 heater state
  var tub = e.parameter['tub'];
  var solar = e.parameter['solar'];
  var delta = e.parameter['delta'];
  var action = e.parameter['action'];
  var note = e.parameter['note'];
  var duration = e.parameter['duration'] || '';

  // Insert new row at top (row 2, keeps headers in row 1)
  sheet.insertRowBefore(2);
  // Now 9 columns: Timestamp | Pump | Heater | Tub | Solar | Delta | Action | Note | Duration
  sheet.getRange(2, 1, 1, 9).setValues([[timestamp, pump, heater, tub, solar, delta, action, note, duration]]);

  // Keep max 500 rows (plus header)
  var lastRow = sheet.getLastRow();
  if (lastRow > 501) sheet.deleteRows(502, lastRow - 501);

  return ContentService.createTextOutput("OK");
}
