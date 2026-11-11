package cn.ukey.pilot.agent;

import cn.ukey.pilot.common.*;
import javax.net.ssl.*;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.Properties;

public final class ControlClient {
    public record Session(String id, String resource, Instant expires) { }
    private final SSLContext tls;
    private final HttpClient http;
    private final String host;
    private final int apiPort, gatewayPort;
    public ControlClient(SSLContext tls, String host, int apiPort, int gatewayPort) {
        this.tls = tls; this.host = host; this.apiPort = apiPort; this.gatewayPort = gatewayPort;
        SSLParameters parameters = new SSLParameters(); parameters.setProtocols(new String[]{"TLSv1.3"}); parameters.setEndpointIdentificationAlgorithm("HTTPS");
        http = HttpClient.newBuilder().sslContext(tls).sslParameters(parameters).connectTimeout(Duration.ofSeconds(5)).version(HttpClient.Version.HTTP_1_1).build();
    }
    public HttpResponse<String> request(String method, String path, String resource) throws Exception {
        HttpRequest.Builder request = HttpRequest.newBuilder(URI.create("https://" + host + ":" + apiPort + path)).timeout(Duration.ofSeconds(5));
        if (resource != null) request.header("X-Resource-Id", resource);
        return http.send(request.method(method, HttpRequest.BodyPublishers.noBody()).build(), HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }
    public Session login(String resource) throws Exception {
        HttpResponse<String> response = request("POST", "/api/sessions", resource);
        if (response.statusCode() != 201) throw new SecurityException("Authentication/resource authorization refused: " + response.statusCode());
        if (response.body().length() > 4096) throw new SecurityException("Invalid authorization response");
        Properties p = Wire.properties(response.body()); String id = p.getProperty("session", "");
        if (!id.matches("[A-Za-z0-9_-]{43}") || !resource.equals(p.getProperty("resource"))) throw new SecurityException("Invalid authorization response");
        return new Session(id, resource, Instant.parse(p.getProperty("expires")));
    }
    public void logout(Session session) throws Exception {
        int status = request("DELETE", "/api/sessions/" + session.id(), null).statusCode();
        if (status != 204 && status != 403) throw new IllegalStateException("Logout service unavailable: " + status);
    }
    public SSLSocket tunnel(String sessionId, String authority) throws Exception {
        if (!authority.matches("[A-Za-z0-9.-]+:[0-9]{1,5}") || !sessionId.matches("[A-Za-z0-9_-]{43}")) throw new IllegalArgumentException("Invalid tunnel parameters");
        SSLSocket socket = TlsSupport.connect(tls, host, gatewayPort);
        try {
            String connect = "CONNECT " + authority + " HTTP/1.1\r\nHost: " + authority + "\r\nX-Access-Session: " + sessionId + "\r\n\r\n";
            socket.getOutputStream().write(connect.getBytes(StandardCharsets.US_ASCII)); socket.getOutputStream().flush();
            Wire.Headers response = Wire.headers(socket.getInputStream());
            if (!response.first().equals("HTTP/1.1 200 Connection Established")) throw new SecurityException("Tunnel authorization refused");
            socket.setSoTimeout(0); return socket;
        } catch (Exception e) { socket.close(); throw e; }
    }
}
