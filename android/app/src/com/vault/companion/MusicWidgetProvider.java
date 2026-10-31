package com.vault.companion;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.widget.RemoteViews;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class MusicWidgetProvider extends AppWidgetProvider {
    public static final String ACTION_PLAY_PAUSE = "com.vault.companion.ACTION_PLAY_PAUSE";
    public static final String ACTION_NEXT = "com.vault.companion.ACTION_NEXT";
    public static final String ACTION_VOL_UP = "com.vault.companion.ACTION_VOL_UP";
    public static final String ACTION_VOL_DOWN = "com.vault.companion.ACTION_VOL_DOWN";
    public static final String ACTION_REFRESH = "com.vault.companion.ACTION_REFRESH";

    private static double currentVolume = 30.0;

    @Override
    public void onUpdate(Context context, AppWidgetManager appWidgetManager, int[] appWidgetIds) {
        for (int widgetId : appWidgetIds) {
            updateWidgetUI(context, appWidgetManager, widgetId, "Vault Jukebox", "Tap to refresh", false);
        }
        fetchStatusAsync(context);
    }

    @Override
    public void onReceive(final Context context, Intent intent) {
        super.onReceive(context, intent);
        String action = intent != null ? intent.getAction() : null;

        if (ACTION_PLAY_PAUSE.equals(action)) {
            sendControlAsync(context, "toggle_play", null);
        } else if (ACTION_NEXT.equals(action)) {
            sendControlAsync(context, "next", null);
        } else if (ACTION_VOL_UP.equals(action)) {
            currentVolume = Math.min(80.0, currentVolume + 10.0);
            sendControlAsync(context, "volume", currentVolume);
        } else if (ACTION_VOL_DOWN.equals(action)) {
            currentVolume = Math.max(0.0, currentVolume - 10.0);
            sendControlAsync(context, "volume", currentVolume);
        } else if (ACTION_REFRESH.equals(action)) {
            fetchStatusAsync(context);
        }
    }

    public static void triggerUpdate(Context context) {
        Intent intent = new Intent(context, MusicWidgetProvider.class);
        intent.setAction(ACTION_REFRESH);
        context.sendBroadcast(intent);
    }

    private static void updateWidgetUI(Context context, AppWidgetManager appWidgetManager, int widgetId,
                                       String title, String artist, boolean isPlaying) {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.widget_music);
        views.setTextViewText(R.id.widget_title, title);
        views.setTextViewText(R.id.widget_artist, artist);
        views.setTextViewText(R.id.btn_widget_playpause, isPlaying ? "⏸" : "▶");

        // Pending Intents
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            flags |= PendingIntent.FLAG_IMMUTABLE;
        }

        // Tap title to refresh
        Intent refreshIntent = new Intent(context, MusicWidgetProvider.class);
        refreshIntent.setAction(ACTION_REFRESH);
        views.setOnClickPendingIntent(R.id.widget_root, PendingIntent.getBroadcast(context, 100, refreshIntent, flags));

        // Play/Pause
        Intent playIntent = new Intent(context, MusicWidgetProvider.class);
        playIntent.setAction(ACTION_PLAY_PAUSE);
        views.setOnClickPendingIntent(R.id.btn_widget_playpause, PendingIntent.getBroadcast(context, 101, playIntent, flags));

        // Next
        Intent nextIntent = new Intent(context, MusicWidgetProvider.class);
        nextIntent.setAction(ACTION_NEXT);
        views.setOnClickPendingIntent(R.id.btn_widget_next, PendingIntent.getBroadcast(context, 102, nextIntent, flags));

        // Vol Up
        Intent volUpIntent = new Intent(context, MusicWidgetProvider.class);
        volUpIntent.setAction(ACTION_VOL_UP);
        views.setOnClickPendingIntent(R.id.btn_widget_volup, PendingIntent.getBroadcast(context, 103, volUpIntent, flags));

        // Vol Down
        Intent volDownIntent = new Intent(context, MusicWidgetProvider.class);
        volDownIntent.setAction(ACTION_VOL_DOWN);
        views.setOnClickPendingIntent(R.id.btn_widget_voldown, PendingIntent.getBroadcast(context, 104, volDownIntent, flags));

        appWidgetManager.updateAppWidget(widgetId, views);
    }

    private static void fetchStatusAsync(final Context context) {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    URL url = new URL(Config.getJukeboxUrl(context) + "/api/status");
                    HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                    conn.setConnectTimeout(3000);
                    conn.setReadTimeout(3000);

                    if (conn.getResponseCode() == 200) {
                        BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                        StringBuilder sb = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) {
                            sb.append(line);
                        }
                        reader.close();

                        JSONObject obj = new JSONObject(sb.toString());
                        final String title = obj.optString("title", "Nothing Playing");
                        final String artist = obj.optString("artist", "");
                        final boolean isPlaying = obj.optBoolean("playing", false) && !obj.optBoolean("paused", false);
                        currentVolume = obj.optDouble("volume", 30.0);

                        AppWidgetManager mgr = AppWidgetManager.getInstance(context);
                        ComponentName cn = new ComponentName(context, MusicWidgetProvider.class);
                        int[] ids = mgr.getAppWidgetIds(cn);
                        for (int id : ids) {
                            updateWidgetUI(context, mgr, id, title, artist, isPlaying);
                        }
                    }
                } catch (Exception ignored) {
                }
            }
        }).start();
    }

    private static void sendControlAsync(final Context context, final String action, final Object value) {
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    URL url = new URL(Config.getJukeboxUrl(context) + "/api/control");
                    HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setRequestProperty("Content-Type", "application/json");
                    conn.setConnectTimeout(3000);
                    conn.setReadTimeout(3000);
                    conn.setDoOutput(true);

                    String json;
                    if (value != null) {
                        json = "{\"action\":\"" + action + "\",\"value\":" + value + "}";
                    } else {
                        json = "{\"action\":\"" + action + "\"}";
                    }

                    OutputStream os = conn.getOutputStream();
                    os.write(json.getBytes("UTF-8"));
                    os.flush();
                    os.close();

                    conn.getResponseCode();
                    Thread.sleep(250);
                    fetchStatusAsync(context);
                } catch (Exception ignored) {
                }
            }
        }).start();
    }
}
