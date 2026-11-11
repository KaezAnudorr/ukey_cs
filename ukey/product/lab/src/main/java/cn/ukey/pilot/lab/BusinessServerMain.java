package cn.ukey.pilot.lab;

import cn.ukey.pilot.common.Settings;
import java.util.concurrent.CountDownLatch;

public final class BusinessServerMain {
    public static void main(String[] args) {
        try {
            Settings s = new Settings(Settings.argument(args)); s.requireDemo();
            BusinessServer server = new BusinessServer(s.loopback("business.host"), s.number("business.port", 19510, 1, 65535), s.set("business.accounts"), s.secret("business.password"));
            Runtime.getRuntime().addShutdownHook(new Thread(server::close));
            System.out.println("DEMO business service on 127.0.0.1:" + server.port()); new CountDownLatch(1).await();
        } catch (Exception e) { System.err.println("BUSINESS REFUSED: " + e.getMessage()); System.exit(2); }
    }
}
