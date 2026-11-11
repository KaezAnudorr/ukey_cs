package cn.ukey.pilot.common;

import java.io.*;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

public final class Settings {
    private final Properties values = new Properties();
    private final Path directory;
    public Settings(Path file) throws IOException {
        directory = file.toAbsolutePath().normalize().getParent();
        try (Reader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8)) { values.load(reader); }
    }
    public String get(String key, String fallback) { return values.getProperty(key, fallback).trim(); }
    public String require(String key) {
        String value = get(key, "");
        if (value.isEmpty()) throw new IllegalArgumentException("Missing configuration: " + key);
        return value;
    }
    public int number(String key, int fallback, int min, int max) {
        int n = Integer.parseInt(get(key, Integer.toString(fallback)));
        if (n < min || n > max) throw new IllegalArgumentException("Out of range: " + key);
        return n;
    }
    public Path path(String key) { return directory.resolve(require(key)).normalize(); }
    public Set<String> set(String key) {
        Set<String> result = new LinkedHashSet<>();
        for (String value : get(key, "").split(",")) if (!value.isBlank()) result.add(value.trim());
        return Set.copyOf(result);
    }
    public char[] password() throws IOException {
        String value = secret("store.password");
        if (value.length() < 16) throw new IllegalArgumentException("Missing or short keystore password");
        return value.toCharArray();
    }
    public String secret(String key) throws IOException {
        Properties secrets = new Properties();
        try (Reader reader = Files.newBufferedReader(path("secrets.file"), StandardCharsets.UTF_8)) { secrets.load(reader); }
        String value = secrets.getProperty(key, "");
        if (value.isEmpty()) throw new IllegalArgumentException("Missing secret: " + key);
        return value;
    }
    public void requireDemo() {
        String mode = require("mode");
        if (!mode.equals("DEMO")) throw new IllegalArgumentException(
                "REAL-PILOT is unavailable: a validated real UKey identity/channel adapter and pilot profile are required. No fallback was started.");
    }
    public InetAddress loopback(String key) throws IOException {
        InetAddress address = InetAddress.getByName(get(key, "127.0.0.1"));
        if (!address.isLoopbackAddress()) throw new IllegalArgumentException("DEMO must bind to loopback: " + key);
        return address;
    }
    public static Path argument(String[] args) {
        for (int i = 0; i + 1 < args.length; i++) if (args[i].equals("--config")) return Path.of(args[i + 1]);
        throw new IllegalArgumentException("Usage: --config <properties file>");
    }
}
