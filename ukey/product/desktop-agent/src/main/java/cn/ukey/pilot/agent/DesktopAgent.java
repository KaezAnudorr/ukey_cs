package cn.ukey.pilot.agent;

import cn.ukey.pilot.common.*;
import java.net.*;
import java.util.Set;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

public final class DesktopAgent implements AutoCloseable {
    private final Settings settings;
    private final ControlClient control;
    private final Consumer<String> status;
    private final Set<Socket> sockets = ConcurrentHashMap.newKeySet();
    private final Semaphore slots = new Semaphore(4);
    private final ExecutorService workers = new ThreadPoolExecutor(16, 16, 60, TimeUnit.SECONDS, new ArrayBlockingQueue<>(32));
    private final ScheduledExecutorService timer = Executors.newSingleThreadScheduledExecutor();
    private final AtomicBoolean closed = new AtomicBoolean();
    private ServerSocket listener;
    private ControlClient.Session session;
    public DesktopAgent(Settings settings, Consumer<String> status) throws Exception {
        settings.requireDemo(); this.settings = settings; this.status = status;
        IdentityProvider identity = IdentityProvider.from(settings);
        String host = settings.require("server.host");
        if (!InetAddress.getByName(host).isLoopbackAddress()) throw new IllegalArgumentException("DEMO server must be loopback");
        control = new ControlClient(identity.context(), host, settings.number("api.port", 19443, 1, 65535), settings.number("gateway.port", 19444, 1, 65535));
        status.accept(identity.description());
    }
    public synchronized void start() throws Exception {
        if (session != null || closed.get()) throw new IllegalStateException("Agent already started/closed");
        session = control.login(settings.require("resource.id"));
        try {
            listener = new ServerSocket(); listener.bind(new InetSocketAddress(settings.loopback("agent.host"), settings.number("agent.port", 19500, 0, 65535)), 8);
            new Thread(this::accept, "desktop-agent-listener").start();
            long delay = Math.max(1, java.time.Duration.between(java.time.Instant.now(), session.expires()).toMillis());
            timer.schedule(this::close, delay, TimeUnit.MILLISECONDS);
            status.accept("Authorized DEMO session; local business port=" + listener.getLocalPort() + "; expires=" + session.expires());
        } catch (Exception e) { close(); throw e; }
    }
    public int localPort() { return listener.getLocalPort(); }
    private void accept() {
        while (!closed.get()) try {
            Socket local = listener.accept();
            if (!slots.tryAcquire()) { local.close(); continue; }
            sockets.add(local);
            try { workers.execute(() -> forward(local)); } catch (RejectedExecutionException e) { slots.release(); sockets.remove(local); Wire.close(local); }
        } catch (Exception e) { if (!closed.get()) status.accept("Local listener stopped: " + e.getClass().getSimpleName()); }
    }
    private void forward(Socket local) {
        Socket remote = null;
        try {
            remote = control.tunnel(session.id(), settings.require("resource.authority")); sockets.add(remote);
            if (closed.get()) return;
            Pumps.bridge(local, remote, workers);
        } catch (Exception e) { if (!closed.get()) status.accept("Business connection refused/closed: " + e.getClass().getSimpleName()); }
        finally { Wire.close(local); Wire.close(remote); sockets.remove(local); if (remote != null) sockets.remove(remote); slots.release(); }
    }
    @Override public synchronized void close() {
        if (!closed.compareAndSet(false, true)) return;
        Wire.close(listener); sockets.forEach(Wire::close); timer.shutdownNow(); workers.shutdownNow();
        if (session != null) try { control.logout(session); } catch (Exception e) { status.accept("Local connections closed; server revocation unavailable, expiry remains enforced"); }
        status.accept("Disconnected; local listener and connections closed");
    }
}
