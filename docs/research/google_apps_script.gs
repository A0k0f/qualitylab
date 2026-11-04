/**
 * QualityLab Learning Lab: data receiver for Google Sheets.
 *
 * The same script serves both stores: research data (docs/research/SETUP.md) and the participation
 * record (docs/PARTICIPATION.md). Deploy it in TWO separate Google Sheets, each with its own token.
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

// The app sends its column names with every batch; the first batch creates the header row.
function sheet_(fields) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    if (!fields || !fields.length) return null;
    sh = ss.insertSheet(SHEET_NAME);
    sh.getRange(1, 1, sh.getMaxRows(), fields.length).setNumberFormat('@'); // store everything as plain text
    sh.getRange(1, 1, 1, fields.length).setValues([fields]);
    sh.setFrozenRows(1);
  }
  return sh;
}

function header_(sh) {
  return sh.getRange(1, 1, 1, sh.getLastColumn()).getDisplayValues()[0];
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
    const events = body.events || [];
    const sh = sheet_(body.fields || (events.length ? Object.keys(events[0]) : []));
    if (!sh) return out_({ ok: true, added: 0 });
    const head = header_(sh);
    const rows = events.map(ev => head.map(f => safe_(ev[f])));
    if (rows.length) {
      const start = sh.getLastRow() + 1;
      const need = start + rows.length - 1 - sh.getMaxRows();
      if (need > 0) sh.insertRowsAfter(sh.getMaxRows(), Math.max(need, 1000)); // grow in blocks
      const range = sh.getRange(start, 1, rows.length, head.length);
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
  const sh = sheet_(null);
  if (!sh) return out_({ ok: true, events: [] });
  const values = sh.getDataRange().getDisplayValues();
  const head = values.shift();
  const events = values.map(r => {
    const o = {};
    head.forEach((h, i) => { o[h] = r[i]; });
    return o;
  });
  return out_({ ok: true, events: events });
}
