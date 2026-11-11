package cn.ukey.pilot.server;

import cn.ukey.pilot.common.*;
import cn.ukey.pilot.agent.*;
import cn.ukey.pilot.lab.BusinessServer;
import org.junit.jupiter.api.*;
import javax.net.ssl.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;

class AccessIntegrationTest {
    static Path fixtures;
    static char[] storePassword;
    static String businessPassword;
    Path work;
    BusinessServer business;
    AccessServer server;
    ControlClient alice;

    @BeforeAll static void prepareCertificates() throws Exception {
        fixtures = Files.createTempDirectory("cs-ukey-test-pki-");
        Path root = Path.of("..").toAbsolutePath().normalize();
        String python = System.getenv().getOrDefault("PYTHON", System.getProperty("os.name").startsWith("Windows") ? "python" : "python3");
        Path log = Files.createTempFile("cs-ukey-keytool-", ".log");
        Process process = new ProcessBuilder(python, root.resolve("tools/manage.py").toString(), "demo-init", "--dir", fixtures.toString()).redirectErrorStream(true).redirectOutput(log.toFile()).start();
        assertTrue(process.waitFor(120, TimeUnit.SECONDS), "Certificate setup timed out");
        assertEquals(0, process.exitValue(), () -> "Fixture initialization failed; inspect " + log);
        Properties secrets = load(fixtures.resolve("secrets.properties"));
        storePassword = secrets.getProperty("store.password").toCharArray(); businessPassword = secrets.getProperty("business.password");
        Files.deleteIfExists(log);
    }
    static Properties load(Path file) throws IOException {
        Properties properties = new Properties(); try (Reader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8)) { properties.load(reader); } return properties;
    }
    Path config(String name, Properties properties) throws IOException {
        Path file = work.resolve(name); try (Writer writer = Files.newBufferedWriter(file, StandardCharsets.UTF_8)) { properties.store(writer, "Test only"); } return file;
    }
    @BeforeEach void startServices() throws Exception {
        work = Files.createTempDirectory("cs-ukey-case-");
        business = new BusinessServer(InetAddress.getLoopbackAddress(), 0, Set.of("alice", "bob"), businessPassword);
        startAccess(30);
    }
    void startAccess(int ttl) throws Exception {
        startAccess(ttl, "server");
    }
    void startAccess(int ttl, String certificate) throws Exception {
        Properties properties = load(fixtures.resolve("server.properties"));
        properties.setProperty("api.port", "0"); properties.setProperty("gateway.port", "0");
        properties.setProperty("resource.sample.port", Integer.toString(business.port()));
        properties.setProperty("session.ttl.seconds", Integer.toString(ttl));
        properties.setProperty("tls.keystore", fixtures.resolve(certificate + ".p12").toString());
        properties.setProperty("tls.truststore", fixtures.resolve("trust.p12").toString());
        properties.setProperty("secrets.file", fixtures.resolve("secrets.properties").toString());
        properties.setProperty("audit.file", work.resolve("audit.jsonl").toString());
        server = new AccessServer(new Settings(config("server.properties", properties)));
        alice = client("alice");
    }
    ControlClient client(String name) throws Exception {
        SSLContext tls = TlsSupport.context(name == null ? null : fixtures.resolve(name + ".p12"), fixtures.resolve("trust.p12"), storePassword);
        return new ControlClient(tls, "localhost", server.apiPort(), server.gatewayPort());
    }
    String login(Socket socket, String account, String password) throws Exception {
        socket.setSoTimeout(4000); Wire.line(socket.getOutputStream(), "LOGIN " + account + " " + password);
        return Wire.line(socket.getInputStream(), 4096);
    }
    @Test void validMutualTlsSessionForwardsBusinessProtocol() throws Exception {
        ControlClient.Session session = alice.login("sample");
        try (Socket tunnel = alice.tunnel(session.id(), "sample-business:443")) {
            assertEquals("OK alice", login(tunnel, "alice", businessPassword));
            Wire.line(tunnel.getOutputStream(), "WHOAMI"); assertEquals("USER alice", Wire.line(tunnel.getInputStream(), 4096));
            Wire.line(tunnel.getOutputStream(), "ECHO unchanged-business-data"); assertEquals("unchanged-business-data", Wire.line(tunnel.getInputStream(), 4096));
        }
        assertEquals(1, business.loginAttempts());
    }
    @Test void aTrustedCertificateStillNeedsAnIdentityMapping() throws Exception {
        assertEquals(403, client("unmapped").request("POST", "/api/sessions", "sample").statusCode());
        assertEquals(0, business.loginAttempts());
    }
    @Test void noClientCertificateCannotAuthenticate() throws Exception { assertThrows(IOException.class, () -> client(null).login("sample")); }
    @Test void anUntrustedClientCertificateCannotAuthenticate() throws Exception { assertThrows(IOException.class, () -> client("untrusted").login("sample")); }
    @Test void anExpiredClientCertificateCannotAuthenticate() throws Exception { assertThrows(IOException.class, () -> client("expired").login("sample")); }
    @Test void serverHostnameIsVerified() throws Exception {
        server.close(); startAccess(30, "server-wronghost");
        // Exercise the actual product paths, without configuring TLS in the test client.
        assertThrows(IOException.class, () -> alice.login("sample"));
        assertThrows(IOException.class, () -> alice.tunnel("A".repeat(43), "sample-business:443"));
        assertEquals(0, business.loginAttempts());
    }
    @Test void missingSessionCannotOpenAResource() throws Exception {
        assertThrows(SecurityException.class, () -> alice.tunnel("A".repeat(43), "sample-business:443")); assertEquals(0, business.loginAttempts());
    }
    @Test void aCopiedSessionCannotBeUsedWithAnotherCertificate() throws Exception {
        ControlClient.Session session = alice.login("sample");
        assertThrows(SecurityException.class, () -> client("bob").tunnel(session.id(), "sample-business:443")); assertEquals(0, business.loginAttempts());
    }
    @Test void clientCannotSelectAnArbitraryDestination() throws Exception {
        ControlClient.Session session = alice.login("sample");
        assertThrows(SecurityException.class, () -> alice.tunnel(session.id(), "169.254.169.254:80"));
        assertThrows(SecurityException.class, () -> alice.login("unconfigured")); assertEquals(0, business.loginAttempts());
    }
    @Test void anUnauthorizedBusinessAccountIsRejectedBeforeUpstreamLogin() throws Exception {
        ControlClient.Session session = alice.login("sample");
        try (Socket tunnel = alice.tunnel(session.id(), "sample-business:443")) {
            assertEquals("ERR ACCOUNT_DENIED", login(tunnel, "bob", businessPassword));
        }
        assertEquals(0, business.loginAttempts());
    }
    @Test void originalBusinessPasswordCheckIsPreserved() throws Exception {
        ControlClient.Session session = alice.login("sample");
        try (Socket tunnel = alice.tunnel(session.id(), "sample-business:443")) { assertEquals("ERR LOGIN", login(tunnel, "alice", "invalid-test-password")); }
        assertEquals(1, business.loginAttempts());
    }
    @Test void logoutRejectsNewConnectionsAndClosesAnExistingConnection() throws Exception {
        ControlClient.Session session = alice.login("sample");
        try (Socket tunnel = alice.tunnel(session.id(), "sample-business:443")) {
            assertEquals("OK alice", login(tunnel, "alice", businessPassword)); alice.logout(session);
            assertThrows(SecurityException.class, () -> alice.tunnel(session.id(), "sample-business:443"));
            assertClosed(tunnel);
        }
    }
    @Test void expiryClosesLongConnectionsWithoutAgentCooperation() throws Exception {
        server.close(); startAccess(1);
        ControlClient.Session session = alice.login("sample");
        try (Socket tunnel = alice.tunnel(session.id(), "sample-business:443")) {
            assertEquals("OK alice", login(tunnel, "alice", businessPassword));
            Thread.sleep(1400); assertClosed(tunnel);
            assertThrows(SecurityException.class, () -> alice.tunnel(session.id(), "sample-business:443"));
        }
    }
    private static void assertClosed(Socket socket) throws Exception {
        socket.setSoTimeout(2000);
        try { assertEquals(-1, socket.getInputStream().read()); } catch (SocketTimeoutException e) { fail("Connection remained open"); } catch (IOException closed) { }
    }
    @Test void oldBooleanVerificationCannotBeUsedAsAuthorization() throws Exception {
        for (String path : List.of("/verifySign", "/genRandom", "/verifyUser", "/deploy")) assertEquals(410, alice.request("POST", path, null).statusCode());
        assertEquals(0, business.loginAttempts());
    }
    @Test void nativeAgentCanCarryAnUnmodifiedBusinessProtocolAndClosesItsListener() throws Exception {
        Properties p = load(fixtures.resolve("alice-agent.properties"));
        p.setProperty("api.port", Integer.toString(server.apiPort())); p.setProperty("gateway.port", Integer.toString(server.gatewayPort())); p.setProperty("agent.port", "0");
        for (String key : List.of("tls.keystore", "tls.truststore", "secrets.file")) p.setProperty(key, fixtures.resolve(p.getProperty(key)).toString());
        DesktopAgent agent = new DesktopAgent(new Settings(config("agent.properties", p)), ignored -> { });
        int port;
        try {
            agent.start(); port = agent.localPort();
            try (Socket socket = new Socket("127.0.0.1", port)) { assertEquals("OK alice", login(socket, "alice", businessPassword)); }
        } finally { agent.close(); }
        assertThrows(ConnectException.class, () -> new Socket("127.0.0.1", port));
    }
    @Test void realPilotModeRefusesBeforeReadingSoftwareKeys() throws Exception {
        Properties p = new Properties(); p.setProperty("mode", "REAL-PILOT");
        IllegalArgumentException error = assertThrows(IllegalArgumentException.class, () -> new AccessServer(new Settings(config("real.properties", p))));
        assertTrue(error.getMessage().contains("REAL-PILOT is unavailable"));
        assertThrows(IllegalArgumentException.class, () -> IdentityProvider.from(new Settings(work.resolve("real.properties"))));
    }
    @Test void unavailableAuthenticationDoesNotOpenTheLocalBusinessPort() throws Exception {
        Properties p = load(fixtures.resolve("alice-agent.properties"));
        int unavailable, local;
        try (ServerSocket reserve = new ServerSocket(0)) { unavailable = reserve.getLocalPort(); }
        try (ServerSocket reserve = new ServerSocket(0)) { local = reserve.getLocalPort(); }
        p.setProperty("api.port", Integer.toString(unavailable)); p.setProperty("gateway.port", Integer.toString(server.gatewayPort())); p.setProperty("agent.port", Integer.toString(local));
        for (String key : List.of("tls.keystore", "tls.truststore", "secrets.file")) p.setProperty(key, fixtures.resolve(p.getProperty(key)).toString());
        try (DesktopAgent agent = new DesktopAgent(new Settings(config("unavailable.properties", p)), ignored -> { })) {
            assertThrows(IOException.class, agent::start);
            assertThrows(ConnectException.class, () -> new Socket("127.0.0.1", local));
        }
        assertEquals(0, business.loginAttempts());
    }
    private Properties agentConfig() throws Exception {
        Properties p = load(fixtures.resolve("alice-agent.properties"));
        p.setProperty("api.port", Integer.toString(server.apiPort())); p.setProperty("gateway.port", Integer.toString(server.gatewayPort())); p.setProperty("agent.port", "0");
        for (String key : List.of("tls.keystore", "tls.truststore", "secrets.file")) p.setProperty(key, fixtures.resolve(p.getProperty(key)).toString());
        return p;
    }
    private Process javaProcess(String main, Path config, Path log) throws IOException {
        String suffix = System.getProperty("os.name").startsWith("Windows") ? ".exe" : "";
        return new ProcessBuilder(Path.of(System.getProperty("java.home"), "bin", "java" + suffix).toString(), "-cp",
                System.getProperty("surefire.test.class.path", System.getProperty("java.class.path")), main, "--config", config.toString())
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
    @Test void deniedBusinessLoginHasANonzeroCliExitCode() throws Exception {
        try (DesktopAgent agent = new DesktopAgent(new Settings(config("cli-agent.properties", agentConfig())), ignored -> { })) {
            agent.start(); Properties p = new Properties();
            p.setProperty("mode", "DEMO"); p.setProperty("client.host", "127.0.0.1"); p.setProperty("client.port", Integer.toString(agent.localPort()));
            p.setProperty("business.user", "bob"); p.setProperty("secrets.file", fixtures.resolve("secrets.properties").toString());
            Path log = work.resolve("client.log"); Process process = javaProcess("cn.ukey.pilot.lab.SampleClientMain", config("cli-client.properties", p), log);
            try { assertTrue(process.waitFor(10, TimeUnit.SECONDS)); assertEquals(2, process.exitValue()); assertTrue(Files.readString(log).contains("ACCOUNT_DENIED")); }
            finally { if (process.isAlive()) process.destroyForcibly().waitFor(); }
        }
        assertEquals(0, business.loginAttempts());
    }
    @Test void cliAgentExitsWhenItsSessionExpires() throws Exception {
        server.close(); startAccess(1); Path log = work.resolve("agent.log");
        Process process = javaProcess("cn.ukey.pilot.agent.AgentMain", config("expiry-agent.properties", agentConfig()), log);
        try {
            assertTrue(process.waitFor(12, TimeUnit.SECONDS)); assertEquals(0, process.exitValue());
            assertTrue(Files.readString(log).contains("Disconnected"));
        } finally { if (process.isAlive()) process.destroyForcibly().waitFor(); }
    }
    @Test void auditRecordsActionsWithoutPasswordsOrBearerSessionValues() throws Exception {
        ControlClient.Session session = alice.login("sample");
        try (Socket tunnel = alice.tunnel(session.id(), "sample-business:443")) { assertEquals("OK alice", login(tunnel, "alice", businessPassword)); }
        alice.logout(session);
        String audit = Files.readString(work.resolve("audit.jsonl"));
        assertTrue(audit.contains("session-created") && audit.contains("tunnel-open") && audit.contains("session-revoked"));
        assertFalse(audit.contains(session.id())); assertFalse(audit.contains(businessPassword)); assertFalse(audit.contains(new String(storePassword)));
    }
    SSLSocket rawGateway() throws Exception {
        return TlsSupport.connect(TlsSupport.context(fixtures.resolve("alice.p12"), fixtures.resolve("trust.p12"), storePassword), "localhost", server.gatewayPort());
    }
    String header(String session) { return "CONNECT sample-business:443 HTTP/1.1\r\nX-Access-Session: " + session + "\r\n"; }
    void assertHealthy() throws Exception {
        var grant = alice.login("sample");
        try (Socket socket = alice.tunnel(grant.id(), "sample-business:443")) { assertEquals("OK alice", login(socket, "alice", businessPassword)); }
        alice.logout(grant);
    }
    @Test void malformedAndOversizedConnectRequestsNeverReachBusinessAndServiceRecovers() throws Exception {
        var grant = alice.login("sample");
        List<String> requests = List.of(
                "CONNECT sample-business:443 HTTP/1.1\r\n\r\n", // Actually missing the header, not merely an unknown value.
                header(grant.id()) + "X-Access-Session: " + grant.id() + "\r\n\r\n",
                "GET sample-business:443 HTTP/1.1\r\n\r\n",
                header(grant.id()) + "BrokenHeader\r\n\r\n",
                header(grant.id()) + "X-Long: " + "x".repeat(2200) + "\r\n\r\n",
                header(grant.id()) + "X-Pad: " + "x".repeat(1900) + "\r\nY-Pad: " + "x".repeat(1900) + "\r\nZ-Pad: " + "x".repeat(1900) + "\r\nW-Pad: " + "x".repeat(1900) + "\r\nV-Pad: " + "x".repeat(1900) + "\r\n\r\n",
                header(grant.id()) + java.util.stream.IntStream.range(0, 33).mapToObj(i -> "X-" + i + ": a\r\n").reduce("", String::concat) + "\r\n");
        for (String request : requests) try (SSLSocket socket = rawGateway()) {
            socket.getOutputStream().write(request.getBytes(StandardCharsets.US_ASCII)); socket.getOutputStream().flush(); socket.setSoTimeout(2000);
            try { String response = Wire.line(socket.getInputStream(), 4096); assertTrue(response == null || response.startsWith("HTTP/1.1 403")); }
            catch (SocketTimeoutException e) { fail("Malformed request was left open"); }
            catch (IOException refused) { }
        }
        assertEquals(0, business.loginAttempts()); assertHealthy();
    }
    @Test void plaintextAndTls12CannotDowngradeTheGateway() throws Exception {
        try (Socket raw = new Socket("127.0.0.1", server.gatewayPort())) {
            raw.getOutputStream().write("CONNECT sample-business:443 HTTP/1.1\r\n\r\n".getBytes(StandardCharsets.US_ASCII)); raw.getOutputStream().flush();
            raw.setSoTimeout(2000);
            try { assertNotEquals((int) 'H', raw.getInputStream().read()); } catch (SocketTimeoutException e) { fail("Plaintext request stalled"); } catch (IOException refused) { }
        }
        SSLContext context = TlsSupport.context(fixtures.resolve("alice.p12"), fixtures.resolve("trust.p12"), storePassword);
        try (SSLSocket socket = (SSLSocket) context.getSocketFactory().createSocket("localhost", server.gatewayPort())) {
            socket.setEnabledProtocols(new String[]{"TLSv1.2"}); socket.setSoTimeout(2000);
            assertThrows(SSLException.class, socket::startHandshake);
        }
        assertEquals(0, business.loginAttempts()); assertHealthy();
    }
    @Test void incompleteTlsHandshakesTimeOutWithoutBlockingTheControlApi() throws Exception {
        var grant = alice.login("sample"); List<Socket> stalled = new ArrayList<>();
        try {
            for (int i = 0; i < 8; i++) stalled.add(new Socket("127.0.0.1", server.gatewayPort()));
            Thread.sleep(200);
            assertEquals(200, alice.request("GET", "/api/status", null).statusCode());
            assertThrows(IOException.class, () -> alice.tunnel(grant.id(), "sample-business:443"));
            for (Socket socket : stalled) { socket.setSoTimeout(6500); assertClosedWithin(socket, 6500); }
        } finally { stalled.forEach(Wire::close); }
        assertHealthy();
    }
    private static void assertClosedWithin(Socket socket, int milliseconds) throws Exception {
        socket.setSoTimeout(milliseconds);
        try {
            // A failed TLS handshake may send a TLS alert before closing TCP.
            int bytes = 0;
            while (socket.getInputStream().read() != -1) assertTrue(++bytes <= 4096, "Unexpected data on an incomplete TLS connection");
        } catch (SocketTimeoutException e) { fail("Connection remained open"); } catch (IOException closed) { }
    }
    @Test void gatewayConnectionLimitRejectsExcessAndReleasesCapacity() throws Exception {
        var grant = alice.login("sample"); List<Socket> held = new ArrayList<>();
        try {
            for (int i = 0; i < 8; i++) { Socket socket = alice.tunnel(grant.id(), "sample-business:443"); held.add(socket); assertEquals("OK alice", login(socket, "alice", businessPassword)); }
            assertThrows(IOException.class, () -> alice.tunnel(grant.id(), "sample-business:443"));
            held.forEach(Wire::close); held.clear();
            awaitHealthy();
        } finally { held.forEach(Wire::close); }
    }
    @Test void slowlyDrippedConnectHeadersCannotHoldAValidationSlotIndefinitely() throws Exception {
        ExecutorService writer = Executors.newSingleThreadExecutor();
        try (SSLSocket socket = rawGateway()) {
            long begin = System.nanoTime();
            Future<?> drip = writer.submit(() -> {
                try {
                    byte[] request = header(alice.login("sample").id()).getBytes(StandardCharsets.US_ASCII);
                    for (byte value : request) { socket.getOutputStream().write(value); socket.getOutputStream().flush(); Thread.sleep(200); }
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                catch (Exception closed) { }
            });
            try { assertClosedWithin(socket, 7000); assertTrue(System.nanoTime() - begin < TimeUnit.MILLISECONDS.toNanos(6500), "Validation exceeded its absolute deadline"); }
            finally { drip.cancel(true); }
            assertEquals(0, business.loginAttempts());
        } finally { writer.shutdownNow(); }
        assertHealthy();
    }
    void awaitHealthy() throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4); Exception last = null;
        do { try { assertHealthy(); return; } catch (IOException | SecurityException e) { last = e; Thread.sleep(50); } } while (System.nanoTime() < deadline);
        throw new AssertionError("Capacity did not recover", last);
    }
    @Test void concurrentUsersKeepTheirOwnBusinessIdentitiesAndData() throws Exception {
        ControlClient bob = client("bob"); var a = alice.login("sample"); var b = bob.login("sample");
        ExecutorService pool = Executors.newFixedThreadPool(6); List<Future<?>> tasks = new ArrayList<>();
        try {
            for (int i = 0; i < 6; i++) { final int index = i; tasks.add(pool.submit(() -> {
                String account = index % 2 == 0 ? "alice" : "bob"; ControlClient c = index % 2 == 0 ? alice : bob;
                try (Socket socket = c.tunnel(index % 2 == 0 ? a.id() : b.id(), "sample-business:443")) {
                    assertEquals("OK " + account, login(socket, account, businessPassword));
                    for (int j = 0; j < 30; j++) {
                        Wire.line(socket.getOutputStream(), "WHOAMI"); assertEquals("USER " + account, Wire.line(socket.getInputStream(), 4096));
                        String text = "中文-" + index + "-" + j; Wire.line(socket.getOutputStream(), "ECHO " + text); assertEquals(text, Wire.line(socket.getInputStream(), 4096));
                    }
                } catch (Exception e) { throw new RuntimeException(e); }
            })); }
            for (Future<?> task : tasks) task.get(20, TimeUnit.SECONDS);
        } finally { pool.shutdownNow(); alice.logout(a); bob.logout(b); }
    }
    @Test void revocationDuringConcurrentConnectionAttemptsNeverAllowsLaterBusinessLogin() throws Exception {
        var grant = alice.login("sample"); ExecutorService pool = Executors.newFixedThreadPool(4); CountDownLatch go = new CountDownLatch(1);
        List<Socket> opened = new CopyOnWriteArrayList<>(); List<Future<?>> tasks = new ArrayList<>();
        try {
            for (int i = 0; i < 4; i++) tasks.add(pool.submit(() -> {
                try { go.await(); opened.add(alice.tunnel(grant.id(), "sample-business:443")); }
                catch (SecurityException | IOException denied) { } catch (Exception e) { throw new RuntimeException(e); }
            }));
            go.countDown(); alice.logout(grant);
            for (Future<?> task : tasks) task.get(8, TimeUnit.SECONDS);
            for (Socket socket : opened) assertClosed(socket);
            assertThrows(SecurityException.class, () -> alice.tunnel(grant.id(), "sample-business:443"));
            assertEquals(0, business.loginAttempts());
        } finally { opened.forEach(Wire::close); pool.shutdownNow(); }
    }
    @Test void accessServiceRestartInvalidatesOldSessionAndClosesBusinessConnections() throws Exception {
        var grant = alice.login("sample");
        try (Socket socket = alice.tunnel(grant.id(), "sample-business:443")) {
            assertEquals("OK alice", login(socket, "alice", businessPassword)); server.close(); assertClosed(socket);
            startAccess(30); assertThrows(SecurityException.class, () -> alice.tunnel(grant.id(), "sample-business:443")); assertHealthy();
        }
    }
    @Test void backendFailureDoesNotAuthenticateAndRestartAllowsRecovery() throws Exception {
        var grant = alice.login("sample"); int port = business.port(); business.close();
        try (Socket socket = alice.tunnel(grant.id(), "sample-business:443")) {
            try { assertNotEquals("OK alice", login(socket, "alice", businessPassword)); } catch (SocketTimeoutException e) { fail("Backend failure hung"); } catch (IOException closed) { }
        }
        business = new BusinessServer(InetAddress.getLoopbackAddress(), port, Set.of("alice", "bob"), businessPassword); assertHealthy();
    }
    @Test void agentConnectionLimitRecoversAfterClientsDisconnect() throws Exception {
        try (DesktopAgent agent = new DesktopAgent(new Settings(config("bounded-agent.properties", agentConfig())), ignored -> { })) {
            agent.start(); List<Socket> held = new ArrayList<>();
            try {
                for (int i = 0; i < 4; i++) { Socket socket = new Socket("127.0.0.1", agent.localPort()); held.add(socket); assertEquals("OK alice", login(socket, "alice", businessPassword)); }
                try (Socket excess = new Socket("127.0.0.1", agent.localPort())) { assertClosed(excess); }
                held.forEach(Wire::close); held.clear(); Thread.sleep(200);
                try (Socket recovered = new Socket("127.0.0.1", agent.localPort())) { assertEquals("OK alice", login(recovered, "alice", businessPassword)); }
            } finally { held.forEach(Wire::close); }
        }
    }
    @Test void fragmentedLoginAndCoalescedCommandsSurviveTheAgent() throws Exception {
        try (DesktopAgent agent = new DesktopAgent(new Settings(config("framing-agent.properties", agentConfig())), ignored -> { })) {
            agent.start();
            try (Socket socket = new Socket("127.0.0.1", agent.localPort())) {
                socket.setSoTimeout(5000);
                byte[] login = ("LOGIN alice " + businessPassword + "\n").getBytes(StandardCharsets.UTF_8);
                for (byte value : login) { socket.getOutputStream().write(value); socket.getOutputStream().flush(); }
                assertEquals("OK alice", Wire.line(socket.getInputStream(), 4096));
                socket.getOutputStream().write("WHOAMI\nECHO 中文\nWHOAMI\n".getBytes(StandardCharsets.UTF_8)); socket.getOutputStream().flush();
                assertEquals("USER alice", Wire.line(socket.getInputStream(), 4096)); assertEquals("中文", Wire.line(socket.getInputStream(), 4096)); assertEquals("USER alice", Wire.line(socket.getInputStream(), 4096));
            }
        }
    }
    @Test void halfClosingTheClientStillDeliversTheCompleteLargeResponse() throws Exception {
        try (DesktopAgent agent = new DesktopAgent(new Settings(config("halfclose-agent.properties", agentConfig())), ignored -> { })) {
            agent.start();
            try (Socket socket = new Socket("127.0.0.1", agent.localPort())) {
                assertEquals("OK alice", login(socket, "alice", businessPassword));
                byte[] payload = new byte[2 * 1024 * 1024]; new Random(98).nextBytes(payload);
                Wire.line(socket.getOutputStream(), "BLOB " + payload.length); socket.getOutputStream().write(payload); socket.getOutputStream().flush();
                socket.shutdownOutput(); socket.setSoTimeout(8000);
                assertEquals("BLOB " + payload.length, Wire.line(socket.getInputStream(), 4096));
                assertArrayEquals(payload, socket.getInputStream().readNBytes(payload.length)); assertClosed(socket);
            }
        }
    }
    @AfterEach void closeServices() throws Exception { if (server != null) server.close(); if (business != null) business.close(); delete(work); }
    @AfterAll static void cleanupCertificates() throws Exception { Arrays.fill(storePassword, '\0'); delete(fixtures); }
    static void delete(Path root) throws IOException {
        if (root == null || !Files.exists(root)) return;
        try (var paths = Files.walk(root)) { for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) Files.deleteIfExists(path); }
    }
}
