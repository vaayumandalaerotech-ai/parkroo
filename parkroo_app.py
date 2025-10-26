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
                flex-direction: column;
                gap: 10px;
                top: 10px;
                left: 10px;
                padding: 10px;
            }
            .stat-info strong { font-size: 1em; }
            .stats-bar {
                flex-direction: row;
                bottom: 10px;
                left: 10px;
            }
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
        
        let authToken = null;
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
                loadParkingData('temp', false); 

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
        
        async function findRouteToDestination() {
            const destinationQuery = document.getElementById('destinationInput').value;
            if (!destinationQuery) {
                alert("Please enter a destination.");
                return;
            }

            // Hide the initial prompt
            const initialPrompt = document.getElementById('initial-prompt');
            if (initialPrompt) initialPrompt.style.display = 'none';


            showLoader(true);
            try {
                const geoResponse = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(destinationQuery)}`);
                const geoData = await geoResponse.json();

                if (geoData && geoData.length > 0) {
                    const { lat, lon } = geoData[0];
                    
                    // Remove old destination marker if it exists
                    if (destinationMarker) {
                        destinationMarker.remove();
                    }

                    // Add a new marker for the destination
                    const destIcon = L.icon({ iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png', iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png', shadowSize: [41, 41] });
                    destinationMarker = L.marker([lat, lon], { icon: destIcon }).addTo(map);
                    destinationMarker.bindPopup(`<b>Your Destination:</b><br>${geoData[0].display_name}`).openPopup();

                    map.setView([lat, lon], 16);
                    
                } else {
                    alert('Destination not found.');
                }
            } catch (e) { console.error("Error in findRouteToDestination:", e); }
            finally { showLoader(false); }
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
                
                try {
                    const response = await fetch(`${API_BASE_URL}/api/route?start_lat=${startLat}&start_lon=${startLng}&end_lat=${lat}&end_lon=${lng}`);
                    if (!response.ok) throw new Error('Failed to fetch route');
                    
                    const routeData = await response.json();
                    
                    if (currentRoute) {
                        currentRoute.remove(); // Remove old route
                    }

                    currentRoute = L.polyline(routeData.geometry, { color: 'blue' }).addTo(map);
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
        }
        
        // Handle Enter key in search
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('searchInput').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    searchLocation();
                }
            });
            document.getElementById('destinationInput').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    findRouteToDestination();
                }
            });
        });
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
        logger.info("Adding 'role' column to 'users' table.")
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if 'stripe_customer_id' not in columns:
        logger.info("Adding 'stripe_customer_id' column to 'users' table.")
        cursor.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")

    # --- Load parking fee data from the new CSV on startup ---
    try:
        fees_df = pandas.read_csv(FEES_CSV_PATH)
        fees_df.rename(columns={
            'KerbsideID': 'kerbside_id',
            'area_type': 'area_type',
            'weekday_peak_aud_per_hr': 'weekday_peak',
            'weekday_offpeak_aud_per_hr': 'weekday_offpeak',
            'weekend_aud_per_hr': 'weekend_rate',
            'rate_type': 'rate_type'
        }, inplace=True)
        
        for _, row in fees_df.iterrows():
            if pandas.notna(row.get('kerbside_id')):
                cursor.execute("""
                    INSERT OR IGNORE INTO parking_fees (city, kerbside_id, area_type, weekday_peak, weekday_offpeak, weekend_rate, rate_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ("melbourne", int(row['kerbside_id']), row.get('area_type'), row.get('weekday_peak'), row.get('weekday_offpeak'), row.get('weekend_rate'), row.get('rate_type')))
        
        db.commit()
        logger.info(f"Successfully loaded or verified {len(fees_df)} parking fee records from {os.path.basename(FEES_CSV_PATH)}.")
    except FileNotFoundError:
        logger.warning(f"'{os.path.basename(FEES_CSV_PATH)}' not found. No fee data will be loaded.")
    except Exception as e:
        logger.error(f"Failed to load parking fee data from CSV: {e}")

    # --- Load the bayid to kerbsideid mapping on startup ---
    global bay_to_kerbside_map
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            sensor_data = json.load(f)
        for item in sensor_data:
            bay_id = item.get("bayid")
            kerbside_id = item.get("kerbsideid")
            if bay_id and kerbside_id:
                bay_to_kerbside_map[int(bay_id)] = int(kerbside_id)
        logger.info(f"Successfully loaded {len(bay_to_kerbside_map)} bay ID to kerbside ID mappings.")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logger.error(f"Could not load or parse bay ID mapping from {JSON_PATH}: {e}")


# ==============================================================================
# --- 3. APP RUNNER ---
# ==============================================================================

if __name__ == "__main__":
    logger.info("Starting FastAPI server with integrated HTML frontend...")
    # This will run the FastAPI app on port 8000
    # The frontend is served at http://localhost:8000/
    # The API is served at http://localhost:8000/api/...
    uvicorn.run(backend_app, host="0.0.0.0", port=8000)
    if not cursor.fetchone():
        admin_password = "Aqiguj@700"
        hashed_password = get_password_hash(admin_password) # Assumes get_password_hash is defined below
        cursor.execute(
            "INSERT INTO users (username, email, name, hashed_password, role) VALUES (?, ?, ?, ?, ?)",
            ("admin", "admin@parkroo.com", "Admin User", hashed_password, "admin")
        )
        logger.info(f"Default admin user 'admin' with password '{admin_password}' created.")

    db.commit()
    db.close()
    logger.info("Database tables verified/created successfully.")
    logger.info("Parking data will be loaded on the first request for each city.")    
    #yield
    logger.info("Backend server shutting down.")

backend_app = FastAPI(lifespan=lifespan)

# --- Middleware ---
backend_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Environment & Security Setup ---
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "your-default-secret-key-if-not-set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# --- Database Connection ---
def get_db():
    db = sqlite3.connect(DATABASE_URL, check_same_thread=False)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()

# --- User & Token Models ---
class User(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    role: str = 'user'

class UserUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    name: Optional[str] = None
    password: str

class BookingRequest(BaseModel):
    payment_method_id: str

class Booking(BaseModel):
    id: int
    user_id: int
    spot_id: str
    booking_time: datetime
    amount: int
    status: str

class DonationRequest(BaseModel):
    amount: int  # Amount in cents
    payment_method_id: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ActivityLogRequest(BaseModel):
    action: str
    details: Optional[Dict] = None

class ActivityLogEntry(BaseModel):
    username: str
    action: str
    details: Optional[str] = None
    timestamp: datetime

class ParkingFee(BaseModel):
    city: str
    street_name: str
    zone: Optional[str] = None
    peak_fee: Optional[float] = None
    off_peak_fee: Optional[float] = None
    shoulder_fee: Optional[float] = None
    notes: Optional[str] = None

class Vehicle(BaseModel):
    id: int
    user_id: int
    nickname: str
    make: Optional[str] = None
    model: Optional[str] = None
    license_plate: str

class VehicleCreate(BaseModel):
    nickname: str
    make: Optional[str] = None
    model: Optional[str] = None
    license_plate: str

class FavoriteSpotCreate(BaseModel):
    nickname: Optional[str] = None

class FavoriteSpot(BaseModel):
    user_id: int
    spot_id: str
    nickname: Optional[str]
    added_on: datetime

class PaymentIntentRequest(BaseModel):
    spot_id: str
    amount: int # Amount in cents

class PaymentMethod(BaseModel):
    id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool

# --- Email Configuration ---
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
    MAIL_FROM=os.getenv("MAIL_FROM", "noreply@example.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=None,
)

async def send_confirmation_email(email_to: str, username: str):
    """Sends a welcome email to a new user."""
    html = f"""
    <p>Hi {username},</p>
    <p>Welcome to Express Parking Australia! We're excited to have you on board.</p>
    <p>Happy parking!</p>
    """
    message = MessageSchema(subject="Welcome to Express Parking Australia!", recipients=[email_to], body=html, subtype=MessageType.html)
    fm = FastMail(conf)
    await fm.send_message(message)

async def send_password_reset_email(email_to: str, username: str, token: str):
    """Sends a password reset email to a user."""
    # MODIFIED: Point to new frontend URL (port 8000)
    reset_link = f"http://localhost:8000?reset_token={token}" 
    html = f"""
    <p>Hi {username},</p>
    <p>You requested a password reset. Click the link below to reset your password. This link is valid for 15 minutes.</p>
    <p><a href="{reset_link}">Reset Password</a></p>
    <p>If you did not request a password reset, please ignore this email.</p>
    """
    message = MessageSchema(
        subject="Password Reset Request", recipients=[email_to], body=html, subtype=MessageType.html
    )
    fm = FastMail(conf)
    await fm.send_message(message)

# --- Paginated Data Fetching & City-Specific Logic ---
def fetch_paginated_data(base_url: str, city_name: str) -> List[dict]:
    """Generic function to fetch all records from a paginated API."""
    all_records = []
    offset = 0
    limit = 100
    while True:
        try:
            params = {"limit": limit, "offset": offset}
            response = requests.get(base_url, params=params, timeout=40)
            response.raise_for_status()
            results = response.json().get("results", [])

            if not results:
                logger.info(f"Finished fetching all {city_name} data. Total records: {len(all_records)}")
                break

            all_records.extend(results)
            logger.info(f"Fetched {len(results)} {city_name} records... Total so far: {len(all_records)}")
            offset += limit
            time.sleep(0.25)
        except requests.RequestException as e:
            logger.error(f"API request failed during {city_name} pagination: {e}.")
            break
    return all_records

def _fetch_melbourne_data() -> List[dict]:
    """Fetches and processes all parking data for Melbourne."""
    url = "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/on-street-parking-bay-sensors/records"
    api_records = fetch_paginated_data(url, "Melbourne")
    
    processed_data = []
    au_tz = ZoneInfo("Australia/Sydney")
    in_tz = ZoneInfo("Asia/Kolkata")
    current_time = datetime.now(in_tz)

    if api_records:
        for item in api_records:
            location = item.get("location", {})
            lat, lng = float(location.get("lat", 0)), float(location.get("lon", 0))
            if lat != 0 or lng != 0:
                processed_data.append(
                    {
                        "city": "melbourne", "lat": lat, "lng": lng,
                        "name": str(item.get("bayid", f"spot_{current_time.timestamp()}")),
                        "street": item.get("st_marker_id", "Unknown"),
                        "occupied": item.get("status_description", "").lower() == "present",
                        "status_note": "Data from Live API", "last_updated": item.get("last_updated", current_time.isoformat()),
                        "kerbsideid": item.get("kerbsideid"), "zone_number": item.get("zone_number")
                    }
                )
        return processed_data

    logger.warning("Melbourne API fetch failed. Falling back to local JSON.")
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        for item in json_data:
            location = item.get("location", {})
            lat, lng = float(location.get("lat", 0)), float(location.get("lon", 0))
            if lat != 0 or lng != 0:
                processed_data.append({
                     "city": "melbourne", "lat": lat, "lng": lng,
                    "name": str(item.get("kerbsideid", f"spot_{current_time.timestamp()}")), "street": "Unknown",
                    "occupied": item.get("status_description", "").lower() == "present", "status_note": "Data from JSON file",
                    "last_updated": item.get("lastupdated", current_time.isoformat()), "fee": 2.5,
                    "auTime": current_time.astimezone(au_tz).strftime("%H:%M %d/%m/%Y"), "inTime": current_time.strftime("%H:%M %d/%m/%Y")
                })
        return processed_data
    except Exception as e:
        logger.error(f"Melbourne JSON fallback failed: {e}")
        return []

def _fetch_brisbane_data() -> List[dict]:
    """Fetches and processes all real-time parking facility data for Brisbane."""
    url = "https://www.data.brisbane.qld.gov.au/api/explore/v2.1/catalog/datasets/real-time-parking-data/records"
    api_records = fetch_paginated_data(url, "Brisbane")
    
    processed_data = []
    au_tz = ZoneInfo("Australia/Sydney")
    in_tz = ZoneInfo("Asia/Kolkata")
    current_time = datetime.now(in_tz)

    if api_records:
        for item in api_records:
            lat = item.get("latitude")
            lng = item.get("longitude")
            
            if lat is not None and lng is not None:
                try:
                    vacancies = int(item.get("vacancies", 0))
                    capacity = int(item.get("capacity", 0))
                except (ValueError, TypeError):
                    vacancies = 0
                    capacity = 0

                processed_data.append({
                    "city": "brisbane", 
                    "lat": float(lat), 
                    "lng": float(lng),
                    "name": item.get("facility_name", f"facility_{current_time.timestamp()}"),
                    "street": item.get("address", "Unknown"),
                    "occupied": vacancies <= 0,
                    "status_note": f"Vacancies: {vacancies}/{capacity}",
                    "last_updated": item.get("date", current_time.isoformat()),
                    "fee": 5.0,
                    "auTime": current_time.astimezone(au_tz).strftime("%H:%M %d/%m/%Y"),
                    "inTime": current_time.strftime("%H:%M %d/%m/%Y")
                })
    return processed_data

def _fetch_temp_csv_data() -> List[dict]:
    """Fetches and processes parking data from a local temp_location.csv file."""
    logger.info("Fetching data from local temp_location.csv")
    temp_csv_path = os.path.join(BASE_DIR, "temp_location.csv")
    processed_data = []
    try:
        df = pandas.read_csv(temp_csv_path)
        # Ensure required columns exist
        required_cols = ['Location', 'KerbsideID', 'Status_Description', 'Lastupdated']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"CSV file is missing one of the required columns: {required_cols}")
            return []

        for _, row in df.iterrows():
            lat, lng = map(float, row['Location'].split(','))
            processed_data.append({
                "city": "temp",
                "lat": lat, "lng": lng,
                "name": str(row['KerbsideID']),
                "street": f"Kerbside {row['KerbsideID']}",
                "occupied": row['Status_Description'].lower() == "present",
                "status_note": "Data from Local CSV",
                "last_updated": row['Lastupdated'],
            })
    except Exception as e:
        logger.error(f"Failed to load or process temp_location.csv: {e}")
    return processed_data

def _get_fee_for_spot(db: sqlite3.Connection, city: str, kerbside_id: int) -> Dict:
    """Helper to get fee data for a spot based on its Kerbside ID and the current time."""
    city_lower = city.lower()
    
    if city_lower == "melbourne":
        query = "SELECT * FROM parking_fees WHERE city = ? AND kerbside_id = ?"
        fee_data = db.execute(query, (city_lower, kerbside_id)).fetchone()
        if fee_data:
            now_melbourne = datetime.now(ZoneInfo("Australia/Melbourne"))
            weekday = now_melbourne.weekday()  # Monday is 0, Sunday is 6
            hour = now_melbourne.hour

            current_fee = None
            fee_type = "Off-Peak"
            if weekday < 5:  # Weekday (Mon-Fri)
                if 7 <= hour < 19: # 7 AM to 7 PM
                    current_fee = fee_data['weekday_peak']
                    fee_type = "Peak"
                else:
                    current_fee = fee_data['weekday_offpeak']
            else:  # Weekend
                current_fee = fee_data['weekend_rate']
                fee_type = "Weekend"
            
            return {"current_fee": current_fee, "fee_type": fee_type, "area_type": fee_data['area_type']}
    return {} # Default empty fee info for other cities or if not found

def _update_cache(city: str):
    """The actual data fetching logic, designed to be run in the background."""
    city_lower = city.lower()
    logger.info(f"BACKGROUND: Starting fresh data fetch for '{city_lower}'.")
    cache_status[city_lower] = "loading"
    processed_data = []
    
    # Use a new DB connection for the background thread
    db_conn = sqlite3.connect(DATABASE_URL)
    db_conn.row_factory = sqlite3.Row
    try:
        if city_lower == "melbourne":
            processed_data = _fetch_melbourne_data()
        elif city_lower == "brisbane":
            processed_data = _fetch_brisbane_data()
        elif city_lower == "temp":
            processed_data = _fetch_temp_csv_data()
        else:
            logger.warning(f"BACKGROUND: No data source configured for city: {city}")

        # --- Process fees ---
        for spot in processed_data:
            try:
                # Try to get kerbside ID, first from the spot, then from the map
                kerbside_id = spot.get('kerbsideid')
                if not kerbside_id:
                    bay_id = int(spot.get("name"))
                    kerbside_id = bay_to_kerbside_map.get(bay_id)
                
                if kerbside_id:
                    spot['kerbsideid'] = kerbside_id
                    fee_info = _get_fee_for_spot(db_conn, city_lower, int(kerbside_id))
                    spot.update(fee_info)
            except (ValueError, TypeError):
                continue # Skip spots with non-integer names (like generated ones or Brisbane)
                
    finally:
        db_conn.close()

    if processed_data:
        parking_data_cache[city_lower] = (processed_data, datetime.now())
        cache_status[city_lower] = "ready"
        logger.info(f"BACKGROUND: Cached {len(processed_data)} spots for '{city_lower}'.")
    else:
        cache_status[city_lower] = "failed"
        logger.error(f"BACKGROUND: Failed to fetch or process data for '{city_lower}'.")

def load_data(city: str, background_tasks: BackgroundTasks) -> List[dict]:
    """Main data loading function. Returns cached data or triggers a background update."""
    city_lower = city.lower()
    
    if city_lower not in parking_data_cache:
        # First time load for this city
        if cache_status.get(city_lower) != "loading":
            logger.info(f"No cache for '{city_lower}'. Triggering background fetch.")
            background_tasks.add_task(_update_cache, city)
        return [] # Return empty list immediately, frontend will show "loading"

    data, timestamp = parking_data_cache[city_lower]
    
    if datetime.now() - timestamp > CACHE_DURATION:
        # Cache is stale
        if cache_status.get(city_lower) != "loading":
            logger.info(f"Cache stale for '{city_lower}'. Triggering background fetch.")
            background_tasks.add_task(_update_cache, city)
        # Return stale data for now
        return data

    logger.info(f"✅ Serving '{city_lower}' data from fresh cache.")
    return data

# --- Authentication Functions ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user(db: sqlite3.Connection, username: str):
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user:
        return UserInDB(**user)
    return None

def get_user_by_email(db: sqlite3.Connection, email: str):
    """Checks if a user exists with the given email."""
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user:
        return UserInDB(**user)
    return None

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
    except JWTError:
        raise credentials_exception
    
    user = get_user(db, username=username)
    if user is None:
        raise credentials_exception
    return dict(user) # Return as a dict for easier access

async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    """Dependency to ensure the current user is an admin."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: requires admin privileges."
        )
    return current_user

# --- Helper for OSRM Routing ---
def _get_osrm_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, steps: bool = False):
    """
    Helper function to fetch a route from OSRM, including turn-by-turn steps.
    Raises exceptions on failure.
    """
    url_params = f"overview=full&geometries=geojson{'&steps=true' if steps else ''}"
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?{url_params}"
    
    logger.info(f"Requesting OSRM route: {url}")
    response = requests.get(url, timeout=40)
    response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
    
    data = response.json()
    if not data.get('routes'):
        raise ValueError("No routes found in OSRM response")
        
    route = data['routes'][0]
    
    if 'geometry' not in route or 'coordinates' not in route['geometry']:
        raise ValueError("Geometry or coordinates missing in OSRM response")

    # OSRM returns (lon, lat), Leaflet needs (lat, lon)
    geometry_coords = route['geometry']['coordinates']
    route_geometry = [[coord[1], coord[0]] for coord in geometry_coords]
    
    if not steps:
        return {"geometry": route_geometry, "steps": [], "summary": {}}

    # Process steps if requested
    route_steps = []
    if route.get('legs') and route['legs'][0].get('steps'):
        for step in route['legs'][0]['steps']:
            maneuver = step.get('maneuver', {})
            instruction = maneuver.get('instruction')
            if not instruction:
                # Fallback for simple steps
                maneuver_type = maneuver.get('type', 'continue').replace('_', ' ').title()
                step_name = step.get('name', 'unnamed road')
                instruction = f"{maneuver_type} onto {step_name}"
            
            route_steps.append({
                "instruction": instruction,
                "distance": step.get('distance', 0), # in meters
                "duration": step.get('duration', 0), # in seconds
            })
            
    return {
        "geometry": route_geometry, 
        "steps": route_steps, 
        "summary": {
            "total_distance": route.get('distance', 0),
            "total_duration": route.get('duration', 0)
        }
    }


# ==============================================================================
# --- 2. API ENDPOINTS ---
# ==============================================================================

# --- NEW: Serve the HTML Frontend ---
@backend_app.get("/", response_class=HTMLResponse)
async def get_frontend():
    """Serves the embedded HTML frontend."""
    return HTML_FRONTEND

# --- Parking Data API ---
@backend_app.get("/api/parking-data/{city}")
async def get_parking_data(city: str, background_tasks: BackgroundTasks):
    """
    Main endpoint to get parking data for a city.
    Triggers a background update if data is stale.
    """
    valid_cities = ["melbourne", "brisbane", "temp"]
    if city.lower() not in valid_cities:
        raise HTTPException(status_code=404, detail="City not found. Try 'melbourne' or 'brisbane'.")
    
    data = load_data(city.lower(), background_tasks)
    return data

@backend_app.get("/api/route")
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float):
    """
    Provides routing information from OSRM.
    """
    try:
        route_data = _get_osrm_route(start_lat, start_lon, end_lat, end_lon, steps=False)
        return {"geometry": route_data["geometry"]}
    except requests.RequestException as e:
        logger.error(f"OSRM request failed: {e}")
        raise HTTPException(status_code=503, detail="Routing service is unavailable.")
    except ValueError as e:
        logger.error(f"OSRM data processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing route data: {e}")
    except Exception as e:
        logger.error(f"Unknown routing error: {e}")
        raise HTTPException(status_code=500, detail="An unknown error occurred while calculating the route.")

@backend_app.get("/api/cache-status")
async def get_cache_status(admin: dict = Depends(get_current_admin_user)):
    """(Admin) Check the status of the data cache."""
    return {"cache_status": cache_status, "cache_keys": list(parking_data_cache.keys())}


# --- User & Auth API Endpoints ---

@backend_app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: sqlite3.Connection = Depends(get_db)
):
    """Provides a JWT access token for a valid user."""
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@backend_app.post("/api/users/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(
    user: UserCreate, 
    background_tasks: BackgroundTasks, 
    db: sqlite3.Connection = Depends(get_db)
):
    """Registers a new user."""
    if get_user(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if user.email and get_user_by_email(db, user.email):
         raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    
    # Create Stripe customer
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.name or user.username,
            description=f"Parkroo user: {user.username}"
        )
        stripe_customer_id = customer.id
    except Exception as e:
        logger.error(f"Stripe customer creation failed for {user.username}: {e}")
        raise HTTPException(status_code=500, detail="Could not create payment profile.")

    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, name, hashed_password, stripe_customer_id) VALUES (?, ?, ?, ?, ?)",
            (user.username, user.email, user.name, hashed_password, stripe_customer_id)
        )
        db.commit()
        new_user_id = cursor.lastrowid
        
        # Log this activity
        background_tasks.add_task(
            log_activity, new_user_id, "register", {"username": user.username}, db_url=DATABASE_URL
        )
        
        # Send welcome email
        if user.email:
            background_tasks.add_task(send_confirmation_email, user.email, user.username)

        return User(id=new_user_id, username=user.username, email=user.email, name=user.name, role='user')
    
    except sqlite3.IntegrityError as e:
        logger.error(f"Database error during registration for {user.username}: {e}")
        raise HTTPException(status_code=400, detail=f"Registration failed: {e}")
    except Exception as e:
        logger.error(f"Generic error during registration for {user.username}: {e}")
        # Rollback Stripe customer creation? Maybe not, just log it.
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


@backend_app.get("/api/users/me", response_model=User)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Returns the details of the currently authenticated user."""
    # current_user is already a dict, just need to ensure it fits the User model
    return User(**current_user)

@backend_app.put("/api/users/me", response_model=User)
async def update_users_me(
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    """Updates the current user's email or name."""
    user_id = current_user['id']
    
    # Check if email is already taken by another user
    if user_update.email:
        existing_user = db.execute("SELECT id FROM users WHERE email = ? AND id != ?", (user_update.email, user_id)).fetchone()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email is already in use by another account.")

    # Update fields that are provided
    fields_to_update = user_update.dict(exclude_unset=True)
    if not fields_to_update:
        return User(**current_user) # Return current user if no changes

    set_clause = ", ".join([f"{field} = ?" for field in fields_to_update.keys()])
    values = list(fields_to_update.values()) + [user_id]
    
    try:
        db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", tuple(values))
        db.commit()
        
        # Update Stripe customer
        if 'email' in fields_to_update or 'name' in fields_to_update:
            try:
                stripe_customer_id = current_user.get('stripe_customer_id')
                if stripe_customer_id:
                    stripe.Customer.modify(
                        stripe_customer_id,
                        email=user_update.email,
                        name=user_update.name,
                    )
            except Exception as e:
                logger.error(f"Failed to update Stripe customer {stripe_customer_id}: {e}")
                # Don't fail the request, just log the error
        
        updated_user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return User(**updated_user)
        
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user profile.")


@backend_app.post("/api/users/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest, 
    background_tasks: BackgroundTasks, 
    db: sqlite3.Connection = Depends(get_db)
):
    """Initiates a password reset by sending an email with a token."""
    user = get_user_by_email(db, request.email)
    if user:
        token_expires = timedelta(minutes=15)
        reset_token = create_access_token(
            data={"sub": user.username, "type": "password_reset"}, 
            expires_delta=token_expires
        )
        background_tasks.add_task(send_password_reset_email, user.email, user.username, reset_token)
        
    return JSONResponse(
        status_code=200, 
        content={"message": "If an account with this email exists, a password reset link has been sent."}
    )

@backend_app.post("/api/users/reset-password")
async def reset_password(
    request: ResetPasswordRequest, 
    db: sqlite3.Connection = Depends(get_db)
):
    """Resets the user's password using a valid token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(request.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if username is None or token_type != "password_reset":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user(db, username=username)
    if user is None:
        raise credentials_exception
        
    new_hashed_password = get_password_hash(request.new_password)
    db.execute("UPDATE users SET hashed_password = ? WHERE username = ?", (new_hashed_password, username))
    db.commit()
    
    return {"message": "Password has been reset successfully."}


# --- Payment & Booking API Endpoints ---

@backend_app.post("/api/payments/create-payment-intent", status_code=status.HTTP_201_CREATED)
async def create_payment_intent(
    request: PaymentIntentRequest,
    current_user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    """Creates a Stripe PaymentIntent for a booking."""
    stripe_customer_id = current_user.get('stripe_customer_id')
    if not stripe_customer_id:
        raise HTTPException(status_code=400, detail="User does not have a payment profile.")

    try:
        intent = stripe.PaymentIntent.create(
            amount=request.amount, # Amount in cents
            currency="aud",
            customer=stripe_customer_id,
            metadata={
                "user_id": current_user['id'],
                "username": current_user['username'],
                "spot_id": request.spot_id
            },
            # setup_usage='on_session', # Use this if you want to save the card for later
        )
        return {"clientSecret": intent.client_secret}
    except Exception as e:
        logger.error(f"Stripe PaymentIntent creation failed for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@backend_app.post("/api/payments/add-payment-method", status_code=201)
async def add_payment_method(
    payment_method_id: str = Depends(lambda x: x.payment_method_id), # Simple way to get it from a small model
    current_user: dict = Depends(get_current_user)
):
    """Attaches a new payment method to the user's Stripe customer."""
    stripe_customer_id = current_user.get('stripe_customer_id')
    if not stripe_customer_id:
        raise HTTPException(status_code=400, detail="User does not have a payment profile.")

    try:
        # Attach the payment method to the customer
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=stripe_customer_id
        )
        
        # Set it as the default payment method
        stripe.Customer.modify(
            stripe_customer_id,
            invoice_settings={"default_payment_method": payment_method_id}
        )
        
        return {"message": "Payment method added and set as default successfully."}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error adding payment method for user {current_user['id']}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@backend_app.get("/api/payments/my-payment-methods", response_model=List[PaymentMethod])
async def get_my_payment_methods(current_user: dict = Depends(get_current_user)):
    """Retrieves the list of saved payment methods for the user."""
    stripe_customer_id = current_user.get('stripe_customer_id')
    if not stripe_customer_id:
        return [] # No profile, no payment methods

    try:
        # Get the customer's default payment method
        customer = stripe.Customer.retrieve(stripe_customer_id)
        default_pm_id = customer.invoice_settings.default_payment_method

        # List all saved card payment methods
        payment_methods = stripe.PaymentMethod.list(
            customer=stripe_customer_id,
            type="card"
        )
        
        processed_methods = []
        for pm in payment_methods.data:
            processed_methods.append(PaymentMethod(
                id=pm.id,
                brand=pm.card.brand,
                last4=pm.card.last4,
                exp_month=pm.card.exp_month,
                exp_year=pm.card.exp_year,
                is_default=(pm.id == default_pm_id)
            ))
            
        return processed_methods
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error listing payment methods for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@backend_app.post("/api/bookings", status_code=201)
async def create_booking(
    payment_intent_id: str, # Sent from frontend after successful payment
    db: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Confirms a booking after a successful payment."""
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if intent.status != 'succeeded':
            raise HTTPException(status_code=400, detail="Payment was not successful.")
            
        # Check metadata
        user_id = intent.metadata.get('user_id')
        spot_id = intent.metadata.get('spot_id')
        
        if not user_id or not spot_id or int(user_id) != current_user['id']:
            raise HTTPException(status_code=400, detail="Payment intent metadata mismatch.")
            
        booking_time = datetime.now(ZoneInfo("UTC")).isoformat()
        amount = intent.amount
        
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO bookings (user_id, spot_id, booking_time, amount, status) VALUES (?, ?, ?, ?, ?)",
            (current_user['id'], spot_id, booking_time, amount, "confirmed")
        )
        db.commit()
        booking_id = cursor.lastrowid
        
        return {
            "message": "Booking confirmed!",
            "booking_id": booking_id,
            "spot_id": spot_id,
            "amount": amount,
            "timestamp": booking_time
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error confirming booking for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail=f"Payment confirmation error: {e}")
    except Exception as e:
        logger.error(f"Booking creation error for user {current_user['id']}: {e}")
        raise HTTPException(status_code=500, detail=f"Booking error: {e}")


# --- Admin & Logging API Endpoints ---

def log_activity(user_id: int, action: str, details: Optional[Dict], db_url: str):
    """Background task to log user activity to the database."""
    try:
        # Must connect in the new thread
        db = sqlite3.connect(db_url)
        timestamp = datetime.now(ZoneInfo("UTC")).isoformat()
        details_json = json.dumps(details) if details else None
        
        db.execute(
            "INSERT INTO activity_log (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details_json, timestamp)
        )
        db.commit()
        db.close()
        logger.info(f"Logged activity for user {user_id}: {action}")
    except Exception as e:
        logger.error(f"Failed to log activity for user {user_id}: {e}")

@backend_app.post("/api/log-activity")
async def log_user_activity(
    request: ActivityLogRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Endpoint for the frontend to log arbitrary user actions (e.g., searches)."""
    user_id = current_user['id']
    background_tasks.add_task(log_activity, user_id, request.action, request.details, db_url=DATABASE_URL)
    return {"message": "Activity logged"}

@backend_app.get("/api/admin/activity-log", response_model=List[ActivityLogEntry])
async def get_activity_log(
    limit: int = 50,
    admin: dict = Depends(get_current_admin_user),
    db: sqlite3.Connection = Depends(get_db)
):
    """(Admin) Retrieves the most recent activity logs for all users."""
    query = """
        SELECT u.username, a.action, a.details, a.timestamp 
        FROM activity_log a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC
        LIMIT ?
    """
    logs = db.execute(query, (limit,)).fetchall()
    return [ActivityLogEntry(**log) for log in logs]

@backend_app.get("/api/admin/users", response_model=List[User])
async def get_all_users(
    admin: dict = Depends(get_current_admin_user),
    db: sqlite3.Connection = Depends(get_db)
):
    """(Admin) Retrieves a list of all registered users."""
    users = db.execute("SELECT id, username, email, name, role FROM users ORDER BY id").fetchall()
    return [User(**user) for user in users]


# ==============================================================================
# --- 3. APP RUNNER ---
# ==============================================================================

if __name__ == "__main__":
    logger.info("Starting FastAPI server with integrated HTML frontend...")
    # This will run the FastAPI app on port 8000
    # The frontend is served at http://localhost:8000/
    # The API is served at http://localhost:8000/api/...
    uvicorn.run(backend_app, host="0.0.0.0", port=8000)