package cn.ukey.pilot.server;

import org.junit.jupiter.api.Test;
import java.time.*;
import java.util.Set;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;

class SessionStoreTest {
    private static final Policy.Identity ALICE = new Policy.Identity("alice", "a".repeat(64), Set.of("sample"), Set.of("alice"));
    static final class MutableClock extends Clock {
        Instant value = Instant.parse("2026-11-06T00:00:00Z");
        public ZoneId getZone() { return ZoneOffset.UTC; }
        public Clock withZone(ZoneId zone) { return this; }
        public Instant instant() { return value; }
    }
    @Test void sessionIsBoundToCertificateAndResource() {
        MutableClock clock = new MutableClock();
        try (SessionStore store = new SessionStore(clock, Duration.ofSeconds(10))) {
            var grant = store.create(ALICE, "sample");
            assertEquals(grant, store.require(grant.id(), ALICE.fingerprint(), "sample"));
            assertThrows(SecurityException.class, () -> store.require(grant.id(), "b".repeat(64), "sample"));
            assertThrows(SecurityException.class, () -> store.require(grant.id(), ALICE.fingerprint(), "different"));
            assertThrows(SecurityException.class, () -> store.create(ALICE, "different"));
        }
    }
    @Test void anExpiredOrRevokedSessionCannotBeReusedAndConnectionsAreClosed() {
        MutableClock clock = new MutableClock(); AtomicBoolean closed = new AtomicBoolean();
        try (SessionStore store = new SessionStore(clock, Duration.ofSeconds(10))) {
            var expired = store.create(ALICE, "sample");
            store.attach(expired.id(), ALICE.fingerprint(), "sample", () -> closed.set(true));
            clock.value = clock.value.plusSeconds(10); store.expire(); assertTrue(closed.get());
            assertThrows(SecurityException.class, () -> store.require(expired.id(), ALICE.fingerprint(), "sample"));
            var revoked = store.create(ALICE, "sample"); store.revoke(revoked.id(), ALICE.fingerprint());
            assertThrows(SecurityException.class, () -> store.require(revoked.id(), ALICE.fingerprint(), "sample"));
        }
    }
    @Test void sessionCapacityIsBoundedAndRecoversAfterRevocationAndExpiry() {
        MutableClock clock = new MutableClock();
        try (SessionStore store = new SessionStore(clock, Duration.ofSeconds(10))) {
            List<SessionStore.Grant> grants = new ArrayList<>();
            for (int i = 0; i < 128; i++) grants.add(store.create(ALICE, "sample"));
            assertEquals(128, grants.stream().map(SessionStore.Grant::id).distinct().count());
            assertThrows(IllegalStateException.class, () -> store.create(ALICE, "sample"));
            store.revoke(grants.get(0).id(), ALICE.fingerprint());
            assertNotNull(store.create(ALICE, "sample"));
            clock.value = clock.value.plusSeconds(10); assertEquals(128, store.expire().size());
            assertNotNull(store.create(ALICE, "sample"));
        }
    }
    @Test void attachmentCapacityAndWrongOwnerRevocationDoNotDamageAnotherSession() {
        AtomicInteger closed = new AtomicInteger();
        try (SessionStore store = new SessionStore(new MutableClock(), Duration.ofSeconds(10))) {
            var grant = store.create(ALICE, "sample");
            List<AutoCloseable> connections = new ArrayList<>();
            for (int i = 0; i < 32; i++) { AutoCloseable socket = new AutoCloseable() { public void close() { closed.incrementAndGet(); } }; connections.add(socket); store.attach(grant.id(), ALICE.fingerprint(), "sample", socket); }
            assertThrows(SecurityException.class, () -> store.attach(grant.id(), ALICE.fingerprint(), "sample", () -> { }));
            assertThrows(SecurityException.class, () -> store.revoke(grant.id(), "b".repeat(64)));
            assertEquals(grant, store.require(grant.id(), ALICE.fingerprint(), "sample")); assertEquals(0, closed.get());
            store.detach(grant.id(), connections.get(0)); store.attach(grant.id(), ALICE.fingerprint(), "sample", closed::incrementAndGet);
            store.revoke(grant.id(), ALICE.fingerprint()); assertEquals(32, closed.get());
        }
    }
    @Test void concurrentRevocationAndAttachmentLeaveNoUnclosedRegisteredConnection() throws Exception {
        try (SessionStore store = new SessionStore(new MutableClock(), Duration.ofSeconds(10))) {
            ExecutorService pool = Executors.newFixedThreadPool(4);
            try {
                for (int round = 0; round < 50; round++) {
                    var grant = store.create(ALICE, "sample"); CountDownLatch go = new CountDownLatch(1);
                    AtomicInteger attached = new AtomicInteger(), closed = new AtomicInteger(); List<Future<?>> tasks = new ArrayList<>();
                    for (int i = 0; i < 3; i++) tasks.add(pool.submit(() -> {
                        try { go.await(); store.attach(grant.id(), ALICE.fingerprint(), "sample", closed::incrementAndGet); attached.incrementAndGet(); }
                        catch (SecurityException revoked) { } catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new RuntimeException(e); }
                    }));
                    go.countDown(); store.revoke(grant.id(), ALICE.fingerprint());
                    for (Future<?> task : tasks) task.get(3, TimeUnit.SECONDS);
                    assertEquals(attached.get(), closed.get());
                    assertThrows(SecurityException.class, () -> store.require(grant.id(), ALICE.fingerprint(), "sample"));
                }
            } finally { pool.shutdownNow(); }
        }
    }
}
