/* Automatic x86 MVKView GetSpectrum evidence, no x32dbg. */
'use strict';
const SITES = __MVK_SITES_JSON__;
const ALLOW_ARRAYS = __MVK_ARRAYS_BOOL__;
const MAX_HITS_PER_SITE = 400;
const MIN_HIT_GAP_MS = 350;
const MIN_ARRAY_GAP_MS = 8000;
const MAX_ARRAY_TOTAL_BYTES = 16 * 1024 * 1024;
const MAX_ARRAY_LENGTH = 1024 * 1024;
let arrayTotal = 0;
const counters = {};
const lastEvent = {};
const lastArray = {};
const listeners = [];
function safeRange(pointer, length, protection) {
  try {
    if (pointer.isNull() || length < 1 || length > MAX_ARRAY_LENGTH) return false;
    const range = Process.findRangeByAddress(pointer);
    if (range === null || (protection === 'r' && range.protection.indexOf('r') === -1) || (protection === 'x' && range.protection.indexOf('x') === -1)) return false;
    return pointer.add(length).compare(range.base.add(range.size)) <= 0;
  } catch (_) { return false; }
}
function readHex(address, n) {
  try {
    if (!safeRange(address, n, 'r')) return null;
    const arr = new Uint8Array(address.readByteArray(n));
    let hex = '';
    for (let i = 0; i < arr.length; i++) hex += ('0' + arr[i].toString(16)).slice(-2);
    return hex;
  } catch (_) { return null; }
}
function read32(address) {
  try { return safeRange(address, 4, 'r') ? address.readU32() : null; }
  catch (_) { return null; }
}
function maybeArray(site, ctx, n, timestamp) {
  if (!ALLOW_ARRAYS || arrayTotal >= MAX_ARRAY_TOTAL_BYTES ||
      (timestamp - (lastArray[site.name] || 0) < MIN_ARRAY_GAP_MS)) return;
  let offset = null;
  let count = null;
  let type = null;
  if (site.name === 'pre_fft') {
    offset = -0x2C; count = n; type = 'pre_fft_float32_candidate';
  } else if (site.name === 'power_after_mode_y') {
    offset = -0x30; count = n >>> 1; type = 'display_y_float32_candidate';
  } else return;
  if (n === null || n < 4096 || n > 262144 || (n & (n - 1)) !== 0) return;
  const length = count * 4;
  if (length > MAX_ARRAY_LENGTH || arrayTotal + length > MAX_ARRAY_TOTAL_BYTES) return;
  try {
    const local = ptr(ctx.ebp).add(offset);
    const raw = read32(local);
    if (raw === null || raw < 0x10000) return;
    const bufferPtr = ptr(raw);
    if (!safeRange(bufferPtr, length, 'r')) return;
    const bytes = bufferPtr.readByteArray(length);
    send({kind: 'array', site: site.name, timestamp_ms: timestamp,
          thread_id: Process.getCurrentThreadId(), array_type: type,
          byte_length: length, n: n}, bytes);
    arrayTotal += length;
    lastArray[site.name] = timestamp;
  } catch (_) { /* invalid pointer = no array evidence */ }
}
try {
  if (Process.arch !== 'ia32') throw new Error('Expected original x86 (ia32) MVKView');
  const module = Process.getModuleByName('mvkview.exe');
  if (module === null) throw new Error('Original executable not present');
  // Validate ALL six original bytes before any interception is installed.
  for (const site of SITES) {
    const address = module.base.add(site.rva);
    if (site.rva < 0 || site.rva + site.signature.length / 2 > module.size ||
        !safeRange(address, site.signature.length / 2, 'x') ||
        readHex(address, site.signature.length / 2) !== site.signature) {
      throw new Error('Original x86 opcode mismatch at ' + site.name);
    }
  }
  for (const site of SITES) {
    counters[site.name] = 0;
    const address = module.base.add(site.rva);
    listeners.push(Interceptor.attach(address, {
      onEnter() {
        try {
          if (counters[site.name] >= MAX_HITS_PER_SITE) return;
          const timestamp = Date.now();
          if (timestamp - (lastEvent[site.name] || 0) < MIN_HIT_GAP_MS) return;
          lastEvent[site.name] = timestamp;
          counters[site.name]++;
          const context = this.context;
          const ebx = ptr(context.ebx), ebp = ptr(context.ebp);
          const n = read32(ebx.add(4));
          const mode = read32(ebx.add(0x18));
          const envCode = read32(ebx.add(8));
          const sp = read32(ebp.sub(4));
          const storage = (sp === null || sp < 0x10000) ? null : readHex(ptr(sp), 56);
          const regs = {};
          for (const key of ['eax','ebx','ecx','edx','esi','edi','ebp','esp','eip']) {
            if (context[key] !== undefined) regs[key] = context[key].toString();
          }
          send({kind: 'hit', site: site.name, timestamp_ms: timestamp,
                thread_id: Process.getCurrentThreadId(), registers: regs,
                params_hex: readHex(ebx, 60),
                stack_hex: readHex(ebp.sub(48), 48), storage_hex: storage,
                n: n, mode: mode, envelope_code: envCode});
          maybeArray(site, context, n, timestamp);
        } catch (_) { /* never block original math on collection failure */ }
      }
    }));
  }
  send({kind: 'ready', architecture: Process.arch, hook_count: listeners.length,
        module_base: module.base.toString()});
} catch (e) {
  for (const listener of listeners) {
    try { listener.detach(); } catch (_) {}
  }
  send({kind: 'trace_error', reason: String(e).slice(0, 240)});
}