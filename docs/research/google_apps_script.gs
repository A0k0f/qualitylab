/**
 * QualityLab Learning Lab: research data receiver for Google Sheets.
 *
 * Setup (about 10 minutes; full instructions in docs/research/SETUP.md):
 *  1. Create a Google Sheet in the account your IRB approved (ideally your university Google Workspace).
 *  2. Extensions → Apps Script. Delete the sample code and paste this file.
 *  3. Replace TOKEN below with a long random string (the same value goes in the app's secrets as webhook_token).
 *  4. Deploy → New deployment → type "Web app". Execute as: Me. Who has access: Anyone.
 *     Copy the Web app URL (ends in /exec): it goes in the app's secrets as webhook_url.
 *
 * The app sends {"token": ..., "events": [...]} by POST and reads everything back with
 * GET ?token=...&action=export (used by the Instructor dashboard). Requests without the token are refused.
 */
const TOKEN = 'PASTE-A-LONG-RANDOM-TOKEN-HERE';
const SHEET_NAME = 'events';
const FIELDS = ['event_id', 'ts_utc', 'session_id', 'participant_id', 'condition', 'course_code', 'app_version',
                'mission', 'step', 'event_type', 'item_id', 'response', 'correct', 'confidence', 'score',
                'latency_s', 'detail'];

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.getRange(1, 1, sh.getMaxRows(), FIELDS.length).setNumberFormat('@'); // store everything as plain text
    sh.getRange(1, 1, 1, FIELDS.length).setValues([FIELDS]);
    sh.setFrozenRows(1);
  }
  return sh;
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// Values that start with = + - @ could be read as spreadsheet formulas: store them as literal text.
function safe_(v) {
  if (v === undefined || v === null) return '';
  if (typeof v === 'string' && /^[=+\-@]/.test(v)) return "'" + v;
  return v;
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const body = JSON.parse(e.postData.contents);
    if (body.token !== TOKEN) return out_({ ok: false, error: 'invalid token' });
    const rows = (body.events || []).map(ev => FIELDS.map(f => safe_(ev[f])));
    if (rows.length) {
      const sh = sheet_();
      const start = sh.getLastRow() + 1;
      const need = start + rows.length - 1 - sh.getMaxRows();
      if (need > 0) sh.insertRowsAfter(sh.getMaxRows(), Math.max(need, 1000)); // grow in blocks
      const range = sh.getRange(start, 1, rows.length, FIELDS.length);
      range.setNumberFormat('@');
      range.setValues(rows);
    }
    return out_({ ok: true, added: rows.length });
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  if ((e.parameter.token || '') !== TOKEN) return out_({ ok: false, error: 'invalid token' });
  if (e.parameter.action !== 'export') return out_({ ok: true });
  const values = sheet_().getDataRange().getDisplayValues();
  const head = values.shift();
  const events = values.map(r => {
    const o = {};
    head.forEach((h, i) => { o[h] = r[i]; });
    return o;
  });
  return out_({ ok: true, events: events });
}
