package cn.ukey.pilot.common;

import javax.net.ssl.*;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.nio.file.*;
import java.security.*;
import java.security.cert.X509Certificate;
import java.util.*;

public final class TlsSupport {
    private TlsSupport() { }
    public static SSLContext context(Settings settings) throws Exception {
        char[] password = settings.password();
        try { return context(settings.path("tls.keystore"), settings.path("tls.truststore"), password); }
        finally { Arrays.fill(password, '\0'); }
    }
    public static SSLContext context(Path keyFile, Path trustFile, char[] password) throws Exception {
        KeyManager[] managers = null;
        if (keyFile != null) {
            KeyStore keys = load(keyFile, password);
            KeyManagerFactory factory = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
            factory.init(keys, password); managers = factory.getKeyManagers();
        }
        TrustManagerFactory trust = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        trust.init(load(trustFile, password));
        SSLContext context = SSLContext.getInstance("TLS");
        context.init(managers, trust.getTrustManagers(), new SecureRandom());
        return context;
    }
    private static KeyStore load(Path file, char[] password) throws Exception {
        KeyStore store = KeyStore.getInstance("PKCS12");
        try (InputStream in = Files.newInputStream(file)) { store.load(in, password); }
        return store;
    }
    public static String fingerprint(X509Certificate certificate) throws Exception {
        certificate.checkValidity();
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded()));
    }
    public static String peer(SSLSession session) throws Exception {
        return fingerprint((X509Certificate) session.getPeerCertificates()[0]);
    }
    public static SSLSocket connect(SSLContext context, String host, int port) throws Exception {
        SSLSocket socket = (SSLSocket) context.getSocketFactory().createSocket();
        try {
            SSLParameters parameters = socket.getSSLParameters();
            parameters.setEndpointIdentificationAlgorithm("HTTPS");
            parameters.setProtocols(new String[]{"TLSv1.3"});
            socket.setSSLParameters(parameters);
            socket.connect(new InetSocketAddress(host, port), 5000);
            socket.setSoTimeout(5000); socket.startHandshake(); return socket;
        } catch (Exception e) { socket.close(); throw e; }
    }
}
