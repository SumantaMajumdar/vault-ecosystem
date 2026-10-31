package com.vault.companion;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        final EditText editIp = (EditText) findViewById(R.id.edit_server_ip);
        editIp.setText(Config.getServerIp(this));

        Button btnSave = (Button) findViewById(R.id.btn_save_ip);
        btnSave.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String ip = editIp.getText().toString().trim();
                if (!ip.isEmpty()) {
                    Config.setServerIp(MainActivity.this, ip);
                    Toast.makeText(MainActivity.this, "Server IP saved: " + ip, Toast.LENGTH_SHORT).show();
                    MusicWidgetProvider.triggerUpdate(MainActivity.this);
                }
            }
        });

        Button btnJukebox = (Button) findViewById(R.id.btn_open_jukebox);
        btnJukebox.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(Config.getJukeboxUrl(MainActivity.this)));
                startActivity(i);
            }
        });

        Button btnQbit = (Button) findViewById(R.id.btn_open_qbittorrent);
        btnQbit.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(Config.getQbittorrentUrl(MainActivity.this)));
                startActivity(i);
            }
        });

        Button btnNas = (Button) findViewById(R.id.btn_open_nas);
        btnNas.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String smbUri = Config.getSmbUri(MainActivity.this);
                Intent i = new Intent(Intent.ACTION_VIEW);
                i.setData(Uri.parse(smbUri));
                try {
                    startActivity(i);
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "NAS Path: " + smbUri + "\nUse a file manager (like CX File Explorer, Solid, or VLC) to connect via SMB.", Toast.LENGTH_LONG).show();
                }
            }
        });
    }
}
