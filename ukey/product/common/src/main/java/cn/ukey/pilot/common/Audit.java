package cn.ukey.pilot.common;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;

public final class Audit implements AutoCloseable {
    private final BufferedWriter writer;
    public Audit(Path file) throws IOException {
        Files.createDirectories(file.toAbsolutePath().getParent());
        writer = Files.newBufferedWriter(file, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }
    public synchronized void event(String event, String identity, String resource, String reason) {
        try {
            writer.write("{\"at\":\"" + Instant.now() + "\",\"event\":\"" + clean(event) + "\",\"identity\":\"" + clean(identity)
                    + "\",\"resource\":\"" + clean(resource) + "\",\"reason\":\"" + clean(reason) + "\"}\n");
            writer.flush();
        } catch (IOException e) { throw new IllegalStateException("Cannot write audit log", e); }
    }
    private static String clean(String value) {
        if (value == null) return "";
        StringBuilder out = new StringBuilder();
        for (char c : value.toCharArray()) {
            if (c == '"' || c == '\\') out.append('\\').append(c);
            else if (c < 32) out.append(String.format("\\u%04x", (int)c));
            else out.append(c);
        }
        return out.toString();
    }
    public static String sessionTag(String id) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(id.getBytes(StandardCharsets.UTF_8))).substring(0, 16); }
        catch (Exception e) { throw new IllegalStateException(e); }
    }
    @Override public synchronized void close() throws IOException { writer.close(); }
}
