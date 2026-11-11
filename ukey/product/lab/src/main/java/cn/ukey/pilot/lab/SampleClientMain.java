package cn.ukey.pilot.lab;

import cn.ukey.pilot.common.*;
import javax.swing.*;
import java.awt.*;
import java.net.*;
import java.nio.file.Path;
import java.util.Arrays;

public final class SampleClientMain {
    public static void main(String[] args) {
        try {
            Path file = Settings.argument(args); Settings s = new Settings(file); s.requireDemo();
            if (Arrays.asList(args).contains("--gui")) { SwingUtilities.invokeLater(() -> gui(file)); return; }
            try (Socket socket = connect(s)) {
                Wire.line(socket.getOutputStream(), "LOGIN " + s.require("business.user") + " " + s.secret("business.password"));
                String login = Wire.line(socket.getInputStream(), 4096);
                if (login == null || !login.startsWith("OK ")) throw new SecurityException("Business login refused: " + login);
                System.out.println(login);
                Wire.line(socket.getOutputStream(), "WHOAMI"); System.out.println(Wire.line(socket.getInputStream(), 4096));
                Wire.line(socket.getOutputStream(), "ECHO Native C/S flow completed without browser"); System.out.println(Wire.line(socket.getInputStream(), 4096));
            }
        } catch (Exception e) { System.err.println("CLIENT FAILED: " + e.getMessage()); System.exit(2); }
    }
    private static Socket connect(Settings s) throws Exception {
        Socket socket = new Socket(); socket.connect(new InetSocketAddress(s.loopback("client.host"), s.number("client.port", 19500, 1, 65535)), 3000); socket.setSoTimeout(5000); return socket;
    }
    private static void gui(Path file) {
        JFrame window = new JFrame("Native C/S business sample - no UKey calls");
        JTextArea output = new JTextArea(13, 66); output.setEditable(false);
        JButton login = new JButton("Login and run business request");
        login.addActionListener(event -> {
            login.setEnabled(false);
            new SwingWorker<String,Void>() {
                protected String doInBackground() throws Exception {
                    Settings s = new Settings(file);
                    try (Socket socket = connect(s)) {
                        Wire.line(socket.getOutputStream(), "LOGIN " + s.require("business.user") + " " + s.secret("business.password"));
                        String result = Wire.line(socket.getInputStream(), 4096);
                        if (result == null || !result.startsWith("OK ")) return "Business login refused: " + result;
                        Wire.line(socket.getOutputStream(), "WHOAMI"); String user = Wire.line(socket.getInputStream(), 4096);
                        Wire.line(socket.getOutputStream(), "ECHO Native C/S request succeeded"); return result + "\n" + user + "\n" + Wire.line(socket.getInputStream(), 4096);
                    }
                }
                protected void done() { try { output.append(get() + "\n"); } catch (Exception e) { output.append("Connection refused/unavailable: " + e.getCause() + "\n"); } login.setEnabled(true); }
            }.execute();
        });
        window.add(new JLabel("DEMO ONLY | Start the separate desktop access agent first"), BorderLayout.NORTH);
        window.add(new JScrollPane(output)); window.add(login, BorderLayout.SOUTH);
        window.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE); window.pack(); window.setLocationRelativeTo(null); window.setVisible(true);
    }
}
