package cn.ukey.pilot.lab;

import cn.ukey.pilot.common.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

/** Independent native workload process. No UKey or authentication-server code is embedded here. */
public final class ProbeMain {
    private record Result(long operations, long bytes, List<Double> latency, String error) { }
    private static String option(String[] args, String name, String fallback) {
        for (int i = 0; i + 1 < args.length; i++) if (args[i].equals(name)) return args[i + 1];
        return fallback;
    }
    private static Socket connect(Settings s, boolean fragmented) throws Exception {
        Socket socket = new Socket();
        try {
            socket.connect(new InetSocketAddress(s.loopback("client.host"), s.number("client.port", 19500, 1, 65535)), 3000);
            socket.setSoTimeout(8000); socket.setTcpNoDelay(true);
            byte[] login = ("LOGIN " + s.require("business.user") + " " + s.secret("business.password") + "\n").getBytes(StandardCharsets.UTF_8);
            if (fragmented) {
                for (byte b : login) { socket.getOutputStream().write(b); socket.getOutputStream().flush(); Thread.sleep(1); }
            } else { socket.getOutputStream().write(login); socket.getOutputStream().flush(); }
            if (!("OK " + s.require("business.user")).equals(Wire.line(socket.getInputStream(), 4096))) throw new IOException("Business login rejected");
            return socket;
        } catch (Exception e) { Wire.close(socket); throw e; }
    }
    private static Result worker(Settings s, int seconds, int bytes, boolean fragmented, boolean halfClose, int index) {
        long operations = 0, volume = 0; List<Double> latency = new ArrayList<>();
        try (Socket socket = connect(s, fragmented)) {
            byte[] payload = new byte[bytes]; new Random(71237L + index).nextBytes(payload);
            long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(seconds);
            do {
                long begin = System.nanoTime();
                // Deliberately coalesce two commands in one write, including UTF-8 text.
                String message = "中文回显-" + index + "-" + operations;
                socket.getOutputStream().write(("WHOAMI\nECHO " + message + "\n").getBytes(StandardCharsets.UTF_8)); socket.getOutputStream().flush();
                if (!("USER " + s.require("business.user")).equals(Wire.line(socket.getInputStream(), 4096))) throw new IOException("Identity crossover");
                if (!message.equals(Wire.line(socket.getInputStream(), 4096))) throw new IOException("UTF-8 framing mismatch");
                Wire.line(socket.getOutputStream(), "BLOB " + bytes);
                if (fragmented) {
                    for (int offset = 0; offset < bytes;) {
                        int count = Math.min(bytes - offset, offset < 32 ? 1 : 4093);
                        socket.getOutputStream().write(payload, offset, count); offset += count;
                    }
                } else socket.getOutputStream().write(payload);
                socket.getOutputStream().flush();
                if (halfClose) socket.shutdownOutput();
                if (!("BLOB " + bytes).equals(Wire.line(socket.getInputStream(), 4096))) throw new IOException("Binary frame mismatch");
                byte[] echoed = socket.getInputStream().readNBytes(bytes);
                if (!MessageDigest.isEqual(payload, echoed)) throw new IOException("Binary payload mismatch");
                operations++; volume += bytes * 2L;
                if (latency.size() < 100000) latency.add((System.nanoTime() - begin) / 1_000_000.0);
                if (seconds > 0) Thread.sleep(50);
            } while (System.nanoTime() < end);
            if (halfClose) { if (socket.getInputStream().read() != -1) throw new IOException("Unexpected data after half close"); }
            else Wire.line(socket.getOutputStream(), "QUIT");
            return new Result(operations, volume, latency, "");
        } catch (Exception e) { return new Result(operations, volume, latency, e.getClass().getSimpleName()); }
    }
    private static Result churn(Settings s, int rounds) {
        long operations = 0; List<Double> latency = new ArrayList<>();
        try {
            for (int i = 0; i < rounds; i++) {
                long begin = System.nanoTime();
                try (Socket socket = connect(s, false)) {
                    Wire.line(socket.getOutputStream(), "WHOAMI");
                    if (!("USER " + s.require("business.user")).equals(Wire.line(socket.getInputStream(), 4096))) throw new IOException("Identity crossover");
                    Wire.line(socket.getOutputStream(), "QUIT");
                    if (socket.getInputStream().read() != -1) throw new IOException("Unexpected data after quit");
                }
                operations++; latency.add((System.nanoTime() - begin) / 1_000_000.0);
            }
            return new Result(operations, 0, latency, "");
        } catch (Exception e) { return new Result(operations, 0, latency, e.getClass().getSimpleName()); }
    }
    public static void main(String[] args) throws Exception {
        Settings s = new Settings(Settings.argument(args)); s.requireDemo();
        Path report = Path.of(option(args, "--report", "probe-result.json"));
        String scenario = option(args, "--scenario", "exercise");
        Map<String,Object> result = new LinkedHashMap<>(); result.put("mode", "DEMO"); result.put("scenario", scenario);
        result.put("physical_ukey", false); boolean success = false; long begin = System.nanoTime();
        try {
            if (scenario.equals("watch")) {
                try (Socket socket = connect(s, false)) {
                    socket.setSoTimeout(20000); System.out.println("READY"); System.out.flush();
                    long ready = System.nanoTime();
                    try { if (socket.getInputStream().read() != -1) throw new IOException("Unexpected business data"); }
                    catch (SocketTimeoutException e) { throw e; }
                    catch (SocketException closed) { }
                    result.put("connected_ms_before_close", (System.nanoTime() - ready) / 1_000_000.0); success = true;
                }
            } else if (scenario.equals("expect-failure")) {
                try (Socket unexpected = connect(s, false)) { result.put("unexpected_business_access", true); }
                catch (IOException expected) { result.put("refusal", expected.getClass().getSimpleName()); success = true; }
            } else if (scenario.equals("exercise") || scenario.equals("half-close") || scenario.equals("churn")) {
                int connections = Integer.parseInt(option(args, "--connections", "1"));
                int seconds = Integer.parseInt(option(args, "--seconds", "0"));
                int bytes = Integer.parseInt(option(args, "--bytes", "262144"));
                int rounds = Integer.parseInt(option(args, "--rounds", "50"));
                if (connections < 1 || connections > 4 || seconds < 0 || seconds > 3600 || bytes < 1 || bytes > 8 * 1024 * 1024 || rounds < 1 || rounds > 10000) throw new IllegalArgumentException("Workload bounds");
                boolean fragmented = Arrays.asList(args).contains("--fragmented");
                boolean halfClose = scenario.equals("half-close");
                if (halfClose && (seconds != 0 || connections != 1)) throw new IllegalArgumentException("Half-close probe is single request only");
                ExecutorService pool = Executors.newFixedThreadPool(connections); List<Future<Result>> futures = new ArrayList<>();
                try {
                    for (int i = 0; i < connections; i++) { final int index = i; futures.add(pool.submit(() -> scenario.equals("churn") ? churn(s, rounds) : worker(s, seconds, bytes, fragmented, halfClose, index))); }
                    long operations = 0, volume = 0; List<Double> latency = new ArrayList<>(); List<String> errors = new ArrayList<>();
                    for (Future<Result> future : futures) {
                        Result r = future.get(scenario.equals("churn") ? 90L : seconds + 25L, TimeUnit.SECONDS); operations += r.operations(); volume += r.bytes(); latency.addAll(r.latency());
                        if (!r.error().isEmpty()) errors.add(r.error());
                    }
                    Collections.sort(latency); success = errors.isEmpty() && operations >= connections;
                    result.put("connections", connections); result.put("requested_seconds", seconds); result.put("operations", operations);
                    result.put("verified_binary_bytes_both_directions", volume); result.put("errors", errors);
                    result.put("latency_samples", latency.size());
                    if (!latency.isEmpty()) { result.put("latency_p50_ms", percentile(latency, .50)); result.put("latency_p95_ms", percentile(latency, .95)); result.put("latency_max_ms", latency.get(latency.size() - 1)); }
                } finally { pool.shutdownNow(); }
            } else throw new IllegalArgumentException("Unknown scenario");
        } catch (Exception e) { result.put("error", e.getClass().getSimpleName()); }
        result.put("elapsed_seconds", (System.nanoTime() - begin) / 1_000_000_000.0); result.put("success", success);
        Files.writeString(report, json(result) + "\n", StandardCharsets.UTF_8);
        System.out.println("PROBE " + scenario + ": " + (success ? "PASS" : "FAIL"));
        if (!success) System.exit(2);
    }
    private static double percentile(List<Double> values, double p) { return values.get(Math.max(0, (int) Math.ceil(values.size() * p) - 1)); }
    private static String json(Object value) {
        if (value instanceof String s) return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + "\"";
        if (value instanceof Map<?,?> map) return "{" + String.join(",", map.entrySet().stream().map(e -> json(e.getKey().toString()) + ":" + json(e.getValue())).toList()) + "}";
        if (value instanceof List<?> list) return "[" + String.join(",", list.stream().map(ProbeMain::json).toList()) + "]";
        return String.valueOf(value);
    }
}
