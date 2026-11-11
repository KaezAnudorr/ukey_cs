package cn.ukey.pilot.lab;

import cn.ukey.pilot.common.Wire;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Set;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Deliberately has no UKey knowledge. The gateway applies the sample-only account adapter. */
public final class BusinessServer implements AutoCloseable {
    private final ServerSocket listener;
    private final ExecutorService workers = Executors.newFixedThreadPool(16);
    private final Set<Socket> sockets = ConcurrentHashMap.newKeySet();
    private final AtomicBoolean closed = new AtomicBoolean();
    private final AtomicInteger attempts = new AtomicInteger();
    private final String password;
    private final Set<String> accounts;
    public BusinessServer(InetAddress host, int port, Set<String> accounts, String password) throws Exception {
        if (!host.isLoopbackAddress()) throw new IllegalArgumentException("Sample business server is loopback only");
        this.password = password; this.accounts = Set.copyOf(accounts);
        listener = new ServerSocket(); listener.bind(new InetSocketAddress(host, port), 16);
        new Thread(this::accept, "sample-business-listener").start();
    }
    public int port() { return listener.getLocalPort(); }
    public int loginAttempts() { return attempts.get(); }
    private void accept() {
        while (!closed.get()) try {
            Socket socket = listener.accept(); sockets.add(socket); workers.execute(() -> serve(socket));
        } catch (Exception e) { if (!closed.get()) System.err.println("Sample business accept error: " + e.getClass().getSimpleName()); }
    }
    private void serve(Socket socket) {
        try {
            socket.setSoTimeout(5000); String first = Wire.line(socket.getInputStream(), 4096); attempts.incrementAndGet();
            String[] login = first == null ? new String[0] : first.split(" ", 3);
            if (login.length != 3 || !login[0].equals("LOGIN") || !accounts.contains(login[1]) || !MessageDigest.isEqual(
                    login[2].getBytes(StandardCharsets.UTF_8), password.getBytes(StandardCharsets.UTF_8))) {
                Wire.line(socket.getOutputStream(), "ERR LOGIN"); return;
            }
            String user = login[1]; Wire.line(socket.getOutputStream(), "OK " + user); socket.setSoTimeout(0);
            for (String line; (line = Wire.line(socket.getInputStream(), 4096)) != null;) {
                if (line.equals("QUIT")) return;
                if (line.equals("WHOAMI")) Wire.line(socket.getOutputStream(), "USER " + user);
                else if (line.startsWith("ECHO ")) Wire.line(socket.getOutputStream(), line.substring(5));
                else if (line.startsWith("BLOB ")) {
                    int size = Integer.parseInt(line.substring(5));
                    if (size < 0 || size > 8 * 1024 * 1024) throw new IOException("Blob limit");
                    socket.setSoTimeout(5000);
                    byte[] payload = socket.getInputStream().readNBytes(size);
                    if (payload.length != size) throw new EOFException("Truncated blob");
                    Wire.line(socket.getOutputStream(), "BLOB " + size);
                    socket.getOutputStream().write(payload); socket.getOutputStream().flush();
                    socket.setSoTimeout(0);
                }
                else Wire.line(socket.getOutputStream(), "ERR COMMAND"); // Cannot switch account on an established connection.
            }
        } catch (Exception ignored) { }
        finally { sockets.remove(socket); Wire.close(socket); }
    }
    @Override public void close() { if (closed.compareAndSet(false, true)) { Wire.close(listener); sockets.forEach(Wire::close); workers.shutdownNow(); } }
}
