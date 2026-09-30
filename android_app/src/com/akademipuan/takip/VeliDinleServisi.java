package com.akademipuan.takip;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.pm.ServiceInfo;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.VibrationEffect;
import android.os.Vibrator;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.Charset;

public class VeliDinleServisi extends Service {
    public static final String HOME = "https://takip.akademipuan.com";
    public static final String PREF = "veli_dinle";
    public static final String KANAL_DINLE = "veli-dinle";
    public static final String KANAL_ALARM = "veli-alarm";
    private static final int DINLE_ID = 110;
    private static final int MESAJ_ID = 111;

    private volatile boolean calisiyor;
    private Thread isci;
    private MediaPlayer calar;
    private PowerManager.WakeLock kilit;
    private PowerManager.WakeLock dinleKilit;

    public static void anahtarKaydet(Context ctx, String anahtar) {
        android.content.SharedPreferences p = ctx.getSharedPreferences(PREF, MODE_PRIVATE);
        if (anahtar == null || anahtar.equals(p.getString("anahtar", ""))) return;
        p.edit().putString("anahtar", anahtar).putInt("son", -1).apply();
    }

    public static void baslat(Context ctx) {
        ctx.getSharedPreferences(PREF, MODE_PRIVATE).edit().putBoolean("aktif", true).apply();
        Intent intent = new Intent(ctx, VeliDinleServisi.class);
        if (Build.VERSION.SDK_INT >= 26) {
            ctx.startForegroundService(intent);
        } else {
            ctx.startService(intent);
        }
    }

    public static void durdur(Context ctx) {
        ctx.getSharedPreferences(PREF, MODE_PRIVATE).edit()
            .putBoolean("aktif", false).remove("anahtar").putInt("son", -1).apply();
        ctx.stopService(new Intent(ctx, VeliDinleServisi.class));
    }

