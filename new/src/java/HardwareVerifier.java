import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.spec.ECGenParameterSpec;
import java.util.Arrays;
import java.util.Base64;
import org.bouncycastle.asn1.ASN1EncodableVector;
import org.bouncycastle.asn1.ASN1Integer;
import org.bouncycastle.asn1.DERSequence;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.jcajce.spec.SM2ParameterSpec;

/** 从原网页插件 JAR 提取的 BC 库独立验签；不读取或操作设备私钥。 */
public final class HardwareVerifier {
    private static final byte[] SM2_ID = "1234567812345678".getBytes(StandardCharsets.US_ASCII);

    private static byte[] der(byte[] signature) throws Exception {
        if (signature.length != 64) return signature; // ASN.1 DER 由签名实现解析。
        ASN1EncodableVector values = new ASN1EncodableVector();
        values.add(new ASN1Integer(new BigInteger(1, Arrays.copyOfRange(signature, 0, 32))));
        values.add(new ASN1Integer(new BigInteger(1, Arrays.copyOfRange(signature, 32, 64))));
        return new DERSequence(values).getEncoded();
    }

    static boolean verify(PublicKey key, byte[] message, byte[] signature) throws Exception {
        Signature verifier = Signature.getInstance("SM3withSM2", "BC");
        verifier.setParameter(new SM2ParameterSpec(SM2_ID));
        verifier.initVerify(key);
        verifier.update(message);
        return verifier.verify(der(signature));
    }

    public static void main(String[] args) throws Exception {
        Security.addProvider(new BouncyCastleProvider());
        if (args[0].equals("self-test")) {
            KeyPairGenerator generator = KeyPairGenerator.getInstance("EC", "BC");
            generator.initialize(new ECGenParameterSpec("sm2p256v1"));
            KeyPair pair = generator.generateKeyPair();
            byte[] message = "local cryptographic verifier self-test".getBytes(StandardCharsets.UTF_8);
            Signature signer = Signature.getInstance("SM3withSM2", "BC");
            signer.setParameter(new SM2ParameterSpec(SM2_ID));
            signer.initSign(pair.getPrivate()); signer.update(message);
            byte[] signature = signer.sign();
            org.bouncycastle.asn1.ASN1Sequence sequence = org.bouncycastle.asn1.ASN1Sequence.getInstance(signature);
            byte[] raw = new byte[64];
            for (int i = 0; i < 2; i++) {
                byte[] n = org.bouncycastle.asn1.ASN1Integer.getInstance(sequence.getObjectAt(i)).getPositiveValue().toByteArray();
                int count = Math.min(n.length, 32);
                System.arraycopy(n, n.length - count, raw, i * 32 + 32 - count, count);
            }
            if (!verify(pair.getPublic(), message, signature) || !verify(pair.getPublic(), message, raw)) throw new AssertionError("valid signature rejected");
            message[0] ^= 1;
            if (verify(pair.getPublic(), message, signature)) throw new AssertionError("tampered message accepted");
            System.out.println("{\"der_valid\":true,\"raw_valid\":true,\"tampered_rejected\":true}");
            return;
        }
        X509Certificate certificate;
        try (FileInputStream in = new FileInputStream(args[1])) {
            certificate = (X509Certificate) CertificateFactory.getInstance("X.509", "BC").generateCertificate(in);
        }
        certificate.checkValidity();
        if (args[0].equals("inspect")) {
            System.out.println("{\"certificate_valid_now\":true,\"signature_algorithm\":\"" + certificate.getSigAlgName()
                    + "\",\"public_key_algorithm\":\"" + certificate.getPublicKey().getAlgorithm()
                    + "\",\"not_after_epoch_ms\":" + certificate.getNotAfter().getTime() + "}");
            return;
        }
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.US_ASCII));
        byte[] message = Base64.getDecoder().decode(reader.readLine());
        byte[] signature = Base64.getDecoder().decode(reader.readLine());
        System.out.println(verify(certificate.getPublicKey(), message, signature) ? "true" : "false");
    }
}
