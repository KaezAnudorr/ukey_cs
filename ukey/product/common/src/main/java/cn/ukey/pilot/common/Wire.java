package cn.ukey.pilot.common;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Bounded application framing. Authentication/encryption are provided by standard TLS. */
public final class Wire {
    private Wire() { }
    public static String line(InputStream in, int limit) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        for (int n; (n = in.read()) != -1;) {
            if (n == '\n') return bytes.toString(StandardCharsets.UTF_8).replaceFirst("\\r$", "");
            if (bytes.size() >= limit) throw new IOException("Line limit exceeded");
            bytes.write(n);
        }
        if (bytes.size() == 0) return null;
        throw new EOFException("Truncated line");
    }
    public static void line(OutputStream out, String value) throws IOException {
        out.write((value + "\n").getBytes(StandardCharsets.UTF_8)); out.flush();
    }
    public record Headers(String first, Map<String, String> fields) { }
    public static Headers headers(InputStream in) throws IOException {
        String first = line(in, 2048);
        if (first == null) throw new EOFException();
        Map<String, String> fields = new HashMap<>(); int size = first.length();
        for (int i = 0; i < 32; i++) {
            String next = line(in, 2048);
            if (next == null) throw new EOFException();
            size += next.length();
            if (size > 8192) throw new IOException("Header limit exceeded");
            if (next.isEmpty()) return new Headers(first, Map.copyOf(fields));
            int colon = next.indexOf(':');
            if (colon <= 0) throw new IOException("Invalid header");
            String name = next.substring(0, colon).toLowerCase(Locale.ROOT);
            if (fields.put(name, next.substring(colon + 1).trim()) != null) throw new IOException("Duplicate header");
        }
        throw new IOException("Header count exceeded");
    }
    public static Properties properties(String text) throws IOException {
        Properties p = new Properties(); p.load(new StringReader(text)); return p;
    }
    public static void close(AutoCloseable closeable) { if (closeable != null) try { closeable.close(); } catch (Exception ignored) { } }
}
