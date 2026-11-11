package cn.ukey.pilot.server;

import cn.ukey.pilot.common.Settings;
import java.net.InetAddress;
import java.util.*;

/** Preserves the legacy account/certificate/resource mapping, without serial-number authentication. */
public final class Policy {
    public record Identity(String id, String fingerprint, Set<String> resources, Set<String> accounts) { }
    public record Resource(String id, String authority, InetAddress host, int port, String adapter) { }
    private final Map<String, Identity> identities = new HashMap<>();
    private final Map<String, Resource> resources = new HashMap<>();
    public Policy(Settings settings) throws Exception {
        if (settings.set("identity.ids").isEmpty() || settings.set("resource.ids").isEmpty()) throw new IllegalArgumentException("Empty policy");
        for (String id : settings.set("resource.ids")) {
            validateId(id);
            String prefix = "resource." + id + ".";
            String authority = settings.require(prefix + "authority");
            if (!authority.matches("[A-Za-z0-9.-]+:[0-9]{1,5}")) throw new IllegalArgumentException("Invalid CONNECT authority");
            if (resources.values().stream().anyMatch(r -> r.authority().equals(authority))) throw new IllegalArgumentException("Duplicate authority");
            String adapter = settings.require(prefix + "adapter");
            if (!adapter.equals("sample-line-login")) throw new IllegalArgumentException("No validated business adapter: " + adapter);
            resources.put(id, new Resource(id, authority, settings.loopback(prefix + "host"), settings.number(prefix + "port", 0, 1, 65535), adapter));
        }
        for (String id : settings.set("identity.ids")) {
            validateId(id); String prefix = "identity." + id + ".";
            String fingerprint = settings.require(prefix + "fingerprint").toLowerCase(Locale.ROOT);
            if (!fingerprint.matches("[0-9a-f]{64}")) throw new IllegalArgumentException("Invalid certificate fingerprint");
            Set<String> allowed = settings.set(prefix + "resources");
            Set<String> accounts = settings.set(prefix + "accounts");
            if (!resources.keySet().containsAll(allowed) || accounts.isEmpty()) throw new IllegalArgumentException("Invalid identity policy");
            if (identities.put(fingerprint, new Identity(id, fingerprint, allowed, accounts)) != null) throw new IllegalArgumentException("Duplicate certificate identity");
        }
    }
    private static void validateId(String id) { if (!id.matches("[A-Za-z0-9._-]{1,64}")) throw new IllegalArgumentException("Invalid policy id"); }
    public Identity identity(String fingerprint) { return identities.get(fingerprint); }
    public Resource resource(String id) { return resources.get(id); }
    public Resource authority(String authority) { return resources.values().stream().filter(r -> r.authority().equals(authority)).findFirst().orElse(null); }
}
