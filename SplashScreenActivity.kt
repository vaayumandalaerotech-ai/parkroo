package com.example.myapplication

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.appcompat.app.AppCompatActivity

@SuppressLint("CustomSplashScreen")
class SplashScreenActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_splash_screen)

        // Hide the action bar for a full-screen experience
        supportActionBar?.hide()

        // Delay for a short period (e.g., 2000 milliseconds) and then start the main activity
        Handler(Looper.getMainLooper()).postDelayed({
            // Create an Intent to start MainActivity
            val intent = Intent(this, MainActivity::class.java)
            startActivity(intent)

            // Finish the splash activity so the user can't navigate back to it
            finish()
        }, 2000) // 2-second delay
    }
}
