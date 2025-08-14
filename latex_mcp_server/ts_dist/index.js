#!/usr/bin/env node
const { summarizeText } = require('./functions/textSummary');
const { suggestBibKey } = require('./functions/refTools');

const map = {
  summarizeText,
  suggestBibKey,
};

function main() {
  const [, , fnName, jsonArg] = process.argv;
  if (!fnName) {
    console.error('No function name provided');
    process.exit(1);
  }
  const fn = map[fnName];
  if (!fn) {
    console.log(JSON.stringify({ ok: false, error: `Unknown TS function: ${fnName}` }));
    return;
  }
  let args = {};
  if (jsonArg) {
    try { args = JSON.parse(jsonArg); } catch (e) {
      console.log(JSON.stringify({ ok: false, error: 'Invalid JSON args' }));
      return;
    }
  }
  try {
    const result = fn(args);
    if (result instanceof Promise) {
      result.then(r => {
        console.log(JSON.stringify({ ok: true, result: r }));
      }).catch(err => {
        console.log(JSON.stringify({ ok: false, error: String(err) }));
      });
    } else {
      console.log(JSON.stringify({ ok: true, result }));
    }
  } catch (err) {
    console.log(JSON.stringify({ ok: false, error: String(err) }));
  }
}

main();
