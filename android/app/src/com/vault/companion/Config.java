package com.vault.companion;

import android.content.Context;
import android.content.SharedPreferences;

public class Config {
    private static final String PREF_NAME = "vault_prefs";
    private static final String KEY_SERVER_IP = "server_ip";
    public static final String DEFAULT_IP = "192.168.1.153";

    public static String getServerIp(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
        return prefs.getString(KEY_SERVER_IP, DEFAULT_IP);
    }

    public static void setServerIp(Context context, String ip) {
        SharedPreferences prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE);
        prefs.edit().putString(KEY_SERVER_IP, ip.trim()).apply();
    }

    public static String getJukeboxUrl(Context context) {
        return "http://" + getServerIp(context) + ":8085";
    }

    public static String getQbittorrentUrl(Context context) {
        return "http://" + getServerIp(context) + ":8080";
    }

    public static String getSmbUri(Context context) {
        return "smb://" + getServerIp(context) + "/Storage";
    }
}
