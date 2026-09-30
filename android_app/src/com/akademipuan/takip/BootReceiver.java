package com.akademipuan.takip;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || intent.getAction() == null) return;
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())
            && !"android.intent.action.QUICKBOOT_POWERON".equals(intent.getAction())) {
            return;
        }
        SharedPreferences p = context.getSharedPreferences(VeliDinleServisi.PREF, Context.MODE_PRIVATE);
        if (p.getBoolean("aktif", false)) {
            VeliDinleServisi.baslat(context);
        }
    }
}
