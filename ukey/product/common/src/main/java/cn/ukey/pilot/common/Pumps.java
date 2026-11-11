package cn.ukey.pilot.common;

import java.io.IOException;
import java.net.Socket;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executor;

public final class Pumps {
    private Pumps() { }
    public static void bridge(Socket first, Socket second, Executor executor) {
        CountDownLatch finished = new CountDownLatch(2);
        try {
            executor.execute(() -> copy(first, second, finished));
            copy(second, first, finished);
            finished.await();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt(); Wire.close(first); Wire.close(second);
        } catch (RuntimeException e) {
            Wire.close(first); Wire.close(second); throw e;
        }
    }
    private static void copy(Socket from, Socket to, CountDownLatch finished) {
        try {
            from.getInputStream().transferTo(to.getOutputStream());
            // FIN/close_notify in one direction must not truncate the reverse response.
            if (!to.isClosed() && !to.isOutputShutdown()) to.shutdownOutput();
        } catch (IOException e) { Wire.close(from); Wire.close(to); }
        finally { finished.countDown(); }
    }
}
