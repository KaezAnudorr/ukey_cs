package cn.ukey.pilot.server;

import cn.ukey.pilot.common.Settings;
import java.util.concurrent.CountDownLatch;

public final class ServerMain {
    public static void main(String[] args) {
        try {
            Settings settings = new Settings(Settings.argument(args));
            if (java.util.Arrays.asList(args).contains("--check")) {
                settings.requireDemo(); new Policy(settings); cn.ukey.pilot.common.TlsSupport.context(settings);
                System.out.println("Configuration valid: DEMO software certificates only"); return;
            }
            AccessServer server = new AccessServer(settings);
            Runtime.getRuntime().addShutdownHook(new Thread(server::close));
            System.out.printf("DEMO ONLY | API https://127.0.0.1:%d | TLS CONNECT 127.0.0.1:%d%n", server.apiPort(), server.gatewayPort());
            new CountDownLatch(1).await();
        } catch (Exception e) { System.err.println("STARTUP REFUSED: " + e.getMessage()); System.exit(2); }
    }
}
