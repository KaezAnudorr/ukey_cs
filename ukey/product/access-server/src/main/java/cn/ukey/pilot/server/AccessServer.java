package cn.ukey.pilot.server;

import cn.ukey.pilot.common.*;
import com.sun.net.httpserver.*;
import javax.net.ssl.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.Set;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

public final class AccessServer implements AutoCloseable {
    private final HttpsServer api;
    private final SSLServerSocket gateway;
    private final Policy policy;
    private final SessionStore sessions;
    private final Audit audit;
    private final AtomicBoolean running = new AtomicBoolean(true);
    private final ExecutorService workers = new ThreadPoolExecutor(32, 32, 60, TimeUnit.SECONDS,
            new ArrayBlockingQueue<>(128), new ThreadPoolExecutor.AbortPolicy());
    private final ExecutorService apiWorkers = new ThreadPoolExecutor(4, 4, 60, TimeUnit.SECONDS,
            new ArrayBlockingQueue<>(64), new ThreadPoolExecutor.AbortPolicy());
    private final Semaphore connections = new Semaphore(8);
    private final Set<Socket> liveSockets = ConcurrentHashMap.newKeySet();
    private final ScheduledExecutorService timer = Executors.newSingleThreadScheduledExecutor();
    private final Thread acceptor;
    public AccessServer(Settings settings) throws Exception {
        settings.requireDemo(); // Before any port is bound or software key loaded.
        policy = new Policy(settings);
        SSLContext tls = TlsSupport.context(settings);
        sessions = new SessionStore(Clock.systemUTC(), Duration.ofSeconds(settings.number("session.ttl.seconds", 60, 1, 3600)));
        audit = new Audit(settings.path("audit.file"));
        api = HttpsServer.create(new InetSocketAddress(settings.loopback("server.host"), settings.number("api.port", 19443, 0, 65535)), 32);
        api.setHttpsConfigurator(new HttpsConfigurator(tls) {
            @Override public void configure(HttpsParameters parameters) {
                SSLParameters p = tls.getDefaultSSLParameters(); p.setProtocols(new String[]{"TLSv1.3"}); p.setNeedClientAuth(true);
                parameters.setSSLParameters(p);
            }
        });
        api.setExecutor(apiWorkers); api.createContext("/", this::api);
        gateway = (SSLServerSocket) tls.getServerSocketFactory().createServerSocket();
        try {
            gateway.setNeedClientAuth(true); gateway.setEnabledProtocols(new String[]{"TLSv1.3"}); gateway.setSoTimeout(500);
            gateway.bind(new InetSocketAddress(settings.loopback("server.host"), settings.number("gateway.port", 19444, 0, 65535)), 32);
            api.start();
        } catch (Exception e) { api.stop(0); gateway.close(); workers.shutdownNow(); apiWorkers.shutdownNow(); timer.shutdownNow(); audit.close(); throw e; }
        timer.scheduleAtFixedRate(() -> {
            for (SessionStore.Grant grant : sessions.expire()) audit.event("session-expired", grant.identity(), grant.resource(), Audit.sessionTag(grant.id()));
        }, 100, 100, TimeUnit.MILLISECONDS);
        acceptor = new Thread(this::accept, "access-gateway"); acceptor.start();
        audit.event("server-start", "", "", "DEMO-TLS1.3-software-certificates");
    }
    public int apiPort() { return api.getAddress().getPort(); }
    public int gatewayPort() { return gateway.getLocalPort(); }
    private void api(HttpExchange exchange) throws IOException {
        String identityId = "";
        try {
            String fingerprint = TlsSupport.peer(((HttpsExchange) exchange).getSSLSession());
            Policy.Identity identity = policy.identity(fingerprint);
            if (identity == null) { respond(exchange, 403, "error=identity-denied\n"); return; }
            identityId = identity.id(); String path = exchange.getRequestURI().getPath();
            if (path.equals("/api/status") && exchange.getRequestMethod().equals("GET")) {
                respond(exchange, 200, "mode=DEMO\nversion=0.2.0-demo\nidentity=" + identity.id() + "\n");
            } else if (path.equals("/api/sessions") && exchange.getRequestMethod().equals("POST")) {
                String resource = exchange.getRequestHeaders().getFirst("X-Resource-Id");
                if (resource == null || policy.resource(resource) == null || !identity.resources().contains(resource)) {
                    audit.event("session-denied", identity.id(), "", "resource-denied"); respond(exchange, 403, "error=resource-denied\n"); return;
                }
                SessionStore.Grant grant = sessions.create(identity, resource);
                audit.event("session-created", identity.id(), resource, Audit.sessionTag(grant.id()));
                respond(exchange, 201, "session=" + grant.id() + "\nresource=" + resource + "\nexpires=" + grant.expires() + "\n");
            } else if (path.startsWith("/api/sessions/") && exchange.getRequestMethod().equals("DELETE")) {
                String id = path.substring("/api/sessions/".length()); sessions.revoke(id, fingerprint);
                audit.event("session-revoked", identity.id(), "", Audit.sessionTag(id)); respond(exchange, 204, "");
            } else if (path.equals("/verifySign") || path.equals("/genRandom") || path.equals("/verifyUser") || path.equals("/deploy")) {
                respond(exchange, 410, "error=legacy-boolean-auth-disabled\n");
            } else respond(exchange, 404, "error=not-found\n");
        } catch (SecurityException e) { respond(exchange, 403, "error=session-denied\n"); }
        catch (Exception e) { audit.event("api-error", identityId, "", e.getClass().getSimpleName()); respond(exchange, 503, "error=service-unavailable\n"); }
        finally { exchange.close(); }
    }
    private static void respond(HttpExchange exchange, int status, String body) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", "text/plain; charset=utf-8");
        exchange.getResponseHeaders().set("Cache-Control", "no-store");
        if (status == 204) { exchange.sendResponseHeaders(status, -1); return; }
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8); exchange.sendResponseHeaders(status, bytes.length); exchange.getResponseBody().write(bytes);
    }
    private void accept() {
        while (running.get()) try {
            SSLSocket socket = (SSLSocket) gateway.accept();
            if (!connections.tryAcquire()) { Wire.close(socket); continue; }
            liveSockets.add(socket);
            try { workers.execute(() -> tunnel(socket)); } catch (RejectedExecutionException e) { liveSockets.remove(socket); connections.release(); Wire.close(socket); }
        } catch (SocketTimeoutException ignored) { }
        catch (IOException e) { if (running.get()) audit.event("accept-error", "", "", e.getClass().getSimpleName()); }
    }
    private void tunnel(SSLSocket client) {
        Socket upstream = null; String session = "", identityId = "", resourceId = ""; boolean established = false;
        ScheduledFuture<?> setupDeadline = null;
        try {
            // An inactivity timeout alone lets a peer retain a slot by dripping bytes.
            setupDeadline = timer.schedule(() -> Wire.close(client), 5, TimeUnit.SECONDS);
            client.setSoTimeout(5000); client.startHandshake();
            String fingerprint = TlsSupport.peer(client.getSession());
            Policy.Identity identity = policy.identity(fingerprint);
            if (identity == null) throw new SecurityException("identity-denied");
            identityId = identity.id(); Wire.Headers headers = Wire.headers(client.getInputStream());
            String[] request = headers.first().split(" ");
            if (request.length != 3 || !request[0].equals("CONNECT") || !request[2].equals("HTTP/1.1")) throw new SecurityException("connect-required");
            Policy.Resource resource = policy.authority(request[1]);
            if (resource == null || !identity.resources().contains(resource.id())) throw new SecurityException("resource-denied");
            resourceId = resource.id(); session = headers.fields().getOrDefault("x-access-session", "");
            sessions.attach(session, fingerprint, resourceId, client);
            client.getOutputStream().write("HTTP/1.1 200 Connection Established\r\n\r\n".getBytes(StandardCharsets.US_ASCII)); client.getOutputStream().flush();
            established = true;
            // This adapter is specific to the bundled sample protocol, not a universal C/S account parser.
            String first = Wire.line(client.getInputStream(), 4096);
            String[] login = first == null ? new String[0] : first.split(" ", 3);
            if (login.length != 3 || !login[0].equals("LOGIN") || !identity.accounts().contains(login[1])) {
                Wire.line(client.getOutputStream(), "ERR ACCOUNT_DENIED"); throw new SecurityException("business-account-denied");
            }
            sessions.require(session, fingerprint, resourceId);
            upstream = new Socket(); upstream.connect(new InetSocketAddress(resource.host(), resource.port()), 3000);
            liveSockets.add(upstream);
            sessions.attach(session, fingerprint, resourceId, upstream);
            Wire.line(upstream.getOutputStream(), first);
            setupDeadline.cancel(false);
            client.setSoTimeout(0);
            audit.event("tunnel-open", identityId, resourceId, Audit.sessionTag(session));
            Pumps.bridge(client, upstream, workers);
        } catch (Exception e) {
            if (e instanceof SecurityException && !established) {
                try { client.getOutputStream().write("HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n".getBytes(StandardCharsets.US_ASCII)); client.getOutputStream().flush(); } catch (Exception ignored) { }
            }
            if (running.get()) audit.event("tunnel-denied-or-closed", identityId, resourceId, e instanceof SecurityException ? e.getMessage() : e.getClass().getSimpleName());
        } finally {
            if (setupDeadline != null) setupDeadline.cancel(false);
            if (running.get() && established) audit.event("tunnel-closed", identityId, resourceId, Audit.sessionTag(session));
            sessions.detach(session, client); if (upstream != null) sessions.detach(session, upstream);
            liveSockets.remove(client); if (upstream != null) liveSockets.remove(upstream); connections.release();
            Wire.close(upstream); Wire.close(client);
        }
    }
    @Override public void close() {
        if (!running.compareAndSet(true, false)) return;
        timer.shutdownNow(); api.stop(0); Wire.close(gateway); sessions.close(); liveSockets.forEach(Wire::close); workers.shutdownNow(); apiWorkers.shutdownNow();
        try { acceptor.join(1500); workers.awaitTermination(2, TimeUnit.SECONDS); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        audit.event("server-stop", "", "", "shutdown"); Wire.close(audit);
    }
}
