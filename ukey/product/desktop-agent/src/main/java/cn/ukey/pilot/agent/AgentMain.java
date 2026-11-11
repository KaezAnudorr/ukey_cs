package cn.ukey.pilot.agent;

import cn.ukey.pilot.common.*;
import javax.swing.*;
import java.awt.*;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

public final class AgentMain {
    public static void main(String[] args) {
        try {
            Path config = Settings.argument(args); new Settings(config).requireDemo();
            if (Arrays.asList(args).contains("--gui")) { SwingUtilities.invokeLater(() -> gui(config)); return; }
            CountDownLatch stopped = new CountDownLatch(1);
            DesktopAgent agent = new DesktopAgent(new Settings(config), text -> { System.out.println(text); if (text.startsWith("Disconnected")) stopped.countDown(); });
            Runtime.getRuntime().addShutdownHook(new Thread(agent::close)); agent.start();
            Thread commands = new Thread(() -> {
                try {
                    BufferedReader input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
                    for (String line; (line = input.readLine()) != null;) if (line.trim().equals("disconnect")) { agent.close(); return; }
                } catch (Exception ignored) { }
            }, "agent-console");
            commands.setDaemon(true); commands.start(); stopped.await();
        } catch (Exception e) { System.err.println("AGENT REFUSED: " + e.getMessage()); System.exit(2); }
    }
    private static void gui(Path config) {
        JFrame window = new JFrame("C/S UKey Access - DEMO software identity");
        JTextArea log = new JTextArea(15, 66); log.setEditable(false); log.setLineWrap(true);
        JButton connect = new JButton("Connect DEMO"), disconnect = new JButton("Disconnect"); disconnect.setEnabled(false);
        AtomicReference<DesktopAgent> current = new AtomicReference<>(); AtomicBoolean closing = new AtomicBoolean();
        java.util.function.Consumer<String> output = text -> SwingUtilities.invokeLater(() -> {
            log.append(text + "\n");
            if (text.startsWith("Disconnected") && !closing.get()) { connect.setEnabled(true); disconnect.setEnabled(false); }
        });
        connect.addActionListener(event -> {
            connect.setEnabled(false);
            new SwingWorker<Void,Void>() {
                protected Void doInBackground() throws Exception {
                    DesktopAgent candidate = new DesktopAgent(new Settings(config), output); current.set(candidate);
                    if (closing.get()) { candidate.close(); return null; }
                    candidate.start(); if (closing.get()) candidate.close(); return null;
                }
                protected void done() { try { get(); if (!closing.get()) disconnect.setEnabled(true); } catch (Exception e) { Wire.close(current.getAndSet(null)); output.accept("Connection failed: " + e.getCause()); if (!closing.get()) connect.setEnabled(true); } }
            }.execute();
        });
        disconnect.addActionListener(event -> {
            disconnect.setEnabled(false); new SwingWorker<Void,Void>() {
                protected Void doInBackground() { Wire.close(current.getAndSet(null)); return null; }
                protected void done() { connect.setEnabled(true); }
            }.execute();
        });
        JPanel buttons = new JPanel(); buttons.add(connect); buttons.add(disconnect);
        window.add(new JLabel("DEMO ONLY - software certificates; no physical UKey, SKF or SM2"), BorderLayout.NORTH);
        window.add(new JScrollPane(log)); window.add(buttons, BorderLayout.SOUTH);
        window.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);
        window.addWindowListener(new java.awt.event.WindowAdapter() { public void windowClosed(java.awt.event.WindowEvent e) { closing.set(true); new Thread(() -> Wire.close(current.getAndSet(null))).start(); } });
        window.pack(); window.setLocationRelativeTo(null); window.setVisible(true);
    }
}
