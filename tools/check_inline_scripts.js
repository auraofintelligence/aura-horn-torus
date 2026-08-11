'use strict';

const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const scripts = Array.from(html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi))
  .map((match) => match[1])
  .filter((source) => source.trim());

scripts.forEach((source) => {
  // Parse without executing browser code.
  new Function(source); // eslint-disable-line no-new-func
});

console.log(`INLINE_JS_OK scripts=${scripts.length}`);
