package com.vault.companion;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Toast;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class ShareReceiverActivity extends Activity {
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent intent = getIntent();
        String action = intent != null ? intent.getAction() : null;

        if (Intent.ACTION_SEND.equals(action) && "text/plain".equals(intent.getType())) {
            String sharedText = intent.getStringExtra(Intent.EXTRA_TEXT);
            handleSharedText(sharedText);
        } else if (Intent.ACTION_VIEW.equals(action) && intent.getData() != null) {
            Uri data = intent.getData();
            if ("magnet".equalsIgnoreCase(data.getScheme())) {
                handleMagnetLink(data.toString());
            } else {
                handleSharedText(data.toString());
            }
        } else {
            finish();
        }
    }

    private void handleSharedText(String text) {
        if (text == null || text.trim().isEmpty()) {
            Toast.makeText(this, "Empty shared link", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        // Check if text contains a magnet link
        if (text.contains("magnet:?")) {
            int idx = text.indexOf("magnet:?");
            String magnet = text.substring(idx).trim();
            handleMagnetLink(magnet);
            return;
        }

        // Extract URL or query for YouTube queue
        String urlOrQuery = extractUrl(text);
        if (urlOrQuery == null) {
            urlOrQuery = text.trim();
        }

        final String finalTarget = urlOrQuery;
        Toast.makeText(this, "Adding to Vault Queue...", Toast.LENGTH_SHORT).show();

        new Thread(new Runnable() {
            @Override
            public void run() {
                final boolean success = sendToJukebox(finalTarget);
                mainHandler.post(new Runnable() {
                    @Override
                    public void run() {
                        if (success) {
                            Toast.makeText(ShareReceiverActivity.this, "Added to Vault Jukebox!", Toast.LENGTH_SHORT).show();
                            MusicWidgetProvider.triggerUpdate(ShareReceiverActivity.this);
                        } else {
                            Toast.makeText(ShareReceiverActivity.this, "Failed to connect to Vault Server", Toast.LENGTH_LONG).show();
                        }
                        finish();
                    }
                });
            }
        }).start();
    }

    private void handleMagnetLink(final String magnetUrl) {
        Toast.makeText(this, "Sending Magnet to qBittorrent...", Toast.LENGTH_SHORT).show();

        new Thread(new Runnable() {
            @Override
            public void run() {
                final boolean success = sendToQbittorrent(magnetUrl);
                mainHandler.post(new Runnable() {
                    @Override
                    public void run() {
                        if (success) {
                            Toast.makeText(ShareReceiverActivity.this, "Torrent added to Gentoo Server!", Toast.LENGTH_SHORT).show();
                        } else {
                            Toast.makeText(ShareReceiverActivity.this, "Failed to add torrent to qBittorrent", Toast.LENGTH_LONG).show();
                        }
                        finish();
                    }
                });
            }
        }).start();
    }

    private String extractUrl(String text) {
        Pattern pattern = Pattern.compile("(https?://[\\w\\-\\._~:/?#\\[\\]@!$&'()*+,;=]+)");
        Matcher matcher = pattern.matcher(text);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return null;
    }

    private boolean sendToJukebox(String query) {
        try {
            URL url = new URL(Config.getJukeboxUrl(this) + "/api/add");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setConnectTimeout(4000);
            conn.setReadTimeout(4000);
            conn.setDoOutput(true);

            String json = "{\"query\":\"" + query.replace("\"", "\\\"") + "\"}";
            OutputStream os = conn.getOutputStream();
            os.write(json.getBytes("UTF-8"));
            os.flush();
            os.close();

            return conn.getResponseCode() == 200;
        } catch (Exception e) {
            return false;
        }
    }

    private boolean sendToQbittorrent(String magnet) {
        try {
            URL url = new URL(Config.getQbittorrentUrl(this) + "/api/v2/torrents/add");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
            conn.setConnectTimeout(4000);
            conn.setReadTimeout(4000);
            conn.setDoOutput(true);

            String body = "urls=" + URLEncoder.encode(magnet, "UTF-8");
            OutputStream os = conn.getOutputStream();
            os.write(body.getBytes("UTF-8"));
            os.flush();
            os.close();

            return conn.getResponseCode() == 200;
        } catch (Exception e) {
            return false;
        }
    }
}
