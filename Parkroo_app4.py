# --- Combined App ---
# This single file contains the FastAPI backend AND the HTML/CSS/JS frontend.
# To run it, just execute: python parkroo_app.py

import uvicorn
import threading
import requests
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import pandas
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, Literal, List
import time
import json 
import os
import sqlite3
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from decimal import Decimal
from zoneinfo import ZoneInfo
import openpyxl
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import stripe
import logging
import html.parser
from contextlib import asynccontextmanager
from streamlit_searchbox import st_searchbox

# ==============================================================================
# --- 0. FRONTEND (HTML/CSS/JS) CODE ---
# ==============================================================================

# Your entire HTML file is stored in this variable
HTML_FRONTEND = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Parkroo - Express Parking Australia</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary-color: #2d7a5f;
            --secondary-color: #667eea;
            --danger-color: #dc3545;
            --success-color: #28a745;
            --warning-color: #ffc107;
            --dark-bg: #1a1a2e;
            --card-bg: #ffffff;
            --text-primary: #2c3e50;
            --text-secondary: #6c757d;
            --border-color: #e0e0e0;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }

        .app-container {
            display: flex;
            flex-direction: column;
            height: 100vh;
        }

        /* Header Styles */
        .header {
            background: white;
            padding: 15px 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .logo-section {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .logo {
            width: 60px;
            height: 60px;
        }

        .brand-text h1 {
            color: var(--primary-color);
            font-size: 1.5em;
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .brand-text p {
            color: var(--text-secondary);
            font-size: 0.9em;
            margin: 0;
        }

        .header-actions {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        /* Search Bar */
        .search-container {
            flex: 1;
            max-width: 600px;
            margin: 0 20px;
            position: relative;
        }

        .search-input {
            width: 100%;
            padding: 12px 45px 12px 20px;
            border: 2px solid var(--border-color);
            border-radius: 25px;
            font-size: 1em;
            transition: all 0.3s;
        }

        .search-input:focus {
            outline: none;
            border-color: var(--secondary-color);
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .search-btn {
            position: absolute;
            right: 5px;
            top: 50%;
            transform: translateY(-50%);
            background: var(--primary-color);
            border: none;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            color: white;
            cursor: pointer;
            transition: all 0.3s;
        }

        .search-btn:hover {
            background: #1e5245;
            transform: translateY(-50%) scale(1.1);
        }

        /* Button Styles */
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 20px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 0.9em;
        }

        .btn-primary {
            background: var(--primary-color);
            color: white;
        }

        .btn-primary:hover {
            background: #1e5245;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }

        .btn-secondary {
            background: var(--secondary-color);
            color: white;
        }

        .btn-icon {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2em;
        }

        /* Main Content */
        .main-content {
            display: flex;
            flex: 1;
            overflow: hidden;
        }

        /* Sidebar */
        .sidebar {
            width: 350px;
            background: white;
            overflow-y: auto;
            box-shadow: 2px 0 10px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }

        .sidebar.collapsed {
            width: 0;
            overflow: hidden;
        }

        .sidebar-header {
            padding: 20px;
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
        }

        .sidebar-section {
            padding: 20px;
            border-bottom: 1px solid var(--border-color);
        }

        .sidebar-section h3 {
            color: var(--text-primary);
            margin-bottom: 15px;
            font-size: 1.1em;
        }

        .sidebar-section .btn {
            width: 100%;
            margin-top: 10px;
            padding: 12px;
            font-size: 1em;
        }

        /* Parking Spot Card */
        .spot-card {
            background: white;
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 15px;
            border: 2px solid var(--border-color);
            cursor: pointer;
            transition: all 0.3s;
        }

        .spot-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.15);
            border-color: var(--secondary-color);
        }

        .spot-card.selected {
            border-color: var(--primary-color);
            box-shadow: 0 5px 20px rgba(45, 122, 95, 0.3);
        }

        .spot-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .spot-id {
            font-weight: bold;
            font-size: 1.1em;
            color: var(--text-primary);
        }

        .status-badge {
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 0.85em;
            font-weight: 600;
        }

        .status-available {
            background: #d4edda;
            color: #155724;
        }

        .status-occupied {
            background: #f8d7da;
            color: #721c24;
        }

        .spot-details {
            color: var(--text-secondary);
            font-size: 0.9em;
            line-height: 1.6;
        }

        .spot-details i {
            width: 20px;
            color: var(--primary-color);
        }

        .price-info {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid var(--border-color);
        }

        .price {
            font-size: 1.3em;
            font-weight: bold;
            color: var(--primary-color);
        }

        .fee-type {
            padding: 3px 8px;
            background: #fff3cd;
            color: #856404;
            border-radius: 10px;
            font-size: 0.8em;
        }

        /* Map Container */
        .map-container {
            flex: 1;
            position: relative;
        }

        #map {
            width: 100%;
            height: 100%;
        }

        .live-data-loader {
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 8px 15px;
            border-radius: 15px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1001;
            color: #4b5563;
            font-weight: 600;
            font-size: 0.85em;
        }

        /* Stats Bar */
        .stats-bar {
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 10px 20px;
            border-radius: 15px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            display: flex;
            gap: 30px;
            z-index: 1000;
        }
        
        .stat-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .stat-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2em;
        }

        .stat-icon.available {
            background: #d4edda;
            color: #155724;
        }

        .stat-icon.occupied {
            background: #f8d7da;
            color: #721c24;
        }

        .stat-info strong {
            display: block;
            font-size: 1.2em;
            color: var(--text-primary);
        }
        
        .stat-info span {
            font-size: 0.85em;
            color: var(--text-secondary);
        }

        /* Filter Section */
        .filter-group {
            margin-bottom: 15px;
        }

        .filter-group label {
            display: block;
            margin-bottom: 5px;
            color: var(--text-secondary);
            font-size: 0.9em;
            font-weight: 600;
        }

        .filter-select {
            width: 100%;
            padding: 10px;
            border: 2px solid var(--border-color);
            border-radius: 10px;
            font-size: 1em;
            transition: all 0.3s;
        }

        .filter-select:focus {
            outline: none;
            border-color: var(--secondary-color);
        }

        /* Time Selector */
        .time-selector {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }

        .time-input {
            padding: 10px;
            border: 2px solid var(--border-color);
            border-radius: 10px;
            font-size: 0.9em;
            text-align: center;
        }
        
        /* Modal Styles */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.6);
            z-index: 2000;
            display: none;
            align-items: center;
            justify-content: center;
        }
        
        .modal-overlay.active {
            display: flex;
        }
        
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 15px;
            width: 90%;
            max-width: 500px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 15px;
            margin-bottom: 20px;
        }

        .modal-header h2 {
            color: var(--text-primary);
        }

        .close-btn {
            background: none;
            border: none;
            font-size: 1.5em;
            color: var(--text-secondary);
            cursor: pointer;
        }
        
        /* Loading Overlay */
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.7);
            z-index: 1500;
            display: none; /* Hidden by default */
            align-items: center;
            justify-content: center;
        }
        
        .loading-overlay.active {
            display: flex;
        }
        
        .spinner {
            width: 60px;
            height: 60px;
            border: 8px solid var(--border-color);
            border-top-color: var(--primary-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Sidebar Toggle */
        .sidebar-toggle {
            position: absolute;
            left: 0;
            top: 50%;
            transform: translateY(-50%);
            width: 25px;
            height: 60px;
            background: var(--primary-color);
            color: white;
            border: none;
            cursor: pointer;
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2em;
            border-radius: 0 10px 10px 0;
            transition: left 0.3s, top 0.3s;
        }
        
        .sidebar.collapsed + .map-container .sidebar-toggle {
            left: 0;
        }
        
        .sidebar:not(.collapsed) + .map-container .sidebar-toggle { 
            /* Move it left by its own width to sit on top of the sidebar's edge */
            left: 325px; /* 350px (sidebar width) - 25px (button width) */
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .header {
                flex-direction: column;
                gap: 15px;
            }
            .search-container {
                max-width: 100%;
                margin: 0;
            }
            .main-content {
                flex-direction: column;
            }
            .sidebar {
                width: 100%;
                height: 40vh;
                border-bottom: 2px solid var(--border-color);
            }
            .sidebar.collapsed {
                width: 100%;
                height: 0;
            }
            .sidebar + .map-container .sidebar-toggle {
                left: auto;
                right: 0;
                top: 10px;
                width: 60px;
                height: 25px;
                border-radius: 10px 0 0 10px;
            }
            .sidebar.collapsed + .map-container .sidebar-toggle {
                top: 0;
            }
            .stats-bar {
                flex-direction: row;
                bottom: 10px;
                left: 10px;
            }
            .stat-info strong { font-size: 1em; }
            .live-data-loader { bottom: 75px; left: 10px; }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <header class="header">
            <div class="logo-section">
                <img src="https://img.icons8.com/plasticine/100/parking.png" alt="Parkroo Logo" class="logo">
                <div class="brand-text">
                    <h1>PARKROO</h1>
                    <p>Express Parking Australia</p>
                </div>
            </div>
            <div class="search-container">
                <input type="text" id="searchInput" class="search-input" placeholder="Search address (e.g., 'Flinders Street Station')...">
                <button class="search-btn" id="searchBtn" onclick="searchLocation()">
                    <i class="fas fa-search"></i>
                </button>
            </div>
            <div class="header-actions">
                <button class="btn btn-secondary btn-icon" onclick="showModal('profile')"><i class="fas fa-user"></i></button>
                <button class="btn btn-primary" id="authButton" onclick="showModal('login')">Login / Sign Up</button>
            </div>
        </header>

        <main class="main-content">
            <aside class="sidebar" id="sidebar">
                <div class="sidebar-header">
                    <h2>Find Your Spot</h2>
                </div>

                <div class="sidebar-section">
                    <h3>Filters</h3>
                    <div class="filter-group">
                        <label for="cityFilter">Select City</label>
                        <select id="cityFilter" class="filter-select" onchange="loadParkingData()">
                            <option value="melbourne">Melbourne</option>
                            <option value="brisbane">Brisbane</option>
                        </select>
                    </div>
                </div>

                <div class="sidebar-section" id="initial-prompt">
                    <h3>Get Started</h3>
                    <p>Click on the map to set your current location, or use the search bar to find a destination.</p>
                </div>

                <div class="sidebar-section">
                    <h3>Available Spots</h3>
                    <div id="spotList" class="spot-list-container">
                        <p>Loading parking spots...</p>
                        </div>
                </div>
            </aside>

            <div class="map-container">
                <button class="sidebar-toggle" id="sidebarToggle" onclick="toggleSidebar()">
                    <i class="fas fa-chevron-left"></i>
                </button>
                <div id="map"></div>
                <div class="live-data-loader" id="liveLoader" style="display: none;">
                    <i class="fas fa-sync-alt fa-spin" style="margin-right: 8px;"></i> Loading live locations...
                </div>
                <div class="stats-bar">
                    <div class="stat-item">
                        <div class="stat-icon available">
                            <i class="fas fa-check"></i>
                        </div>
                        <div class="stat-info">
                            <strong id="statsAvailable">--</strong>
                            <span>Available</span>
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-icon occupied">
                            <i class="fas fa-times"></i>
                        </div>
                        <div class="stat-info">
                            <strong id="statsOccupied">--</strong>
                            <span>Occupied</span>
                        </div>
                    </div>
                </div>
                <div class="loading-overlay" id="mapLoader">
                    <div class="spinner"></div>
                </div>
            </div>
        </main>
    </div>

    <div class="modal-overlay" id="modalOverlay" onclick="closeModal()">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h2 id="modalTitle">Modal</h2>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div id="modalBody">
                <p>Modal content goes here.</p>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // --- Global State ---
        let map;
        let parkingData = [];
        let markers = [];
        let currentRoute = null;
        let destinationMarker = null;
        let selectedMarker = null;
        let userLocationMarker = null; // <-- FIX 1: Added this line
        
        // --- API Base URL ---
        // We assume the frontend is served from the same host/port as the backend
        const API_BASE_URL = window.location.origin;

        // --- Map Initialization ---
        function initMap() {
            try {
                map = L.map('map').setView([-37.8136, 144.9631], 14); // Default to Melbourne

                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 19,
                    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                }).addTo(map);

                // --- MODIFIED: Load ONLY local data on startup ---
                loadParkingData('temp', false).then(() => {
                    // After temp data is loaded, fetch live data in the background
                    setTimeout(() => {
                        const selectedCity = document.getElementById('cityFilter').value;
                        loadParkingData(selectedCity, true);
                    }, 500); // Small delay for better UX
                });

                // --- ADDED: Map click handler to set user location ---
                map.on('click', function(e) {
                    const { lat, lng } = e.latlng;

                    // Remove old marker
                    if (userLocationMarker) {
                        userLocationMarker.remove();
                    }

                    // Add new marker
                    const userIcon = L.icon({ iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png', iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png', shadowSize: [41, 41] });
                    userLocationMarker = L.marker([lat, lng], { icon: userIcon }).addTo(map);
                    userLocationMarker.bindPopup('<b>Your Start Location</b>').openPopup();
                });

            } catch (error) {
                console.error("Error initializing map:", error);
                document.getElementById('map').innerHTML = "Error loading map. Please try again.";
            }
        }

        function loadLiveData() {
            const selectedCity = document.getElementById('cityFilter').value;
            loadParkingData(selectedCity, true);
        }

        // --- Data Fetching (Modified for Live/Temp) ---
        async function loadParkingData(city, isLiveData = false) {
            const liveLoader = document.getElementById('liveLoader');
            if (isLiveData) {
                liveLoader.style.display = 'flex';
            }
            showLoader(true);
            
            try {
                // Only recenter the map if it's a live data load
                if (isLiveData) {
                    if (city === 'melbourne') {
                        map.setView([-37.8136, 144.9631], 13);
                    } else if (city === 'brisbane') {
                        map.setView([-27.4698, 153.0251], 13);
                    }
                }
                
                // Fetch data from our backend
                const response = await fetch(`${API_BASE_URL}/api/parking-data/${city}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                
                parkingData = data;

                // If loading live data, clear the temporary markers first
                if (isLiveData) {
                    clearAllMarkers();
                }
                updateMapMarkers(data);
                updateSpotList(data);
                updateStats(data);
                if (isLiveData) {
                    liveLoader.style.display = 'none';
                }
                
            } catch (error) {
                console.error('Failed to load parking data:', error);
                document.getElementById('spotList').innerHTML = `<p style="color:var(--danger-color)">Error loading spots for ${city}. Please try again later.</p>`;
            } finally {
                showLoader(false);
            }
        }
        
        // --- UI Updates ---
        
        function clearAllMarkers() {
            markers.forEach(marker => marker.remove());
            markers = [];
            if (selectedMarker) selectedMarker = null;
        }

        function updateMapMarkers(data) {
            // Clear existing markers
            markers.forEach(marker => marker.remove());
            markers = [];

            const availableIcon = L.icon({
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                shadowSize: [41, 41]
            });

            const occupiedIcon = L.icon({
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                shadowSize: [41, 41]
            });

            data.forEach(spot => {
                const icon = spot.occupied ? occupiedIcon : availableIcon;
                const marker = L.marker([spot.lat, spot.lng], { icon: icon });
                
                marker.bindPopup(createPopupContent(spot));
                marker.spotData = spot; // Attach data to marker
                
                marker.on('click', () => {
                    handleMarkerClick(marker, spot);
                });

                marker.addTo(map);
                markers.push(marker);
            });
        }
        
        function createPopupContent(spot) {
            const status = spot.occupied ? 'Occupied' : 'Available';
            const price = spot.current_fee ? `$${spot.current_fee.toFixed(2)}/hr` : 'N/A';
            return `
                <b>Spot ID: ${spot.name}</b><br>
                Street: ${spot.street}<br>
                Status: ${status}<br>
                Price: ${price} (${spot.fee_type || '...'})<br>
                <button class="btn btn-primary" style="font-size: 0.8em; padding: 5px 10px; margin-top: 5px;" onclick="getDirectionsToSpot(${spot.lat}, ${spot.lng})">Get Directions</button>
            `;
        }

        function updateSpotList(data) {
            const listEl = document.getElementById('spotList');
            listEl.innerHTML = ''; // Clear list

            const availableSpots = data.filter(s => !s.occupied);

            if (availableSpots.length === 0) {
                listEl.innerHTML = '<p>No available spots found.</p>';
                return;
            }

            availableSpots.forEach(spot => {
                const card = document.createElement('div');
                card.className = 'spot-card';
                card.id = `spot-card-${spot.name}`;
                card.onclick = () => handleSpotCardClick(spot);
                
                const price = spot.current_fee ? `$${spot.current_fee.toFixed(2)}` : 'N/A';
                const feeType = spot.fee_type ? spot.fee_type : '';
                
                card.innerHTML = `
                    <div class="spot-header">
                        <span class="spot-id">Spot: ${spot.name}</span>
                        <span class="status-badge status-available">Available</span>
                    </div>
                    <div class="spot-details">
                        <p><i class="fas fa-map-marker-alt"></i> ${spot.street}</p>
                        <p><i class="fas fa-info-circle"></i> ${spot.status_note || 'On-street'}</p>
                    </div>
                    <div class="price-info">
                        <span class="price">${price}</span>
                        <span class="fee-type">${feeType}</span>
                    </div>
                `;
                listEl.appendChild(card);
            });
        }
        
        function updateStats(data) {
            const available = data.filter(s => !s.occupied).length;
            const occupied = data.length - available;
            
            document.getElementById('statsAvailable').textContent = available;
            document.getElementById('statsOccupied').textContent = occupied;
        }

        function showLoader(isLoading) {
            document.getElementById('mapLoader').classList.toggle('active', isLoading);
        }
        
        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            const toggleBtn = document.getElementById('sidebarToggle');
            const icon = toggleBtn.querySelector('i');
            
            sidebar.classList.toggle('collapsed');
            
            if (sidebar.classList.contains('collapsed')) {
                icon.className = 'fas fa-chevron-right';
            } else {
                icon.className = 'fas fa-chevron-left';
            }
            
            // Invalidate map size to fix rendering issues
            setTimeout(() => {
                map.invalidateSize();
            }, 300); // Match CSS transition time
        }
        
        // --- User Interaction ---

        function handleSpotCardClick(spot) {
            // Find corresponding marker
            const marker = markers.find(m => m.spotData.name === spot.name);
            
            if (marker) {
                map.setView([spot.lat, spot.lng], 17);
                marker.openPopup();
                handleMarkerClick(marker, spot);
            }
            
            // Highlight card
            document.querySelectorAll('.spot-card').forEach(c => c.classList.remove('selected'));
            document.getElementById(`spot-card-${spot.name}`).classList.add('selected');
        }
        
        function handleMarkerClick(marker, spot) {
            if (selectedMarker) {
                // Reset old marker
                const oldSpot = selectedMarker.spotData;
                const oldIcon = oldSpot.occupied ? marker.options.icon : marker.options.icon; // This is a bit wrong, let's redefine
                
                const availableIcon = L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
                    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png', shadowSize: [41, 41]
                });
                const occupiedIcon = L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png', shadowSize: [41, 41]
                });
                
                selectedMarker.setIcon(selectedMarker.spotData.occupied ? occupiedIcon : availableIcon);
            }
            
            // Set new marker
            const selectedIcon = L.icon({
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
                iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png', shadowSize: [41, 41]
            });
            
            marker.setIcon(selectedIcon);
            selectedMarker = marker;

            // Highlight card
            document.querySelectorAll('.spot-card').forEach(c => c.classList.remove('selected'));
            const card = document.getElementById(`spot-card-${spot.name}`);
            if (card) {
                card.classList.add('selected');
                card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
        
        async function searchLocation() {
            const query = document.getElementById('searchInput').value;
            if (query.length < 3) return;
            
            showLoader(true);
            try {
                // Use Nominatim for geocoding
                const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
                const data = await response.json();
                
                if (data && data.length > 0) {
                    const { lat, lon } = data[0];
                    map.setView([lat, lon], 16);

                    // --- ADDED: Create/Move Destination Marker (FIX 2) ---
                    const destIcon = L.icon({
                        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png', // Red for destination
                        iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
                        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png', shadowSize: [41, 41]
                    });

                    if (destinationMarker) {
                        destinationMarker.setLatLng([lat, lon]);
                    } else {
                        destinationMarker = L.marker([lat, lon], { icon: destIcon }).addTo(map);
                    }
                    destinationMarker.bindPopup(`<b>Destination:</b><br>${data[0].display_name}`).openPopup();
                    // --- END OF ADDED CODE ---

                } else {
                    alert('Location not found.');
                }
            } catch (error) {
                console.error("Geocoding error:", error);
                alert('Error searching for location.');
            } finally {
                showLoader(false);
            }
        }
        
        async function getDirectionsToSpot(lat, lng) {
            if (!("geolocation" in navigator)) {
                alert("Geolocation is not available in your browser.");
                return;
            }
            showLoader(true);

            navigator.geolocation.getCurrentPosition(async (position) => {
                const startLat = position.coords.latitude;
                const startLng = position.coords.longitude;

                // --- ADDED: Create/Move Current Location Marker (FIX 3) ---
                const userIcon = L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
                    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
                    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png', shadowSize: [41, 41]
                });
                
                if (userLocationMarker) {
                    userLocationMarker.setLatLng([startLat, startLng]);
                } else {
                    userLocationMarker = L.marker([startLat, startLng], { icon: userIcon }).addTo(map);
                }
                userLocationMarker.bindPopup('<b>Your Start Location</b>').openPopup();
                // --- END OF ADDED CODE ---

                // --- ADDED: Create/Move Destination Marker for the Spot (FIX 4) ---
                const destIcon = L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
                    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
                    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png', shadowSize: [41, 41]
                });
                
                if (destinationMarker) {
                    destinationMarker.setLatLng([lat, lng]);
                } else {
                    destinationMarker = L.marker([lat, lng], { icon: destIcon }).addTo(map);
                }
                destinationMarker.bindPopup('<b>Your Destination</b>').openPopup();
                // --- END OF ADDED CODE ---

                try {
                    const response = await fetch(`${API_BASE_URL}/api/route?start_lat=${startLat}&start_lon=${startLng}&end_lat=${lat}&end_lon=${lng}`);
                    if (!response.ok) throw new Error('Failed to fetch route');
                    const routeData = await response.json();
                    
                    if (currentRoute) {
                        currentRoute.remove(); // Remove old route
                    }

                    // --- NOTE: This line requires your backend to send a valid array of [lat, lng] coordinates ---
                    currentRoute = L.polyline(routeData.geometry, { color: '#FF5733', weight: 6 }).addTo(map);
                    map.fitBounds(currentRoute.getBounds());
                    
                } catch (error) {
                    console.error("Routing error:", error);
                    alert("Could not calculate directions.");
                } finally {
                    showLoader(false);
                }
            }, (error) => {
                console.error("Geolocation error:", error);
                alert("Could not get your current location.");
                showLoader(false);
            });
        }

        // --- Modal ---
        function closeModal() {
            const modal = document.getElementById('modalOverlay');
            modal.classList.remove('active');
        }
        
        function showModal(type) {
            const modal = document.getElementById('modalOverlay');
            const title = document.getElementById('modalTitle');
            const body = document.getElementById('modalBody');

            switch(type) {
                case 'login':
                    title.innerText = 'Login';
                    body.innerHTML = `
                        <div id="login-error" style="color: var(--danger-color); margin-bottom: 15px; display: none;"></div>
                        <form onsubmit="handleLogin(event)">
                            <div class="filter-group">
                                <label for="login-username">Username</label>
                                <input type="text" id="login-username" class="search-input" required>
                            </div>
                            <div class="filter-group">
                                <label for="login-password">Password</label>
                                <input type="password" id="login-password" class="search-input" required>
                            </div>
                            <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 10px;">Login</button>
                        </form>
                        <p style="text-align: center; margin-top: 15px; font-size: 0.9em;">
                            Don't have an account? <a href="#" onclick="showModal('register')" style="color: var(--primary-color); font-weight: 600;">Sign Up</a>
                        </p>
                    `;
                    break;
                case 'register':
                    title.innerText = 'Sign Up';
                    body.innerHTML = `
                        <div id="register-error" style="color: var(--danger-color); margin-bottom: 15px; display: none;"></div>
                        <div id="register-success" style="color: var(--success-color); margin-bottom: 15px; display: none;"></div>
                        <form onsubmit="handleRegister(event)">
                            <div class="filter-group">
                                <label for="register-username">Username</label>
                                <input type="text" id="register-username" class="search-input" required>
                            </div>
                            <div class="filter-group">
                                <label for="register-email">Email</label>
                                <input type="email" id="register-email" class="search-input" required>
                            </div>
                            <div class="filter-group">
                                <label for="register-password">Password</label>
                                <input type="password" id="register-password" class="search-input" required>
                            </div>
                            <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 10px;">Create Account</button>
                        </form>
                        <p style="text-align: center; margin-top: 15px; font-size: 0.9em;">
                            Already have an account? <a href="#" onclick="showModal('login')" style="color: var(--primary-color); font-weight: 600;">Login</a>
                        </p>
                    `;
                    break;
                case 'profile':
                    if (!authToken) {
                        showModal('login');
                        return;
                    }
                    title.innerText = 'My Profile';
                    body.innerHTML = `<div id="profile-loading" class="spinner"></div>`;
                    fetchProfile();
                    break;
            }
            modal.classList.add('active');
        }

        // --- Auth Functions ---
        let authToken = null;

        async function handleLogin(event) {
            event.preventDefault();
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;
            const errorDiv = document.getElementById('login-error');
            
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            try {
                const response = await fetch(`${API_BASE_URL}/token`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData,
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Login failed');
                }
                const data = await response.json();
                setAuthToken(data.access_token);
                closeModal();
                updateUIForLogin();
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.style.display = 'block';
            }
        }

        async function handleRegister(event) {
            event.preventDefault();
            const username = document.getElementById('register-username').value;
            const email = document.getElementById('register-email').value;
            const password = document.getElementById('register-password').value;
            const errorDiv = document.getElementById('register-error');
            const successDiv = document.getElementById('register-success');
            
            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';

            try {
                const response = await fetch(`${API_BASE_URL}/api/users/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, email, password }),
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Registration failed');
                }
                successDiv.textContent = 'Registration successful! You can now log in.';
                successDiv.style.display = 'block';
                setTimeout(() => showModal('login'), 2000);
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.style.display = 'block';
            }
        }

        function handleLogout() {
            setAuthToken(null);
            updateUIForLogout();
        }

        function setAuthToken(token) {
            if (token) {
                localStorage.setItem('parkroo_token', token);
                authToken = token;
            } else {
                localStorage.removeItem('parkroo_token');
                authToken = null;
            }
        }

        function updateUIForLogin() {
            const authButton = document.getElementById('authButton');
            authButton.textContent = 'Logout';
            authButton.onclick = handleLogout;
        }

        function updateUIForLogout() {
            const authButton = document.getElementById('authButton');
            authButton.textContent = 'Login / Sign Up';
            authButton.onclick = () => showModal('login');
        }

        async function fetchProfile() {
            const body = document.getElementById('modalBody');
            try {
                const response = await fetch(`${API_BASE_URL}/api/users/me`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                if (!response.ok) throw new Error('Could not fetch profile.');
                const user = await response.json();
                
                body.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 20px;">
                        <i class="fas fa-user-circle" style="font-size: 60px; color: var(--primary-color);"></i>
                        <div>
                            <h3 style="margin: 0; color: var(--text-primary);">${user.name || user.username}</h3>
                            <p style="color: var(--text-secondary); margin: 0;">${user.email || 'No email provided'}</p>
                        </div>
                    </div>
                    <hr style="margin: 20px 0; border: none; border-top: 1px solid var(--border-color);">
                    <p>More profile features coming soon!</p>
                    <button class="btn btn-secondary" onclick="closeModal()" style="width: 100%; margin-top: 20px;">Close</button>
                `;
            } catch (error) {
                body.innerHTML = `<p style="color: var(--danger-color);">${error.message}</p>`;
            }
        }

        // --- Lifecycle ---
        
        // Add CSS animations
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);

        // Initialize on page load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                initMap();
                const token = localStorage.getItem('parkroo_token');
                if (token) {
                    setAuthToken(token);
                    updateUIForLogin();
                }
            });
        } else {
            initMap();
            const token = localStorage.getItem('parkroo_token');
            if (token) {
                setAuthToken(token);
                updateUIForLogin();
            }
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# --- 1. BACKEND (FastAPI) CODE ---
# ==============================================================================

# --- Basic Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# --- In-Memory Cache for Parking Data ---
parking_data_cache = {}
cache_status: Dict[str, str] = {} # To track loading status (e.g., "loading", "ready")
bay_to_kerbside_map: Dict[int, int] = {} # To map bayid to kerbsideid
CACHE_DURATION = timedelta(minutes=10)

# --- Robust File Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.path.join(BASE_DIR, "parking.db")
JSON_PATH = os.path.join(BASE_DIR, "on-street-parking-bay-sensors.json")
# HTML_PATH = os.path.join(BASE_DIR, "parking2.html") # No longer needed
EXCEL_PATH = os.path.join(BASE_DIR, "melbourne_parking_bay_sensors.csv")
FEES_CSV_PATH = os.path.join(BASE_DIR, "on-street-with-fees.csv")

# --- Lifespan Manager for Startup Actions ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backend server starting up...")
    
    # --- Database Initialization ---
    db = sqlite3.connect(DATABASE_URL)
    cursor = db.cursor()
    
    # Create users table with a 'role' column
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        name TEXT,
        phone TEXT,
        hashed_password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        stripe_customer_id TEXT
    )
    """)

    # Create bookings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        spot_id TEXT,
        booking_time TEXT,
        amount INTEGER,
        status TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Create activity_log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    # Create vehicles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        nickname TEXT NOT NULL,
        make TEXT,
        model TEXT,
        license_plate TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    # Create favorite_spots table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favorite_spots (
        user_id INTEGER NOT NULL,
        spot_id TEXT NOT NULL,
        nickname TEXT,
        added_on TEXT NOT NULL,
        PRIMARY KEY (user_id, spot_id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)

    # Drop and recreate the fees table on startup to ensure schema is always fresh
    cursor.execute("DROP TABLE IF EXISTS parking_fees")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parking_fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT NOT NULL,
        kerbside_id INTEGER UNIQUE NOT NULL,
        area_type TEXT,
        weekday_peak REAL,
        weekday_offpeak REAL,
        weekend_rate REAL,
        notes TEXT,
        rate_type TEXT
    )
    """)

    # --- Simple Migration: Add 'role' column to users if it doesn't exist ---
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'role' not in columns:
        logger.info("Adding 'role' column to 'users' table...")
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if 'stripe_customer_id' not in columns:
        logger.info("Adding 'stripe_customer_id' column to 'users' table...")
        cursor.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    
    db.commit()
    db.close()
    
    logger.info("Database tables verified/created successfully.")

    # --- Start Background Tasks ---
    # Start the data loading in a separate thread to not block startup
    logger.info("Starting background thread to load parking data...")
    threading.Thread(target=load_and_cache_data, args=("melbourne",), daemon=True).start()
    threading.Thread(target=load_and_cache_data, args=("brisbane",), daemon=True).start()

    yield # This is where the application runs

    # --- Shutdown Actions ---
    logger.info("Backend server shutting down...")
    # Clean up resources if needed
    parking_data_cache.clear()

# --- Initialize FastAPI App ---
backend_app = FastAPI(lifespan=lifespan)

# --- CORS Configuration ---
backend_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins. For production, restrict this.
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# --- Database Dependency ---
def get_db():
    db = sqlite3.connect(DATABASE_URL)
    db.row_factory = sqlite3.Row  # This allows accessing columns by name
    try:
        yield db
    finally:
        db.close()

# ==============================================================================
# --- 2. BACKEND API ENDPOINTS ---
# ==============================================================================

# --- Models ---
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    name: Optional[str] = None
    phone: Optional[str] = None
    stripe_customer_id: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class Booking(BaseModel):
    spot_id: str
    booking_time: str
    amount: int
    status: str

class Vehicle(BaseModel):
    nickname: str
    make: Optional[str] = None
    model: Optional[str] = None
    license_plate: str

class FavoriteSpot(BaseModel):
    spot_id: str
    nickname: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None

# --- Security & Auth ---
SECRET_KEY = os.environ.get("SECRET_KEY", "your_fallback_secret_key_1234567890")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: sqlite3.Connection = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (token_data.username,))
    user = cursor.fetchone()
    
    if user is None:
        raise credentials_exception
    return dict(user) # Return as a dictionary

async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return current_user

def log_activity(db: sqlite3.Connection, user_id: int, action: str, details: Optional[str] = None):
    try:
        db.execute(
            "INSERT INTO activity_log (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, datetime.now())
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log activity for user {user_id}: {e}")

# --- Auth Endpoints ---

@backend_app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (form_data.username,))
    user = cursor.fetchone()
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    log_activity(db, user["id"], "login", "User logged in successfully.")
    
    return {"access_token": access_token, "token_type": "bearer"}

@backend_app.post("/api/auth/google")
async def auth_google(token: Dict[str, str], db: sqlite3.Connection = Depends(get_db)):
    try:
        token_str = token.get("token")
        if not token_str:
            raise HTTPException(status_code=400, detail="No token provided")
        if not GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=500, detail="Google Auth is not configured on server")

        idinfo = id_token.verify_oauth2_token(token_str, google_requests.Request(), GOOGLE_CLIENT_ID)
        
        email = idinfo['email']
        name = idinfo.get('name', 'Google User')
        
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            # Create a new user
            # Use email as username for simplicity, or generate a unique one
            username = email
            # Generate a secure random password as it's required, but user will use Google to log in
            temp_password = os.urandom(16).hex()
            hashed_password = get_password_hash(temp_password)
            
            try:
                cursor.execute(
                    "INSERT INTO users (username, email, name, hashed_password) VALUES (?, ?, ?, ?)",
                    (username, email, name, hashed_password)
                )
                db.commit()
                user_id = cursor.lastrowid
                log_activity(db, user_id, "register", "New user registered via Google.")
                
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                user = cursor.fetchone()
            
            except sqlite3.IntegrityError:
                # Fallback if username (email) is somehow already taken but email wasn't found
                raise HTTPException(status_code=409, detail="User already exists, but login failed.")
        
        # User exists, create a token for them
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"]}, expires_delta=access_token_expires
        )
        
        log_activity(db, user["id"], "login", "User logged in via Google.")
        
        return {"access_token": access_token, "token_type": "bearer"}

    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    except Exception as e:
        logger.error(f"Google auth error: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

# --- User Management Endpoints ---

@backend_app.post("/api/users/register", response_model=UserResponse)
async def register_user(user: UserCreate, db: sqlite3.Connection = Depends(get_db)):
    hashed_password = get_password_hash(user.password)
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            (user.username, user.email, hashed_password)
        )
        db.commit()
        user_id = cursor.lastrowid
        
        # Log this activity
        log_activity(db, user_id, "register", "New user created.")

        # Fetch the created user to return
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        new_user = cursor.fetchone()
        
        return dict(new_user)
        
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already registered")

@backend_app.get("/api/users/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    # current_user is already a dict from get_current_user
    return UserResponse(**current_user)

@backend_app.put("/api/users/me", response_model=UserResponse)
async def update_user_me(user_update: UserUpdate, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    
    # Build query dynamically based on provided fields
    updates = []
    params = []
    
    if user_update.email:
        updates.append("email = ?")
        params.append(user_update.email)
    if user_update.name:
        updates.append("name = ?")
        params.append(user_update.name)
    if user_update.phone:
        updates.append("phone = ?")
        params.append(user_update.phone)
        
    if not updates:
        raise HTTPException(status_code=400, detail="No update information provided")

    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    params.append(user_id)
    
    try:
        db.execute(query, tuple(params))
        db.commit()
        
        log_activity(db, user_id, "profile_update", f"Updated fields: {', '.join(updates)}")

        # Fetch and return updated user
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        updated_user = cursor.fetchone()
        return UserResponse(**updated_user)
        
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Update failed. Possible duplicate data: {e}")


# --- Admin Endpoint ---
@backend_app.get("/api/admin/users", response_model=List[UserResponse])
async def get_all_users(skip: int = 0, limit: int = 20, db: sqlite3.Connection = Depends(get_db), admin_user: dict = Depends(get_current_admin_user)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users LIMIT ? OFFSET ?", (limit, skip))
    users = cursor.fetchall()
    return [UserResponse(**user) for user in users]

@backend_app.get("/api/admin/logs", response_model=List[dict])
async def get_activity_logs(skip: int = 0, limit: int = 50, db: sqlite3.Connection = Depends(get_db), admin_user: dict = Depends(get_current_admin_user)):
    cursor = db.cursor()
    cursor.execute("""
        SELECT a.id, a.action, a.details, a.timestamp, u.username 
        FROM activity_log a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC
        LIMIT ? OFFSET ?
    """, (limit, skip))
    logs = cursor.fetchall()
    return [dict(log) for log in logs]


# --- Parking Data Logic & Endpoints ---

def get_current_fee(kerbside_id: int, db: sqlite3.Connection) -> Tuple[Optional[float], str]:
    """
    Calculates the current fee based on the kerbside_id and current time.
    """
    try:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM parking_fees WHERE kerbside_id = ?", (kerbside_id,))
        fee_rule = cursor.fetchone()
        
        if not fee_rule:
            return None, "No fee info"
            
        fee_rule = dict(fee_rule) # Convert from sqlite3.Row

        # Get current time in Melbourne
        now = datetime.now(ZoneInfo("Australia/Melbourne"))
        weekday = now.weekday() # Monday is 0, Sunday is 6
        hour = now.hour

        if weekday < 5: # Weekday (0-4)
            if 7 <= hour < 19: # Peak (7am - 7pm)
                return fee_rule.get('weekday_peak'), fee_rule.get('rate_type', 'Hourly')
            else: # Off-peak
                return fee_rule.get('weekday_offpeak'), fee_rule.get('rate_type', 'Hourly')
        else: # Weekend (5-6)
            return fee_rule.get('weekend_rate'), fee_rule.get('rate_type', 'Hourly')
            
    except Exception as e:
        logger.error(f"Error getting fee for kerbside_id {kerbside_id}: {e}")
        return None, "Error"

def load_parking_fees_to_db(db: sqlite3.Connection, city: str):
    """
    Loads parking fee data from a CSV file into the database.
    """
    try:
        if not os.path.exists(FEES_CSV_PATH):
            logger.warning(f"Fees CSV file not found at {FEES_CSV_PATH}. Skipping fee loading.")
            return

        fees_df = pandas.read_csv(FEES_CSV_PATH)
        
        # Basic validation
        required_cols = ['Kerbside_Id', 'Area_Type', 'Weekday_Peak', 'Weekday_Offpeak', 'Weekend_Rate', 'Rate_Type']
        if not all(col in fees_df.columns for col in required_cols):
            logger.error(f"Fees CSV is missing one of the required columns: {required_cols}")
            return
            
        logger.info(f"Loading {len(fees_df)} fee rules into database...")
        
        cursor = db.cursor()
        for _, row in fees_df.iterrows():
            try:
                cursor.execute(
                    """
                    INSERT INTO parking_fees (city, kerbside_id, area_type, weekday_peak, weekday_offpeak, weekend_rate, notes, rate_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(kerbside_id) DO UPDATE SET
                        area_type=excluded.area_type,
                        weekday_peak=excluded.weekday_peak,
                        weekday_offpeak=excluded.weekday_offpeak,
                        weekend_rate=excluded.weekend_rate,
                        notes=excluded.notes,
                        rate_type=excluded.rate_type
                    """,
                    (
                        city,
                        int(row['Kerbside_Id']),
                        row.get('Area_Type'),
                        float(row['Weekday_Peak']) if pandas.notna(row['Weekday_Peak']) else None,
                        float(row['Weekday_Offpeak']) if pandas.notna(row['Weekday_Offpeak']) else None,
                        float(row['Weekend_Rate']) if pandas.notna(row['Weekend_Rate']) else None,
                        row.get('Notes'),
                        row.get('Rate_Type')
                    )
                )
            except Exception as e:
                logger.error(f"Failed to insert fee row {row.get('Kerbside_Id')}: {e}")
                
        db.commit()
        logger.info(f"Successfully loaded/updated {len(fees_df)} fee rules.")
        
    except Exception as e:
        logger.error(f"Failed to load parking fees CSV: {e}")

def load_and_cache_data(city: str):
    global parking_data_cache, cache_status, bay_to_kerbside_map
    
    if cache_status.get(city) == "loading":
        logger.info(f"Data loading for {city} is already in progress.")
        return
        
    cache_status[city] = "loading"
    logger.info(f"Starting data load for city: {city}...")
    
    db_conn = None
    try:
        # --- Step 1: Connect to DB and load fees ---
        db_conn = sqlite3.connect(DATABASE_URL)
        load_parking_fees_to_db(db_conn, city)

        # --- Step 2: Load Bay-to-Kerbside Mapping (from JSON) ---
        if not bay_to_kerbside_map: # Only load if empty
            if not os.path.exists(JSON_PATH):
                logger.error(f"CRITICAL: JSON file not found at {JSON_PATH}. Cannot map bays to fees.")
                cache_status[city] = "error"
                return

            logger.info("Loading Bay-to-Kerbside mapping from JSON...")
            with open(JSON_PATH, 'r') as f:
                json_data = json.load(f)
                
            for feature in json_data.get('features', []):
                props = feature.get('properties', {})
                bay_id = props.get('bay_id')
                kerbside_id = props.get('kerbside_id')
                if bay_id and kerbside_id:
                    bay_to_kerbside_map[int(bay_id)] = int(kerbside_id)
            logger.info(f"Loaded {len(bay_to_kerbside_map)} bay-to-kerbside mappings.")

        # --- Step 3: Fetch Live Sensor Data (Socrata API) ---
        # This is the Socrata endpoint for Melbourne's live sensor data
        # Note: Brisbane would have a different endpoint
        if city == "melbourne":
            socrata_url = "https://data.melbourne.vic.gov.au/api/views/vh2v-4nfs/rows.json?accessType=DOWNLOAD"
            response = requests.get(socrata_url, timeout=15)
            response.raise_for_status() # Raise an exception for bad status codes
            live_data = response.json()
            
            # --- Step 4: Process Live Data ---
            processed_data = []
            columns = [col['fieldName'] for col in live_data['meta']['view']['columns']]
            
            # Find indices of required columns
            try:
                bay_id_idx = columns.index('bay_id')
                lat_idx = columns.index('lat')
                lon_idx = columns.index('lon')
                status_idx = columns.index('status')
                # Optional fields
                try: desc1_idx = columns.index('desc1') 
                except ValueError: desc1_idx = -1
                try: desc2_idx = columns.index('desc2') 
                except ValueError: desc2_idx = -1

            except ValueError as e:
                logger.error(f"Live data feed for {city} is missing a required column: {e}")
                cache_status[city] = "error"
                if db_conn: db_conn.close()
                return

            for item in live_data['data']:
                try:
                    bay_id = int(item[bay_id_idx])
                    kerbside_id = bay_to_kerbside_map.get(bay_id)
                    
                    current_fee, fee_type = None, "N/A"
                    if kerbside_id:
                        current_fee, fee_type = get_current_fee(kerbside_id, db_conn)
                    
                    processed_data.append({
                        "name": str(bay_id), # Use bay_id as the 'name'
                        "lat": float(item[lat_idx]),
                        "lng": float(item[lon_idx]),
                        "occupied": item[status_idx] != 'Unoccupied',
                        "status_note": item[status_idx],
                        "street": item[desc1_idx] if desc1_idx != -1 else "N/A",
                        "extra_info": item[desc2_idx] if desc2_idx != -1 else "",
                        "bay_id": bay_id,
                        "kerbside_id": kerbside_id,
                        "current_fee": current_fee,
                        "fee_type": fee_type
                    })
                except Exception as e:
                    logger.warning(f"Failed to process live data row: {item}. Error: {e}")
            
            # --- Step 5: Cache the processed data ---
            parking_data_cache[city] = {
                "data": processed_data,
                "last_updated": datetime.now()
            }
            cache_status[city] = "ready"
            logger.info(f"Successfully loaded and cached {len(processed_data)} parking spots for {city}.")

        elif city == "brisbane":
            # --- BRISBANE DATA LOADING (Placeholder) ---
            # TODO: Find Brisbane's live data API and implement processing
            logger.warning("Brisbane data loading is not yet implemented. Using placeholder data.")
            
            # Example placeholder data
            brisbane_placeholder_data = [
                {"name": "B001", "lat": -27.4698, "lng": 153.0251, "occupied": False, "status_note": "Unoccupied", "street": "Queen St", "extra_info": "", "bay_id": 10001, "kerbside_id": 20001, "current_fee": 3.50, "fee_type": "Hourly"},
                {"name": "B002", "lat": -27.4705, "lng": 153.0255, "occupied": True, "status_note": "Occupied", "street": "Adelaide St", "extra_info": "", "bay_id": 10002, "kerbside_id": 20002, "current_fee": 3.50, "fee_type": "Hourly"},
                {"name": "B003", "lat": -27.4690, "lng": 153.0260, "occupied": False, "status_note": "Unoccupied", "street": "George St", "extra_info": "", "bay_id": 10003, "kerbside_id": 20001, "current_fee": 3.50, "fee_type": "Hourly"},
            ]
            
            parking_data_cache[city] = {
                "data": brisbane_placeholder_data,
                "last_updated": datetime.now()
            }
            cache_status[city] = "ready" # Mark as ready even with placeholders
            logger.info(f"Loaded {len(brisbane_placeholder_data)} placeholder spots for {city}.")
            
        else:
            logger.error(f"Unknown city requested: {city}")
            cache_status[city] = "error"

    except requests.RequestException as e:
        logger.error(f"Failed to fetch live data for {city} from API: {e}")
        cache_status[city] = "error"
    except Exception as e:
        logger.error(f"An unexpected error occurred during data loading for {city}: {e}")
        cache_status[city] = "error"
    finally:
        if db_conn:
            db_conn.close()

def get_cached_data(city: str) -> List[Dict[str, Any]]:
    """
    Retrieves parking data from cache, refreshing if it's stale or missing.
    """
    global parking_data_cache, cache_status
    
    cache_entry = parking_data_cache.get(city)
    
    if cache_entry:
        is_stale = (datetime.now() - cache_entry["last_updated"]) > CACHE_DURATION
        if is_stale and cache_status.get(city) != "loading":
            logger.info(f"Cache for {city} is stale. Triggering background refresh...")
            threading.Thread(target=load_and_cache_data, args=(city,), daemon=True).start()
        
        logger.info(f"Serving {len(cache_entry['data'])} spots for {city} from cache.")
        return cache_entry["data"]
        
    else: # No cache entry
        status = cache_status.get(city)
        if status == "loading":
            logger.warning(f"Data for {city} is still loading. Returning empty list for now.")
            return [] # Return empty while loading
        
        # If no cache and not loading (e.g., initial start or error), trigger a load
        logger.info(f"No cache found for {city}. Triggering synchronous load...")
        load_and_cache_data(city) # This will block, which is ok for the first load
        
        # Retry getting the cache
        cache_entry = parking_data_cache.get(city)
        if cache_entry:
            return cache_entry["data"]
        else:
            logger.error(f"Failed to load data for {city} even after synchronous call.")
            return [] # Return empty on failure


# --- Main Data Endpoint ---
@backend_app.get("/api/parking-data/{city}")
async def get_parking_data(city: str = "melbourne"):
    """
    The main API endpoint to get all parking data.
    It uses the caching logic.
    """
    if city not in ["melbourne", "brisbane"]:
        raise HTTPException(status_code=404, detail="City not supported. Try 'melbourne' or 'brisbane'.")
        
    try:
        data = get_cached_data(city)
        if not data and cache_status.get(city) != "loading":
            # This handles the case where the load failed
            raise HTTPException(status_code=503, detail=f"Parking data for {city} is currently unavailable. Please try again later.")
        
        return data
    except Exception as e:
        logger.error(f"Error in /api/parking-data/{city} endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching parking data.")

# --- Routing Endpoint ---
@backend_app.get("/api/route")
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    """
    Gets a route from OSRM.
    """
    try:
        # OSRM demo server. Replace with your own OSRM instance for production.
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
        
        # Request geometry as a polyline (default)
        response = requests.get(osrm_url, params={"overview": "full", "geometries": "polyline"})
        response.raise_for_status()
        
        route_data = response.json()
        
        if route_data.get('code') != 'Ok' or not route_data.get('routes'):
            raise HTTPException(status_code=404, detail="Route not found.")
            
        # --- IMPORTANT ---
        # The 'geometry' from OSRM is an ENCODED polyline string (e.g., "_p~iF~ps|U...").
        # Leaflet's L.polyline *cannot* read this directly.
        #
        # OPTION 1: (Backend fix) Decode it here.
        # You would need a library like `polyline` (pip install polyline)
        # import polyline
        # encoded_geometry = route_data['routes'][0]['geometry']
        # decoded_geometry = polyline.decode(encoded_geometry) # This gives [[lat, lon], ...]
        
        # OPTION 2: (Frontend fix) Send the encoded string and use a Leaflet plugin.
        # e.g., Leaflet.Polyline.Encoded
        
        # OPTION 3: (Easiest for this setup) Request GeoJSON from OSRM
        # This is the best fix. Change the 'geometries' param.
        
        # Let's try to implement Option 3 by changing the request
        osrm_url_geojson = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
        response_geojson = requests.get(osrm_url_geojson, params={"overview": "full", "geometries": "geojson"})
        response_geojson.raise_for_status()
        route_data_geojson = response_geojson.json()
        
        if route_data_geojson.get('code') != 'Ok' or not route_data_geojson.get('routes'):
            raise HTTPException(status_code=404, detail="Route not found (GeoJSON).")
        
        # The geometry is now in GeoJSON format: { "type": "LineString", "coordinates": [[lon, lat], ...] }
        # Leaflet's L.polyline expects [[lat, lon], ...]
        # We must swap the coordinates.
        
        geojson_coords = route_data_geojson['routes'][0]['geometry']['coordinates']
        leaflet_coords = [[lat, lon] for lon, lat in geojson_coords] # Swap lon/lat
        
        return {
            "geometry": leaflet_coords, # Send the corrected [lat, lon] array
            "duration": route_data_geojson['routes'][0]['duration'], # in seconds
            "distance": route_data_geojson['routes'][0]['distance'] # in meters
        }

    except requests.RequestException as e:
        logger.error(f"OSRM routing request failed: {e}")
        raise HTTPException(status_code=503, detail="Routing service is unavailable.")
    except Exception as e:
        logger.error(f"Error processing route: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate route.")


# --- Payment & Booking Endpoints (Stripe) ---

@backend_app.post("/api/payment/create-setup-intent")
async def create_setup_intent(current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """
    Creates a Stripe SetupIntent to save a new payment method.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=501, detail="Payment system is not configured.")

    customer_id = current_user.get('stripe_customer_id')
    
    try:
        # Create a new Stripe Customer if one doesn't exist
        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.get('email'),
                name=current_user.get('name'),
                metadata={'user_id': current_user['id']}
            )
            customer_id = customer.id
            
            # Save the new customer_id to our database
            db.execute("UPDATE users SET stripe_customer_id = ? WHERE id = ?", (customer_id, current_user['id']))
            db.commit()
            log_activity(db, current_user['id'], "stripe_customer_created", customer_id)

        # Create a SetupIntent
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
            usage="on_session" # Use 'off_session' if you plan to charge them later
        )
        
        return {
            "clientSecret": setup_intent.client_secret,
            "customerId": customer_id
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating setup intent: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize payment setup.")

@backend_app.get("/api/payment/methods")
async def get_payment_methods(current_user: dict = Depends(get_current_user)):
    """
    Lists the user's saved payment methods.
    """
    customer_id = current_user.get('stripe_customer_id')
    if not customer_id:
        return [] # No customer ID, so no saved methods

    try:
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type="card",
        )
        
        # Format for frontend
        formatted_methods = []
        for pm in payment_methods.data:
            formatted_methods.append({
                "id": pm.id,
                "brand": pm.card.brand,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year
            })
            
        return formatted_methods
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error listing payment methods: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# --- Vehicle Management Endpoints ---

@backend_app.post("/api/vehicles", response_model=dict)
async def add_vehicle(vehicle: Vehicle, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO vehicles (user_id, nickname, make, model, license_plate) VALUES (?, ?, ?, ?, ?)",
            (user_id, vehicle.nickname, vehicle.make, vehicle.model, vehicle.license_plate)
        )
        db.commit()
        vehicle_id = cursor.lastrowid
        
        log_activity(db, user_id, "vehicle_add", f"Added vehicle {vehicle.license_plate}")
        
        return {"id": vehicle_id, **vehicle.dict()}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Failed to add vehicle. Check data.")

@backend_app.get("/api/vehicles", response_model=List[dict])
async def get_vehicles(current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    cursor = db.cursor()
    cursor.execute("SELECT * FROM vehicles WHERE user_id = ?", (user_id,))
    vehicles = cursor.fetchall()
    return [dict(v) for v in vehicles]

@backend_app.delete("/api/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: int, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    cursor = db.cursor()
    
    # Verify the vehicle belongs to the user before deleting
    cursor.execute("SELECT * FROM vehicles WHERE id = ? AND user_id = ?", (vehicle_id, user_id))
    vehicle = cursor.fetchone()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found or does not belong to user.")
        
    db.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
    db.commit()
    
    log_activity(db, user_id, "vehicle_remove", f"Removed vehicle {vehicle['license_plate']}")
    
    return {"message": "Vehicle removed successfully."}

# --- Favorite Spots Endpoints ---

@backend_app.get("/api/favorites", response_model=List[dict])
async def get_favorites(current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    cursor = db.cursor()
    cursor.execute("SELECT * FROM favorite_spots WHERE user_id = ?", (user_id,))
    favorites = cursor.fetchall()
    return [dict(fav) for fav in favorites]

@backend_app.post("/api/favorites", response_model=dict)
async def add_favorite(favorite: FavoriteSpot, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    try:
        cursor = db.cursor()
        cursor.execute("INSERT INTO favorite_spots (user_id, spot_id, nickname, added_on) VALUES (?, ?, ?, ?)",
                       (user_id, favorite.spot_id, favorite.nickname, datetime.now()))
        db.commit()
        
        # Fetch the newly added favorite to return it
        cursor.execute("SELECT * FROM favorite_spots WHERE user_id = ? AND spot_id = ?", (user_id, favorite.spot_id))
        new_fav = cursor.fetchone()
        
        return dict(new_fav)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Spot is already in favorites.")

@backend_app.delete("/api/favorites/{spot_id}")
async def delete_favorite(spot_id: str, current_user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    user_id = current_user['id']
    db.execute("DELETE FROM favorite_spots WHERE user_id = ? AND spot_id = ?", (user_id, spot_id))
    db.commit()
    return {"message": "Favorite spot removed successfully."}


# ==============================================================================
# --- 3. APP RUNNER ---
# ==============================================================================

# --- Serve Frontend ---
@backend_app.get("/", response_class=HTMLResponse)
async def read_root():
    """
    Serves the main HTML file.
    """
    return HTML_FRONTEND


if __name__ == "__main__":
    logger.info("Starting FastAPI server with integrated HTML frontend...")
    # This will run the FastAPI app on port 8000
    # Use reload=True for development to auto-reload on code changes
    uvicorn.run(backend_app, host="0.0.0.0", port=8000)