package com.example.myapplication

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.os.Bundle
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ProgressBar
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var errorTextView: TextView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Hide the action bar for a full-screen experience
        supportActionBar?.hide()

        webView = findViewById(R.id.webview)
        progressBar = findViewById(R.id.progressBar)
        errorTextView = findViewById(R.id.errorText)

        // --- IMPORTANT ---
        // Replace this URL with the live URL of your deployed Streamlit/FastAPI app
        val appUrl = "https://your-deployed-app.com"

        // Configure WebView settings
        webView.settings.javaScriptEnabled = true // Enable JavaScript
        webView.settings.domStorageEnabled = true // Enable DOM Storage for modern web apps

        // Set up clients to handle loading progress and events
        setupWebViewClients()

        // Load your web app
        webView.loadUrl(appUrl)

        // Handle the back button press to navigate within the WebView's history
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack()
                } else {
                    // If there's no history, finish the activity (close the app)
                    finish()
                }
            }
        })
    }

    private fun setupWebViewClients() {
        // WebChromeClient handles UI-related changes like progress updates
        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                super.onProgressChanged(view, newProgress)
                if (newProgress < 100) {
                    progressBar.visibility = View.VISIBLE
                    progressBar.progress = newProgress
                } else {
                    progressBar.visibility = View.GONE
                }
            }
        }

        // WebViewClient handles content-related events like page loads and errors
        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                // When a page starts loading, ensure the error message is hidden
                errorTextView.visibility = View.GONE
                webView.visibility = View.VISIBLE
            }

            // This method is deprecated for API 23+ but required for older versions
            override fun onReceivedError(view: WebView, errorCode: Int, description: String, failingUrl: String) {
                super.onReceivedError(view, errorCode, description, failingUrl)
                showErrorView()
            }

            private fun showErrorView() {
                // In case of an error, hide the WebView and show the error message
                webView.visibility = View.GONE
                errorTextView.visibility = View.VISIBLE
            }
        }
    }
}

