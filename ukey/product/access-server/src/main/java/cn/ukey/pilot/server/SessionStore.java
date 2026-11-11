package cn.ukey.pilot.server;

import cn.ukey.pilot.common.Wire;
import java.security.SecureRandom;
import java.time.*;
import java.util.*;

public final class SessionStore implements AutoCloseable {
    public record Grant(String id, String fingerprint, String identity, String resource, Instant expires) { }
    private record Entry(Grant grant, Set<AutoCloseable> sockets) { }
    private final Map<String, Entry> sessions = new HashMap<>();
    private final SecureRandom random = new SecureRandom();
    private final Clock clock;
    private final Duration ttl;
    public SessionStore(Clock clock, Duration ttl) { this.clock = clock; this.ttl = ttl; }
    public synchronized Grant create(Policy.Identity identity, String resource) {
        if (!identity.resources().contains(resource)) throw new SecurityException("resource-denied");
        if (sessions.size() >= 128) throw new IllegalStateException("session-capacity");
        byte[] bytes = new byte[32]; random.nextBytes(bytes);
        String id = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        Grant grant = new Grant(id, identity.fingerprint(), identity.id(), resource, clock.instant().plus(ttl));
        sessions.put(id, new Entry(grant, new HashSet<>())); return grant;
    }
    public synchronized Grant require(String id, String fingerprint, String resource) {
        Entry entry = sessions.get(id);
        if (entry == null || !clock.instant().isBefore(entry.grant().expires()) || !entry.grant().fingerprint().equals(fingerprint)
                || !entry.grant().resource().equals(resource)) throw new SecurityException("session-denied");
        return entry.grant();
    }
    public synchronized void attach(String id, String fingerprint, String resource, AutoCloseable socket) {
        require(id, fingerprint, resource);
        Set<AutoCloseable> sockets = sessions.get(id).sockets();
        if (sockets.size() >= 32) throw new SecurityException("connection-capacity");
        sockets.add(socket);
    }
    public synchronized void detach(String id, AutoCloseable socket) { Entry e = sessions.get(id); if (e != null) e.sockets().remove(socket); }
    public void revoke(String id, String fingerprint) {
        Entry removed;
        synchronized (this) {
            Entry e = sessions.get(id);
            if (e == null || !e.grant().fingerprint().equals(fingerprint)) throw new SecurityException("session-denied");
            removed = sessions.remove(id);
        }
        removed.sockets().forEach(Wire::close);
    }
    public List<Grant> expire() {
        List<AutoCloseable> close = new ArrayList<>();
        List<Grant> expired = new ArrayList<>();
        synchronized (this) { sessions.values().removeIf(e -> {
            if (clock.instant().isBefore(e.grant().expires())) return false;
            close.addAll(e.sockets()); expired.add(e.grant()); return true;
        }); }
        close.forEach(Wire::close);
        return List.copyOf(expired);
    }
    @Override public void close() {
        List<AutoCloseable> close;
        synchronized (this) { close = sessions.values().stream().flatMap(e -> e.sockets().stream()).toList(); sessions.clear(); }
        close.forEach(Wire::close);
    }
}