    @Override
    public void onCreate() {
        super.onCreate();
        kanallariKur();
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm != null) {
            kilit = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "akademipuan:veli");
            kilit.setReferenceCounted(false);
            dinleKilit = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "akademipuan:dinle");
            dinleKilit.setReferenceCounted(false);
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(DINLE_ID, dinlemeBildirimi(), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else if (Build.VERSION.SDK_INT >= 29) {
            startForeground(DINLE_ID, dinlemeBildirimi(), ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(DINLE_ID, dinlemeBildirimi());
        }
        if (intent != null && "dur".equals(intent.getAction())) {
            alarmDurdur();
            return START_STICKY;
        }
        if (dinleKilit != null && !dinleKilit.isHeld()) dinleKilit.acquire();
        if (!calisiyor) {
            calisiyor = true;
            isci = new Thread(new Runnable() {
                @Override
                public void run() {
                    dinle();
                }
            }, "veli-dinle");
            isci.start();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        calisiyor = false;
        if (isci != null) isci.interrupt();
        alarmDurdur();
        if (kilit != null && kilit.isHeld()) kilit.release();
        if (dinleKilit != null && dinleKilit.isHeld()) dinleKilit.release();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void kanallariKur() {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm == null) return;
        NotificationChannel dinle = new NotificationChannel(KANAL_DINLE, "Öğretmen mesajı dinleme", NotificationManager.IMPORTANCE_MIN);
        dinle.setShowBadge(false);
        dinle.setSound(null, null);
        nm.createNotificationChannel(dinle);

        Uri alarm = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
        if (alarm == null) alarm = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
        AudioAttributes ses = new AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ALARM)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build();
        NotificationChannel mesaj = new NotificationChannel(KANAL_ALARM, "Öğretmen mesajı", NotificationManager.IMPORTANCE_HIGH);
        mesaj.setDescription("Öğretmen veri girdiğinde yazılı bildirim ve alarm");
        mesaj.enableVibration(true);
        mesaj.setVibrationPattern(new long[]{0, 900, 250, 900, 250, 900});
        mesaj.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        mesaj.setSound(alarm, ses);
        try { mesaj.setBypassDnd(true); } catch (Exception ignored) {}
        nm.createNotificationChannel(mesaj);
    }

    private Notification dinlemeBildirimi() {
        Intent ac = new Intent(this, MainActivity.class);
        ac.putExtra("open_veli", true);
        ac.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(this, 1, ac, pendingBayrak());
        Notification.Builder b = bildirimKur(KANAL_DINLE)
            .setContentTitle("Akademi Puan")
            .setContentText("Öğretmen mesajları dinleniyor")
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentIntent(pi)
            .setOngoing(true);
        return b.build();
    }

    private void dinle() {
        while (calisiyor) {
            try {
                String anahtar = getSharedPreferences(PREF, MODE_PRIVATE).getString("anahtar", "");
                if (anahtar == null || anahtar.length() == 0) {
                    Thread.sleep(4000);
                    continue;
                }
                int son = getSharedPreferences(PREF, MODE_PRIVATE).getInt("son", -1);
                JSONObject veri = oku(HOME + "/veli/haber/cihaz?t=" + URLEncoder.encode(anahtar, "UTF-8") + "&son=" + son);
                if (veri == null) {
                    Thread.sleep(3000);
                    continue;
                }
                if (!veri.optBoolean("ok", false)) {
                    getSharedPreferences(PREF, MODE_PRIVATE).edit()
                        .putBoolean("aktif", false).remove("anahtar").putInt("son", -1).apply();
                    stopSelf();
                    return;
                }
                if (son < 0) {
                    getSharedPreferences(PREF, MODE_PRIVATE).edit().putInt("son", veri.optInt("son", 0)).apply();
                    continue;
                }
                JSONArray haber = veri.optJSONArray("haber");
                if (haber != null && haber.length() > 0) {
                    String metin = "";
                    String tur = "duyuru";
                    for (int i = 0; i < haber.length(); i++) {
                        JSONObject h = haber.getJSONObject(i);
                        son = Math.max(son, h.optInt("id", son));
                        metin = h.optString("metin", metin);
                        tur = h.optString("tur", tur);
                    }
                    getSharedPreferences(PREF, MODE_PRIVATE).edit().putInt("son", son).apply();
                    mesajGoster(tur, metin);
                }
            } catch (InterruptedException e) {
                return;
            } catch (Exception ignored) {
            }
            try {
                Thread.sleep(4000);
            } catch (InterruptedException e) {
                return;
            }
        }
    }

    private JSONObject oku(String adres) {
        HttpURLConnection bag = null;
        try {
            bag = (HttpURLConnection) new URL(adres).openConnection();
            bag.setConnectTimeout(8000);
            bag.setReadTimeout(8000);
            bag.setRequestProperty("Accept", "application/json");
            int kod = bag.getResponseCode();
            if (kod == 401 || kod == 403) return new JSONObject().put("ok", false);
            if (kod != 200) return null;
            BufferedReader okuyucu = new BufferedReader(new InputStreamReader(bag.getInputStream(), Charset.forName("UTF-8")));
            StringBuilder sb = new StringBuilder();
            String satir;
            while ((satir = okuyucu.readLine()) != null) sb.append(satir);
            okuyucu.close();
            return new JSONObject(sb.toString());
        } catch (Exception e) {
            return null;
        } finally {
            if (bag != null) bag.disconnect();
        }
    }

    private void mesajGoster(String tur, String metin) {
        String baslik = "Öğretmen mesajı";
        if ("uyari".equals(tur)) baslik = "Uyarı";
        else if ("olumlu".equals(tur)) baslik = "Olumlu not";
        else if ("odev".equals(tur)) baslik = "Ödev";
        else if ("duyuru".equals(tur)) baslik = "Duyuru";

        Intent ac = new Intent(this, MainActivity.class);
        ac.putExtra("open_veli", true);
        ac.putExtra("alarm_dur", true);
        ac.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(this, 2, ac, pendingBayrak());

        Intent dur = new Intent(this, VeliDinleServisi.class);
        dur.setAction("dur");
        PendingIntent durPi = PendingIntent.getService(this, 3, dur, pendingBayrak());

        Notification.Builder b = bildirimKur(KANAL_ALARM)
            .setContentTitle(baslik)
            .setContentText(metin)
            .setStyle(new Notification.BigTextStyle().bigText(metin))
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentIntent(pi)
            .setDeleteIntent(durPi)
            .setAutoCancel(true)
            .setOngoing(false)
            .setOnlyAlertOnce(false);
        if (Build.VERSION.SDK_INT >= 21) {
            b.setVisibility(Notification.VISIBILITY_PUBLIC);
            b.setPriority(Notification.PRIORITY_MAX);
            b.setCategory(Notification.CATEGORY_ALARM);
            b.setFullScreenIntent(pi, true);
        }
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(MESAJ_ID, b.build());
        alarmCal();
    }

    private Notification.Builder bildirimKur(String kanal) {
        if (Build.VERSION.SDK_INT >= 26) {
            return new Notification.Builder(this, kanal);
        }
        return new Notification.Builder(this);
    }

    private int pendingBayrak() {
        int bayrak = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) bayrak |= PendingIntent.FLAG_IMMUTABLE;
        return bayrak;
    }

    private void alarmCal() {
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                try {
                    if (kilit != null && !kilit.isHeld()) kilit.acquire(25000);
                    alarmDurdur();
                    Uri uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
                    if (uri == null) uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
                    calar = new MediaPlayer();
                    calar.setDataSource(VeliDinleServisi.this, uri);
                    if (Build.VERSION.SDK_INT >= 21) {
                        calar.setAudioAttributes(new AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ALARM)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                            .build());
                    } else {
                        calar.setAudioStreamType(AudioManager.STREAM_ALARM);
                    }
                    calar.setLooping(true);
                    calar.prepare();
                    calar.start();
                    Vibrator vib = (Vibrator) getSystemService(VIBRATOR_SERVICE);
                    if (vib != null) {
                        if (Build.VERSION.SDK_INT >= 26) {
                            vib.vibrate(VibrationEffect.createWaveform(new long[]{0, 900, 250, 900}, 0));
                        } else {
                            vib.vibrate(new long[]{0, 900, 250, 900}, 0);
                        }
                    }
                    new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {
                        @Override
                        public void run() {
                            alarmDurdur();
                        }
                    }, 25000);
                } catch (Exception ignored) {
                }
            }
        });
    }

    private void alarmDurdur() {
        try {
            if (calar != null) {
                if (calar.isPlaying()) calar.stop();
                calar.release();
            }
        } catch (Exception ignored) {
        }
        calar = null;
        Vibrator vib = (Vibrator) getSystemService(VIBRATOR_SERVICE);
        if (vib != null) vib.cancel();
        if (kilit != null && kilit.isHeld()) kilit.release();
    }
}
