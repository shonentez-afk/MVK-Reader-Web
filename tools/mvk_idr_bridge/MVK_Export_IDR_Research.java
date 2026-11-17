//@category MVK_IDR
//@menupath Tools.MVK IDR.Export original MVKView research bundle
// Ghidra 12.2 Java script. READS current Ghidra project; does not modify the program database.
// Exports decompilation, disassembly, incoming/outgoing references, data strings, and Ghidra structures.
// Does NOT start the target EXE, run device measurements, send TCP commands, or require Python/MCP.

import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.decompiler.DecompiledFunction;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Variable;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.data.DataTypeComponent;
import ghidra.program.model.data.DataTypeManager;
import ghidra.program.model.data.Structure;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.ReferenceManager;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import java.io.File;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public class MVK_Export_IDR_Research extends GhidraScript {
    // Conservative bounds: keep one package useful without exporting all Delphi RTL/VCL.
    private static final int MAX_FUNCTIONS = 64;
    private static final int CALLEE_DEPTH = 1;
    private static final int MAX_INSTRUCTIONS_PER_FUNCTION = 1200;
    private static final int MAX_XREFS_PER_FUNCTION = 350;
    private static final int MAX_DATA_STRINGS_PER_FUNCTION = 50;
    private static final int MAX_STRUCTURES = 100;
    private static final int DECOMPILE_TIMEOUT_SECONDS = 15;
    private static final long INTERESTING_CODE_START = 0x007D0000L;
    private static final long INTERESTING_CODE_END = 0x00860000L;

    // Labels confirmed from the original IDR/PAS database (names kept as research hints).
    // All other names and function boundaries MUST be rechecked in Ghidra.
    private static final String[][] SEEDS = {
        {"007D0988", "channel_create"},
        {"007D0B6C", "get_raw_signal"},
        {"007D0C30", "get_signal"},
        {"007D0E58", "get_narrowband_value"},
        {"007D1158", "get_adjusted_envelope_length"},
        {"007D1268", "get_derived_units"},
        {"007D13D4", "get_spectrum"},
        {"007D1998", "check_data_availability"},
        {"007D1A80", "init_params"},
        {"007D1AE0", "invalidate_data"},
        {"007D1B08", "alloc_buffer_chunk"},
        {"007D2398", "process_buffer_chunk"},
        {"008060B0", "thread_create"},
        {"00807A98", "thread_execute"},
        {"00809330", "queue_command"},
        {"00809400", "set_rate"},
        {"00846AD4", "measurement_mode_common"},
        {"00846DCC", "thread_create_callsite"},
        {"00848200", "spectrum_callsite_1"},
        {"0084FB03", "spectrum_callsite_2"},
        {"00848E78", "task_connect_click"},
        {"00848E84", "task_view_click"},
        {"0084B4A4", "adc_paint"},
        {"0084B4AC", "adc_mouse_move"},
        {"0084C910", "spectrum_paint"},
        {"0084C918", "spectrum_mouse_move"},
        {"0084DEA4", "freeze_update_click"},
        {"0084E020", "write_table_click"},
        {"0084E914", "write_adc_click"},
        {"0084E988", "write_values_click"},
        {"0084EAF4", "any_dropdown_click"},
        {"0084ECF0", "pages_change"}
    };
    // Instructions inside GetSpectrum and its math/filter branches: NOT assumed entry points.
    private static final String[][] PROBES = {
        {"007D14AA", "filter_code20"},
        {"007D154B", "spectrum_tag_1"},
        {"007D17E7", "spectrum_tag_2"},
        {"007D1900", "spectrum_tag_3"}
    };

    private static String h(Address a) { return a == null ? "" : String.format(Locale.ROOT, "%08X", a.getOffset()); }
    private static String escaped(String s) {
        if (s == null) return "";
        StringBuilder b = new StringBuilder(s.length() + 16);
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': b.append("\\\\"); break;
                case '"': b.append("\\\""); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default: if (c < 0x20) b.append(String.format(Locale.ROOT, "\\u%04X", (int)c)); else b.append(c);
            }
        }
        return b.toString();
    }
    private static String json(String s) { return "\"" + escaped(s) + "\""; }
    private static String csv(String s) { return "\"" + (s == null ? "" : s.replace("\"", "\"\"").replace("\r", " ").replace("\n", " ")) + "\""; }
    private static String byteHex(byte[] bytes) {
        if (bytes == null) return "";
        StringBuilder sb = new StringBuilder(bytes.length * 3);
        for (byte b : bytes) sb.append(String.format(Locale.ROOT, "%02X ", b & 0xff));
        return sb.toString().trim();
    }
    private static void write(Path file, String value) throws IOException {
        Files.writeString(file, value, StandardCharsets.UTF_8);
    }
    private static boolean isInteresting(Address a) {
        if (a == null) return false;
        long x = a.getOffset();
        return x >= INTERESTING_CODE_START && x < INTERESTING_CODE_END;
    }

    private final Map<String, Function> queue = new LinkedHashMap<>();
    private final Map<String, Integer> depths = new LinkedHashMap<>();
    private final Set<String> referenceEdges = new LinkedHashSet<>();
    private final Set<String> stringEdges = new LinkedHashSet<>();
    private final Set<String> callerEdges = new LinkedHashSet<>();
    private final List<String> probeRows = new ArrayList<>();
    private FunctionManager functions;
    private ReferenceManager refs;
    private Listing listing;
    private Memory memory;
    private SymbolTable symbols;
    private int nDecompiled = 0, nFailures = 0, nUnknown = 0, nCanceled = 0;

    private String symbolAt(Address addr) {
        if (addr == null) return "";
        Function f = functions.getFunctionContaining(addr);
        if (f != null) return f.getName();
        Symbol s = symbols.getPrimarySymbol(addr);
        return s != null ? s.getName() : "";
    }

    private void addTarget(Function f, int depth) {
        if (f == null || !isInteresting(f.getEntryPoint())) return;
        String id = h(f.getEntryPoint());
        if (queue.containsKey(id) || queue.size() >= MAX_FUNCTIONS) return;
        queue.put(id, f);
        depths.put(id, depth);
    }

    private void seedTargets() {
        for (String[] seed : SEEDS) {
            Address addr = toAddr("0x" + seed[0]);
            if (addr == null || !memory.contains(addr)) {
                probeRows.add(csv(seed[0]) + "," + csv(seed[1]) + "," + csv("NOT_IN_IMAGE") + "," + csv(""));
                nUnknown++;
                continue;
            }
            Function f = functions.getFunctionContaining(addr);
            if (f != null) {
                addTarget(f, 0);
                probeRows.add(csv(seed[0]) + "," + csv(seed[1]) + "," + csv("FUNCTION") + "," + csv(h(f.getEntryPoint())));
            }
            else {
                probeRows.add(csv(seed[0]) + "," + csv(seed[1]) + "," + csv("LABEL_OR_UNDEFINED") + "," + csv(symbolAt(addr)));
                nUnknown++;
            }
        }
        for (String[] probe : PROBES) {
            Address addr = toAddr("0x" + probe[0]);
            Function f = addr == null ? null : functions.getFunctionContaining(addr);
            probeRows.add(csv(probe[0]) + "," + csv(probe[1]) + "," + csv(f == null ? "UNDEFINED" : "INSIDE_FUNCTION") + "," + csv(f == null ? symbolAt(addr) : h(f.getEntryPoint())));
        }
    }

    private void captureRefs(Function f, int depth) {
        int written = 0;
        InstructionIterator it = listing.getInstructions(f.getBody(), true);
        while (it.hasNext() && written < MAX_INSTRUCTIONS_PER_FUNCTION && !monitor.isCancelled()) {
            Instruction ins = it.next();
            written++;
            for (Reference r : refs.getReferencesFrom(ins.getAddress())) {
                if (referenceEdges.size() < MAX_FUNCTIONS * MAX_XREFS_PER_FUNCTION) {
                    referenceEdges.add(csv(h(f.getEntryPoint())) + "," + csv(h(r.getFromAddress())) + "," + csv(h(r.getToAddress())) + "," + csv(r.getReferenceType().toString()) + "," + csv(symbolAt(r.getToAddress())));
                }
                if (r.getReferenceType().isCall() && depth < CALLEE_DEPTH) {
                    Function dest = functions.getFunctionContaining(r.getToAddress());
                    if (dest != null && isInteresting(dest.getEntryPoint())) addTarget(dest, depth + 1);
                }
                if (r.getReferenceType().isData()) {
                    Data d = listing.getDataAt(r.getToAddress());
                    if (d != null && d.hasStringValue()) {
                        Object v = d.getValue();
                        if (v != null && v.toString().length() < 1000 && stringEdges.size() < MAX_FUNCTIONS * MAX_DATA_STRINGS_PER_FUNCTION) {
                            stringEdges.add(csv(h(f.getEntryPoint())) + "," + csv(h(r.getFromAddress())) + "," + csv(h(r.getToAddress())) + "," + csv(v.toString()));
                        }
                    }
                }
            }
        }
        int c = 0;
        ReferenceIterator callers = refs.getReferencesTo(f.getEntryPoint());
        while (callers.hasNext() && c < MAX_XREFS_PER_FUNCTION) {
            Reference r = callers.next();
            if (!r.getReferenceType().isCall()) continue;
            c++;
            Function source = functions.getFunctionContaining(r.getFromAddress());
            callerEdges.add(csv(h(f.getEntryPoint())) + "," + csv(h(r.getFromAddress())) + "," + csv(source == null ? "" : h(source.getEntryPoint())) + "," + csv(source == null ? symbolAt(r.getFromAddress()) : source.getName()));
        }
    }

    private String disassemble(Function f) {
        StringBuilder b = new StringBuilder("; MVKView original binary / Ghidra disassembly\n");
        b.append("; Entry: ").append(h(f.getEntryPoint())).append(" Name: ").append(f.getName()).append("\n");
        b.append("; This is static analysis, NOT a device trace.\n\n");
        int count = 0;
        InstructionIterator it = listing.getInstructions(f.getBody(), true);
        while (it.hasNext() && count < MAX_INSTRUCTIONS_PER_FUNCTION && !monitor.isCancelled()) {
            Instruction ins = it.next();
            b.append(h(ins.getAddress())).append("  ");
            try { b.append(String.format(Locale.ROOT, "%-36s", byteHex(ins.getBytes()))); }
            catch (Exception e) { b.append("<bytes unavailable> "); }
            b.append(ins.getMnemonicString());
            for (int n = 0; n < ins.getNumOperands(); n++) {
                b.append(n == 0 ? " " : ", ").append(ins.getDefaultOperandRepresentation(n));
            }
            b.append('\n');
            count++;
        }
        if (it.hasNext()) b.append("; TRUNCATED: instruction cap ").append(MAX_INSTRUCTIONS_PER_FUNCTION).append('\n');
        return b.toString();
    }

    private String decompile(DecompInterface dec, Function f) {
        try {
            DecompileResults res = dec.decompileFunction(f, DECOMPILE_TIMEOUT_SECONDS, monitor);
            if (res != null && res.decompileCompleted()) {
                DecompiledFunction out = res.getDecompiledFunction();
                if (out != null && out.getC() != null && !out.getC().isEmpty()) {
                    nDecompiled++;
                    return "/* Ghidra decompiler (not verified original source). Function " + h(f.getEntryPoint()) + " */\n"
                         + "/* Delphi x87 float10, calling conventions, and structure fields require manual verification. */\n\n"
                         + out.getC();
                }
            }
            nFailures++;
            return "/* Decompilation unavailable: " + (res == null ? "no result" : res.getErrorMessage()) + " */\n";
        }
        catch (Exception ex) {
            nFailures++;
            return "/* Decompiler error (review Ghidra log): " + escaped(ex.toString()) + " */\n";
        }
    }

    private String variableSummary(Function f) {
        StringBuilder b = new StringBuilder("Entry,Name,Signature,Variable,Storage,Type\n");
        try {
            for (Variable v : f.getAllVariables()) {
                b.append(csv(h(f.getEntryPoint()))).append(',')
                 .append(csv(f.getName())).append(',')
                 .append(csv(f.getSignature().toString())).append(',')
                 .append(csv(v.getName())).append(',')
                 .append(csv(v.getVariableStorage().toString())).append(',')
                 .append(csv(v.getDataType().getDisplayName())).append('\n');
            }
        }
        catch (Exception ex) {
            b.append("#variables error: ").append(ex.toString()).append('\n');
        }
        return b.toString();
    }

    private int exportStructures(Path target) throws IOException {
        StringBuilder out = new StringBuilder("Structure,Length,Offset,Field,FieldType,FieldLength\n");
        DataTypeManager manager = currentProgram.getDataTypeManager();
        java.util.Iterator<Structure> all = manager.getAllStructures();
        int included = 0;
        while (all.hasNext() && included < MAX_STRUCTURES && !monitor.isCancelled()) {
            Structure st = all.next();
            String name = st.getName();
            String low = name.toLowerCase(Locale.ROOT);
            if (!(low.contains("mvk") || low.contains("spectrum") || low.contains("grapher") || low.contains("fft") || low.contains("channel") || low.contains("adc"))) continue;
            included++;
            for (DataTypeComponent part : st.getComponents()) {
                out.append(csv(st.getPathName())).append(',').append(st.getLength()).append(',').append(part.getOffset()).append(',')
                   .append(csv(part.getFieldName())).append(',').append(csv(part.getDataType().getDisplayName())).append(',').append(part.getLength()).append('\n');
            }
        }
        write(target, out.toString());
        return included;
    }

    @Override
    public void run() throws Exception {
        if (currentProgram == null) { printerr("MVK EXPORT: Open mvkview.exe in CodeBrowser first."); return; }
        if (!currentProgram.getName().toLowerCase(Locale.ROOT).contains("mvkview")) {
            printerr("MVK EXPORT: Refusing unexpected binary: " + currentProgram.getName()); return;
        }
        if (currentProgram.getImageBase().getOffset() != 0x00400000L) {
            printerr("MVK EXPORT: Wrong image base " + currentProgram.getImageBase() + " (expected 00400000)"); return;
        }
        File outputParent = askDirectory("Where to save private MVK Ghidra research ZIP materials?", "Select folder");
        if (outputParent == null) return;
        String stamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
        Path base = outputParent.toPath().resolve("MVK_Ghidra_Research_" + stamp);
        int suffix = 0;
        while (Files.exists(base)) base = outputParent.toPath().resolve("MVK_Ghidra_Research_" + stamp + "_" + (++suffix));
        Files.createDirectories(base);
        Path exportedFunctions = Files.createDirectories(base.resolve("functions"));
        functions = currentProgram.getFunctionManager();
        refs = currentProgram.getReferenceManager();
        listing = currentProgram.getListing();
        memory = currentProgram.getMemory();
        symbols = currentProgram.getSymbolTable();
        seedTargets();
        StringBuilder index = new StringBuilder("Address,Name,Signature,Depth,Disassembly,Decompilation,Variables\n");
        DecompInterface dec = new DecompInterface();
        if (!dec.openProgram(currentProgram)) {
            printerr("MVK EXPORT: Failed to open decompiler; exporting disassembly anyway.");
        }
        int processed = 0;
        try {
            // Array-like LinkedHashMap is used intentionally: captureRefs may enqueue callees.
            while (processed < MAX_FUNCTIONS && processed < queue.size() && !monitor.isCancelled()) {
                List<String> keys = new ArrayList<>(queue.keySet());
                String key = keys.get(processed);
                Function f = queue.get(key);
                int depth = depths.get(key);
                monitor.setMessage("MVK IDR export " + (processed + 1) + "/" + queue.size() + " " + key + " " + f.getName());
                captureRefs(f, depth);
                String stem = key;
                String disassembly = stem + ".asm";
                String decomp = stem + ".c";
                String vars = stem + "_variables.csv";
                write(exportedFunctions.resolve(disassembly), disassemble(f));
                write(exportedFunctions.resolve(decomp), decompile(dec, f));
                write(exportedFunctions.resolve(vars), variableSummary(f));
                index.append(csv(key)).append(',').append(csv(f.getName())).append(',')
                     .append(csv(f.getSignature().toString())).append(',').append(depth).append(',')
                     .append(csv("functions/" + disassembly)).append(',').append(csv("functions/" + decomp)).append(',')
                     .append(csv("functions/" + vars)).append('\n');
                processed++;
                if (processed % 5 == 0) println("MVK EXPORT: " + processed + " functions captured, pending " + (queue.size() - processed));
            }
        }
        finally { dec.dispose(); }
        if (monitor.isCancelled()) nCanceled = 1;
        write(base.resolve("functions.csv"), index.toString());
        write(base.resolve("probes.csv"), "Address,IDR_Hint,Status,Enclosing_Entry_Or_Symbol\n" + String.join("\n", probeRows) + "\n");
        write(base.resolve("outgoing_references.csv"), "SourceFunction,Instruction,Target,RefType,TargetSymbol\n" + String.join("\n", referenceEdges) + "\n");
        write(base.resolve("incoming_calls.csv"), "TargetFunction,CallInstruction,SourceFunction,SourceName\n" + String.join("\n", callerEdges) + "\n");
        write(base.resolve("referenced_strings.csv"), "Function,Instruction,StringAddress,Value\n" + String.join("\n", stringEdges) + "\n");
        int structures = exportStructures(base.resolve("structures.csv"));
        String manifest = "{\n" +
            "  \"schema\": \"mvk-ghidra-idr-export-v1\",\n" +
            "  \"ghidra_script\": \"MVK_Export_IDR_Research.java\",\n" +
            "  \"program\": " + json(currentProgram.getName()) + ",\n" +
            "  \"image_base\": " + json(h(currentProgram.getImageBase())) + ",\n" +
            "  \"executable_md5\": " + json(currentProgram.getExecutableMD5()) + ",\n" +
            "  \"generated_local\": " + json(stamp) + ",\n" +
            "  \"seed_count\": " + SEEDS.length + ",\n" +
            "  \"resolved_functions_exported\": " + processed + ",\n" +
            "  \"decompiled_functions\": " + nDecompiled + ",\n" +
            "  \"decompilation_failures\": " + nFailures + ",\n" +
            "  \"missing_or_undefined_seed_addresses\": " + nUnknown + ",\n" +
            "  \"outgoing_reference_rows\": " + referenceEdges.size() + ",\n" +
            "  \"incoming_call_rows\": " + callerEdges.size() + ",\n" +
            "  \"data_string_rows\": " + stringEdges.size() + ",\n" +
            "  \"structure_count\": " + structures + ",\n" +
            "  \"canceled\": " + (nCanceled == 1 ? "true" : "false") + ",\n" +
            "  \"limits\": { \"max_functions\": " + MAX_FUNCTIONS + ", \"call_depth\": " + CALLEE_DEPTH +
            ", \"max_instructions_per_function\": " + MAX_INSTRUCTIONS_PER_FUNCTION + " }\n" +
            "}\n";
        write(base.resolve("manifest.json"), manifest);
        write(base.resolve("READ_ME_FIRST_RU.txt"),
            "MVKVIEW GHIDRA IDR RESEARCH v1 | PRIVATE LOCAL EXPORT\n\n" +
            "Этот пакет получен статическим анализом оригинального mvkview.exe в Ghidra 12.2.\n" +
            "Файл не запускался, команды прибору не отправлялись, EXE не модифицировался.\n" +
            "Ghidra декомпиляция НЕ является исходным Delphi-кодом; проверьте float10/x87, Delphi ABI, указатели и поля структур.\n" +
            "functions.csv: функции и пути их исходящих файлов .c/.asm.\n" +
            "probes.csv: известные адреса из IDR; INSIDE_FUNCTION != начало новой функции.\n" +
            "outgoing_references.csv / incoming_calls.csv: статические XREF (не динамическая трасса).\n" +
            "referenced_strings.csv: только явно отмеченные Ghidra строки-данные, связанные с кодом.\n" +
            "structures.csv: только определённые Ghidra структуры, имя которых соответствует MVK/ADC/спектрам.\n" +
            "Бинарник/конфигурация/IP/живые данные устройства в пакет не включаются.\n" +
            "Перед размещением в ПУБЛИЧНОМ GitHub проверьте конфиденциальность ДЕКОМПИЛЯЦИИ.\n" +
            "Рекомендуется передавать ZIP напрямую в приватный чат, НЕ публиковать original decompilation в публичном репозитории.\n");
        println("MVK EXPORT: DONE: " + base.toAbsolutePath());
        println("MVK EXPORT: functions=" + processed + ", decompiled=" + nDecompiled + ", failed=" + nFailures + ", missing seeds=" + nUnknown + ", structures=" + structures + ", canceled=" + (nCanceled==1));
        println("MVK EXPORT: ZIP the generated folder locally and upload it to this chat. Do NOT publish original code to public GitHub.");
    }
}