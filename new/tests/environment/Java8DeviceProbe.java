import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;

public class Java8DeviceProbe {
    public static void main(String[] args) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL("http://127.0.0.1:38080/sys/getDevInfo").openConnection();
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
        c.setConnectTimeout(5000);
        c.setReadTimeout(5000);
        c.setDoOutput(true);
        try (OutputStream out = c.getOutputStream()) { out.write(new byte[0]); }
        int status = c.getResponseCode();
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (InputStream in = status < 400 ? c.getInputStream() : c.getErrorStream()) {
            byte[] buffer = new byte[1024];
            int n;
            while ((n = in.read(buffer)) != -1) bytes.write(buffer, 0, n);
        } finally { c.disconnect(); }
        String body = new String(bytes.toByteArray(), StandardCharsets.UTF_8);
        boolean codeOk = java.util.regex.Pattern.compile("\"code\"\\s*:\\s*200\\b").matcher(body).find();
        boolean device = java.util.regex.Pattern.compile("\"SerialNumber\"\\s*:\\s*\"[^\"]+\"").matcher(body).find();
        System.out.println("java.version=" + System.getProperty("java.version"));
        System.out.println("http.status=" + status);
        System.out.println("device.detected=" + (status == 200 && codeOk && device));
        if (!(status == 200 && codeOk && device)) System.exit(2);
    }
}
