package cn.ukey.pilot.agent;

import cn.ukey.pilot.common.*;
import javax.net.ssl.SSLContext;

/** Native UKey/GM-TLS integration must supply a separately validated implementation. */
public interface IdentityProvider {
    SSLContext context() throws Exception;
    String description();
    static IdentityProvider from(Settings settings) {
        settings.requireDemo();
        if (!settings.require("identity.provider").equals("demo-software-pkcs12")) throw new IllegalArgumentException("Unsupported identity provider");
        return new IdentityProvider() {
            public SSLContext context() throws Exception { return TlsSupport.context(settings); }
            public String description() { return "DEMO software certificate; no physical UKey or SM2"; }
        };
    }
}
