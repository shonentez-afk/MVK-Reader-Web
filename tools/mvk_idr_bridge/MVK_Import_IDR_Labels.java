//@category MVK_IDR
//@menupath Tools.MVK IDR.Import labels from CSV
// Imports IDR labels into the currently open Ghidra PROGRAM DATABASE only.
// Does NOT execute or patch the analyzed mvkview.exe file.
// Java script: works with ordinary ghidraRun.bat, no Python/PyGhidra required.

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolTable;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public class MVK_Import_IDR_Labels extends GhidraScript {

    private static List<String> parseCsvLine(String line) {
        List<String> fields = new ArrayList<>();
        StringBuilder cell = new StringBuilder();
        boolean inQuotes = false;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') {
                if (inQuotes && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    cell.append('"');
                    i++;
                }
                else {
                    inQuotes = !inQuotes;
                }
            }
            else if (c == ',' && !inQuotes) {
                fields.add(cell.toString());
                cell.setLength(0);
            }
            else {
                cell.append(c);
            }
        }
        fields.add(cell.toString());
        return fields;
    }

    private static String safeSymbolName(String raw, String addressHex) {
        String name = raw.trim().replaceAll("[^A-Za-z0-9_$]", "_");
        if (name.length() == 0) {
            return "IDR_" + addressHex.toUpperCase(Locale.ROOT);
        }
        if (!Character.isLetter(name.charAt(0)) && name.charAt(0) != '_') {
            name = "IDR_" + name;
        }
        if (name.length() > 150) {
            name = name.substring(0, 135) + "_" + addressHex.toUpperCase(Locale.ROOT);
        }
        return name;
    }

    private static boolean alreadyPresent(SymbolTable table, Address address, String name) {
        for (Symbol symbol : table.getSymbols(address)) {
            if (symbol.getName().equals(name)) {
                return true;
            }
        }
        return false;
    }

    @Override
    public void run() throws Exception {
        if (currentProgram == null) {
            printerr("MVK IDR: open mvkview.exe in CodeBrowser first.");
            return;
        }
        String programName = currentProgram.getName();
        if (!programName.toLowerCase(Locale.ROOT).contains("mvkview")) {
            printerr("MVK IDR: refusing to label non-MVKView program: " + programName);
            return;
        }
        if (currentProgram.getImageBase().getOffset() != 0x00400000L) {
            printerr("MVK IDR: wrong image base " + currentProgram.getImageBase()
                    + "; expected 00400000. Import aborted.");
            return;
        }

        File file = askFile("Select ghidra_labels.csv (MVK IDR Bridge)", "Open CSV");
        if (file == null) {
            return;
        }
        SymbolTable symbols = currentProgram.getSymbolTable();
        int imported = 0;
        int duplicates = 0;
        int invalid = 0;
        int failed = 0;
        int total = 0;
        boolean canceled = false;

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
            String headerLine = reader.readLine();
            if (headerLine == null) {
                printerr("MVK IDR: CSV is empty.");
                return;
            }
            if (headerLine.startsWith("\uFEFF")) {
                headerLine = headerLine.substring(1);
            }
            List<String> header = parseCsvLine(headerLine);
            int addressColumn = header.indexOf("address");
            int nameColumn = header.indexOf("name");
            if (addressColumn < 0 || nameColumn < 0) {
                printerr("MVK IDR: CSV must have address and name columns.");
                return;
            }
            int required = Math.max(addressColumn, nameColumn);

            String line;
            while ((line = reader.readLine()) != null) {
                if (monitor.isCancelled()) {
                    canceled = true;
                    break;
                }
                if (line.trim().isEmpty()) {
                    continue;
                }
                total++;
                List<String> cells = parseCsvLine(line);
                if (cells.size() <= required) {
                    invalid++;
                    continue;
                }
                String hex = cells.get(addressColumn).trim();
                String rawName = cells.get(nameColumn).trim();
                if (!hex.matches("(?i)[0-9a-f]{8,16}") || rawName.isEmpty()) {
                    invalid++;
                    continue;
                }
                try {
                    Address address = toAddr("0x" + hex);
                    if (address == null || !currentProgram.getMemory().contains(address)) {
                        invalid++;
                        continue;
                    }
                    String name = safeSymbolName(rawName, hex);
                    if (alreadyPresent(symbols, address, name)) {
                        duplicates++;
                        continue;
                    }
                    try {
                        symbols.createLabel(address, name, SourceType.IMPORTED);
                        imported++;
                    }
                    catch (Exception nameCollision) {
                        String unique = name + "_IDR_" + hex.toUpperCase(Locale.ROOT);
                        if (alreadyPresent(symbols, address, unique)) {
                            duplicates++;
                        }
                        else {
                            symbols.createLabel(address, unique, SourceType.IMPORTED);
                            imported++;
                        }
                    }
                }
                catch (Exception e) {
                    failed++;
                    if (failed <= 5) {
                        printerr("MVK IDR: failed row " + total + " at " + hex + ": " + e.getMessage());
                    }
                }
                if (total % 2000 == 0) {
                    monitor.setMessage("MVK IDR: processed " + total + ", imported " + imported);
                }
            }
        }
        println("MVK IDR labels: total=" + total + ", imported=" + imported
                + ", already-present=" + duplicates + ", invalid/outside-image=" + invalid
                + ", failed=" + failed + ", canceled=" + canceled);
        println("Import changes only current Ghidra project, not the original EXE.");
    }
}