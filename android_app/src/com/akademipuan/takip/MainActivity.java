package com.akademipuan.takip;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.PowerManager;
import android.provider.Settings;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final String HOME_URL = "https://takip.akademipuan.com";
    private static final int FILE_CHOOSER_REQUEST = 42;
    private static final int STORAGE_PERMISSION_REQUEST = 43;
    private static final int NOTIFY_PERMISSION_REQUEST = 44;

    private WebView webView;
    private ProgressBar progressBar;
    private ValueCallback<Uri[]> filePathCallback;
    static volatile boolean ekranda;

    @Override
    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (Build.VERSION.SDK_INT >= 21) {
            getWindow().setStatusBarColor(Color.WHITE);
            getWindow().setNavigationBarColor(Color.WHITE);
        }
        if (Build.VERSION.SDK_INT >= 23) {
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
            );
        }

        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);

        root.addView(webView, new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ));
        FrameLayout.LayoutParams progressParams = new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            dp(3)
        );
        root.addView(progressBar, progressParams);
        setContentView(root);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        if (Build.VERSION.SDK_INT >= 21) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        }

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= 21) {
            cookieManager.setAcceptThirdPartyCookies(webView, true);
        }

        webView.addJavascriptInterface(new AndroidBridge(), "AndroidApp");
        webView.setWebViewClient(new AppWebViewClient());
        webView.setWebChromeClient(new AppChromeClient());
        webView.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String contentDisposition, String mimeType, long contentLength) {
                if (Build.VERSION.SDK_INT < 29 && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, STORAGE_PERMISSION_REQUEST);
                    return;
                }
                startDownload(url, contentDisposition, mimeType);
            }
        });

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(HOME_URL);
        }
        bildirimIzniIste();
        sayfayiAc(getIntent());
    }

    @Override
    protected void onResume() {
        super.onResume();
        ekranda = true;
    }

    @Override
    protected void onPause() {
        ekranda = false;
        super.onPause();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
            return;
        }
        super.onBackPressed();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST || filePathCallback == null) {
            return;
        }

        Uri[] results = null;
        if (resultCode == RESULT_OK && data != null) {
            if (data.getClipData() != null) {
                int count = data.getClipData().getItemCount();
                results = new Uri[count];
                for (int i = 0; i < count; i++) {
                    results[i] = data.getClipData().getItemAt(i).getUri();
                }
            } else if (data.getData() != null) {
                results = new Uri[]{data.getData()};
            }
        }
        filePathCallback.onReceiveValue(results);
        filePathCallback = null;
    }

    private void startDownload(String url, String contentDisposition, String mimeType) {
        try {
            String fileName = URLUtil.guessFileName(url, contentDisposition, mimeType);
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
            request.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url));
            request.setMimeType(mimeType);
            request.setTitle(fileName);
            request.setDescription(getString(R.string.download_started));
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName);
            DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            if (manager != null) {
                manager.enqueue(request);
                Toast.makeText(this, R.string.download_started, Toast.LENGTH_SHORT).show();
            }
        } catch (Exception ex) {
            Toast.makeText(this, ex.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        sayfayiAc(intent);
    }

    private void sayfayiAc(Intent intent) {
        if (intent != null && intent.getBooleanExtra("alarm_dur", false)) {
            Intent dur = new Intent(this, VeliDinleServisi.class);
            dur.setAction("dur");
            startService(dur);
        }
        if (intent != null && intent.getBooleanExtra("open_veli", false) && webView != null) {
            webView.loadUrl(HOME_URL + "/veli");
        }
    }

    private void bildirimIzniIste() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFY_PERMISSION_REQUEST);
        }
    }

    private void pilKorumasiniAc() {
        if (Build.VERSION.SDK_INT < 23) return;
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm == null || pm.isIgnoringBatteryOptimizations(getPackageName())) return;
        if (getSharedPreferences(VeliDinleServisi.PREF, MODE_PRIVATE).getBoolean("pil_soruldu", false)) return;
        getSharedPreferences(VeliDinleServisi.PREF, MODE_PRIVATE).edit().putBoolean("pil_soruldu", true).apply();
        try {
            Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
            intent.setData(Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        } catch (Exception ignored) {
        }
    }

    private void veliDinlemeyiAyarla(String url) {
        if (url == null) return;
        boolean veli = url.contains("/veli") && !url.contains("/veli/giris") && !url.contains("/veli/cikis");
        if (veli) {
            VeliDinleServisi.baslat(this);
            pilKorumasiniAc();
        } else if (url.contains("/veli/giris") || url.contains("/veli/cikis") || url.contains("/login")) {
            VeliDinleServisi.durdur(this);
        }
    }

    private class AppWebViewClient extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, String url) {
            if (url == null) return false;
            if (url.startsWith("http://") || url.startsWith("https://")) {
                return false;
            }
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                return true;
            } catch (Exception ignored) {
                return false;
            }
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            super.onPageFinished(view, url);
            progressBar.setVisibility(View.GONE);
            view.evaluateJavascript("window.print=function(){AndroidApp.printPage();};", null);
            veliDinlemeyiAyarla(url);
        }
    }

    private class AppChromeClient extends WebChromeClient {
        @Override
        public void onProgressChanged(WebView view, int newProgress) {
            progressBar.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
            progressBar.setProgress(newProgress);
        }

        @Override
        public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
            if (filePathCallback != null) {
                filePathCallback.onReceiveValue(null);
            }
            filePathCallback = callback;
            Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("*/*");
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
            startActivityForResult(Intent.createChooser(intent, getString(R.string.file_chooser_title)), FILE_CHOOSER_REQUEST);
            return true;
        }
    }

    public class AndroidBridge {
        @JavascriptInterface
        public void printPage() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    PrintManager printManager = (PrintManager) getSystemService(Context.PRINT_SERVICE);
                    if (printManager == null || webView == null) return;
                    PrintDocumentAdapter adapter;
                    if (Build.VERSION.SDK_INT >= 21) {
                        adapter = webView.createPrintDocumentAdapter("Akademi Puan");
                    } else {
                        adapter = webView.createPrintDocumentAdapter();
                    }
                    printManager.print("Akademi Puan", adapter, new PrintAttributes.Builder().build());
                }
            });
        }

        @JavascriptInterface
        public void veliBaglan(final String anahtar) {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    VeliDinleServisi.anahtarKaydet(MainActivity.this, anahtar);
                    bildirimIzniIste();
                    VeliDinleServisi.baslat(MainActivity.this);
                    pilKorumasiniAc();
                }
            });
        }

        @JavascriptInterface
        public String durum() {
            boolean izin = Build.VERSION.SDK_INT < 33
                || checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
            boolean pil = true;
            if (Build.VERSION.SDK_INT >= 23) {
                PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
                pil = pm == null || pm.isIgnoringBatteryOptimizations(getPackageName());
            }
            String anahtar = getSharedPreferences(VeliDinleServisi.PREF, MODE_PRIVATE).getString("anahtar", "");
            return "{\"izin\":" + izin + ",\"pil\":" + pil + ",\"bagli\":" + (anahtar != null && anahtar.length() > 0) + "}";
        }

        @JavascriptInterface
        public void ayarlariAc() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    try {
                        if (Build.VERSION.SDK_INT >= 23) {
                            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
                            if (pm != null && !pm.isIgnoringBatteryOptimizations(getPackageName())) {
                                Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                                intent.setData(Uri.parse("package:" + getPackageName()));
                                startActivity(intent);
                                return;
                            }
                        }
                        Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                        intent.setData(Uri.parse("package:" + getPackageName()));
                        startActivity(intent);
                    } catch (Exception ignored) {
                    }
                }
            });
        }

        @JavascriptInterface
        public void veliDinle() {
            runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    bildirimIzniIste();
                    VeliDinleServisi.baslat(MainActivity.this);
                    pilKorumasiniAc();
                }
            });
        }
    }
}
