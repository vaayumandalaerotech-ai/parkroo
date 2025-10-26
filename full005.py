import streamlit as st
import pydeck as pdk
import requests
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import pandas
from datetime import datetime, timedelta
from streamlit_lottie import st_lottie
from typing import Optional, Dict, Any, Tuple, Literal
import time
import json 
        raise HTTPException(status_code=404, detail="add_card.html not found")


# ==============================================================================
# --- 2. FRONTEND (Streamlit) CODE ---
# ==============================================================================

# --- Constants ---
CITY_CENTERS = {
    "brisbane": [-27.4698, 153.0251],
    "sydney": [-33.8688, 151.2093],
    "melbourne": [-37.8136, 144.9631]
}
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def run_frontend():
    """
    This function contains the entire Streamlit frontend application.
    """
    import folium
    from streamlit_folium import st_folium
    from streamlit_searchbox import st_searchbox

    st.set_page_config(layout="wide")

    def init_session_state():
        """Initialize session state variables."""
        defaults = {
            'token': None,
            'user': None,
            'spots': [],
            'path_data': None,
            'selected_spot': None,
            'viewing_bookings': False,
            'dark_theme': True,
            'viewing_settings': False,
            'navigation_active': False,
            'profile_page': 'menu', # 'menu', 'profile', 'vehicles', 'add_vehicle', 'favorites', 'payment', 'help', 'settings'
            'viewing_admin': False,
            'location_set_by_user': False,
            'selected_city': 'melbourne',
            'current_lat': CITY_CENTERS["melbourne"][0],
            'current_lng': CITY_CENTERS["melbourne"][1],
            'dest_lat': None,
            'dest_lng': None,
            'leg1_route': None,
            'leg2_route': None,
            'leg2_steps': None,
            'leg2_summary': None,
            'direct_route': None,
            'stripe_pk': None,
            'first_login_refresh_done': False,
        } 
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    init_session_state()

    # Check for payment success in URL
    query_params = st.query_params
    if "payment_success" in query_params and "spot_id" in query_params:
        spot_id = query_params["spot_id"]
        st.success(f"✅ Payment successful! Your booking for spot {spot_id} is confirmed.")
        st.query_params.clear()
    
    if "card_saved" in query_params:
        st.success("✅ Your new payment method has been saved successfully!")
        st.session_state.profile_page = 'payment' # Navigate to the payment methods page
        st.query_params.clear()

    # Check for password reset token in URL
    if "reset_token" in query_params:
        st.session_state.show_reset_password_form = True
        st.session_state.reset_token = query_params["reset_token"]
        st.query_params.clear()

    # --- API & Data Helper Functions ---
    def api_request(
        method: Literal["GET", "POST", "DELETE", "PUT"],
        path: str,
        **kwargs: Any
    ) -> Optional[requests.Response]:
        """A small wrapper for API requests with error handling."""
        try:
            kwargs.setdefault('timeout', 45)
            url = f"{API_BASE_URL}{path}"
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            st.error(f"API Error: {e.response.status_code} - {e.response.text}", icon="🚨")
        except requests.RequestException as e:
            st.error(f"An unexpected error occurred: {e}")
        return None

    def handle_set_destination():
        destination_address = st.session_state.get("destination_search") # Read from the searchbox state
        if destination_address:
            with st.spinner("Geocoding..."):
                geolocator = Nominatim(user_agent="parking_finder")
                location = geolocator.geocode(destination_address, country_codes="AU", timeout=10)
                if location:
                    st.session_state.dest_lat, st.session_state.dest_lng = location.latitude, location.longitude
                    st.session_state.destination_address_str = location.address
                    st.success(f"Destination set to: {location.address}. Click 'Find Spots' to continue.")
                    st.rerun() # Rerun to update the UI
                else: st.error(f"Could not find the destination: {destination_address}")
        else: st.warning("Please enter and select a destination from the search box.")

    @st.cache_data(ttl=3600) # Cache for 1 hour
    def get_address_from_coords(lat: float, lon: float) -> str:
        """Reverse geocode coordinates to get an address."""
        try:
            geolocator = Nominatim(user_agent="parking_finder_app")
            location = geolocator.reverse((lat, lon), exactly_one=True, timeout=10)
            return location.address if location else "Unknown Location"
        except Exception:
            return f"Lat: {lat:.4f}, Lon: {lon:.4f}"

    def render_loading_screen(message: str):
        """Displays a full-screen Lottie animation and a loading message."""
        try:
            with open("loading_animation.json", "r") as f:
                lottie_json = json.load(f)
                st_lottie(lottie_json, speed=1, height=200, key="loading_animation_file")
        except (FileNotFoundError, json.JSONDecodeError):
            st.warning("Could not load animation file.")
        
        st.markdown(f"<h3 style='text-align: center;'>{message}</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>This may take a moment on the first load...</p>", unsafe_allow_html=True)

    # --- UI Rendering Functions ---
    def render_navigation_view():
        st.header("Navigation")
        if st.button("Exit Navigation", key="exit_nav_btn", use_container_width=True):
            st.session_state.navigation_active = False
            st.session_state.leg1_route = None
            st.session_state.leg2_route = None
            st.session_state.leg2_steps = None
            st.session_state.leg2_summary = None
            st.session_state.direct_route = None
            st.rerun()
        
        st.subheader("Parking to Destination")
        if st.session_state.leg2_summary:
            summary = st.session_state.leg2_summary
            distance_km = summary['total_distance_meters'] / 1000
            duration_min = summary['total_duration_seconds'] / 60
            st.metric("Total Distance", f"{distance_km:.2f} km")
            st.metric("Estimated Time", f"{duration_min:.1f} minutes")

        if st.session_state.leg2_steps:
            with st.expander("Show Turn-by-Turn Directions"):
                for i, step in enumerate(st.session_state.leg2_steps):
                    st.write(f"{i+1}. {step['instruction']} ({step['distance_meters']:.0f} m)")

    def render_bookings_view():
        st.header("My Bookings")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}    
        response = api_request("GET", "/api/my-bookings", headers=headers, timeout=10)
        if response and response.status_code == 200:
            bookings = response.json()
            if bookings:
                for booking in sorted(bookings, key=lambda x: x['booking_time'], reverse=True):
                    booking_time = datetime.fromisoformat(booking['booking_time']).strftime('%Y-%m-%d %H:%M')
                    with st.expander(f"Spot: {booking['spot_id']} on {booking_time}"):
                        st.write(f"**Booking ID:** {booking['id']}")
                        st.write(f"**Amount Paid:** ${booking['amount']/100:.2f}")
                        st.write(f"**Status:** {booking['status']}")
            else:
                st.info("You have no past bookings.")

        if st.button("⬅️ Back to Map Controls", key="exit_bookings_btn", use_container_width=True):
            st.session_state.viewing_bookings = False
            st.rerun()

    def render_vehicles_view():
        st.subheader("My Vehicles")
        
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = api_request("GET", "/api/vehicles", headers=headers)

        if response and response.status_code == 200:
            vehicles = response.json()
            if vehicles:
                for v in vehicles:
                    with st.container(border=True):
                        st.write(f"**{v['nickname']}**")
                        st.write(f"{v.get('make', '')} {v.get('model', '')}")
                        st.code(v['license_plate'])
            else:
                st.info("You haven't added any vehicles yet.")
        
        if st.button("＋ Add New Vehicle", use_container_width=True):
            st.session_state.profile_page = 'add_vehicle'
            st.rerun()

        if st.button("⬅️ Back to Profile", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'menu'
            st.rerun()

    def render_add_vehicle_view():
        st.subheader("Add a New Vehicle")
        with st.form("add_vehicle_form"):
            nickname = st.text_input("Nickname (e.g., 'My Honda')")
            license_plate = st.text_input("License Plate")
            make = st.text_input("Make (Optional)")
            model = st.text_input("Model (Optional)")
            
            submitted = st.form_submit_button("Save Vehicle")
            if submitted:
                if not nickname or not license_plate:
                    st.error("Nickname and License Plate are required.")
                else:
                    payload = {"nickname": nickname, "license_plate": license_plate, "make": make, "model": model}
                    headers = {"Authorization": f"Bearer {st.session_state.token}"}
                    response = api_request("POST", "/api/vehicles", headers=headers, json=payload)
                    if response and response.status_code == 200:
                        st.success("Vehicle added!")
                        st.session_state.profile_page = 'vehicles'
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to add vehicle.")

        if st.button("⬅️ Back to My Vehicles", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'vehicles'
            st.rerun()

    def render_favorites_view():
        st.subheader("❤️ My Favorite Spots")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = api_request("GET", "/api/favorites", headers=headers)

        if response and response.status_code == 200:
            favorites = response.json()
            if favorites:
                for fav in sorted(favorites, key=lambda x: x['added_on'], reverse=True):
                    spot_id = fav['spot_id']
                    nickname = fav.get('nickname') or f"Spot {spot_id}"
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{nickname}**")
                            st.caption(f"Spot ID: {spot_id}")
                        with col2:
                            if st.button("❌", key=f"del_fav_{spot_id}", help="Remove from favorites"):
                                del_resp = api_request("DELETE", f"/api/favorites/{spot_id}", headers=headers)
                                if del_resp and del_resp.status_code == 200:
                                    st.success("Favorite removed.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to remove favorite.")
            else:
                st.info("You haven't added any favorite spots yet. Select a spot on the map to add it!")

        if st.button("⬅️ Back to Profile", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'menu'
            st.rerun()

    def render_payment_methods_view():
        st.subheader("💳 My Payment Methods")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = api_request("GET", "/api/payment-methods", headers=headers)

        if response and response.status_code == 200:
            payment_methods = response.json()
            if payment_methods:
                for pm in payment_methods:
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"**{pm['brand'].title()}** ending in **** {pm['last4']}")
                            st.caption(f"Expires {pm['exp_month']}/{pm['exp_year']}")
                        with col2:
                            if st.button("Delete", key=f"del_pm_{pm['id']}", type="secondary"):
                                del_resp = api_request("DELETE", f"/api/payment-methods/{pm['id']}", headers=headers)
                                if del_resp and del_resp.status_code == 200:
                                    st.success("Payment method removed.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to remove payment method.")
            else:
                st.info("You have no saved payment methods.")

        if not st.session_state.stripe_pk:
            pk_response = api_request("GET", "/config")
            if pk_response and pk_response.status_code == 200 and pk_response.json().get("publishableKey"):
                st.session_state.stripe_pk = pk_response.json().get("publishableKey")

        if st.session_state.stripe_pk:
            add_card_url = f"http://localhost:8000/add_card.html?token={st.session_state.token}&pk={st.session_state.stripe_pk}"
            st.link_button("＋ Add New Card", url=add_card_url, use_container_width=True)
        else:
            st.error("Payment gateway is not configured. Cannot add new cards.")

        if st.button("⬅️ Back to Profile", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'menu'
            st.rerun()

    def render_profile_update_view():
        st.subheader("Update Profile")
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        user_resp = api_request("GET", "/api/me", headers=headers)
        
        if user_resp and user_resp.status_code == 200:
            user_data = user_resp.json()
            
            with st.form("profile_form"):
                st.write(f"**Username:** {user_data.get('username')}")
                email = st.text_input("Email", value=user_data.get('email', ''))
                name = st.text_input("Name", value=user_data.get('name', ''))
                
                submitted = st.form_submit_button("Update Profile")
                if submitted:
                    update_payload = {"email": email, "name": name}
                    update_resp = api_request("POST", "/api/me/update", headers=headers, json=update_payload)
                    if update_resp and update_resp.status_code == 200:
                        st.success("Profile updated successfully!")
                        time.sleep(1)
                        st.session_state.profile_page = 'menu'
                        st.rerun()
                    else:
                        st.error("Failed to update profile.")
        
        if st.button("⬅️ Back to Profile Menu", use_container_width=True, type="secondary"):
            st.session_state.profile_page = 'menu'
            st.rerun()

    def render_settings_view():
        st.header("Profile")

        # Main Profile Menu
        if st.session_state.profile_page == 'menu':
            if st.button("👤 Edit Profile", use_container_width=True):
                st.session_state.profile_page = 'profile'
                st.rerun()
            if st.button("🚗 My Vehicles", use_container_width=True):
                st.session_state.profile_page = 'vehicles'
                st.rerun()
            if st.button("❤️ My Favorites", use_container_width=True):
                st.session_state.profile_page = 'favorites'
                st.rerun()
            if st.button("💳 Payment Methods", use_container_width=True):
                st.session_state.profile_page = 'payment'
                st.rerun()
            if st.button("❓ Help Center", use_container_width=True):
                st.info("Help Center is coming soon!")
            
            st.markdown("---")
            st.subheader("Settings")
            st.selectbox("Language", ["English", "Spanish (coming soon)"], disabled=True)
            st.toggle("Push Notifications", disabled=True)
            st.toggle("Email Notifications", disabled=True)
            st.toggle("Dark Mode", key="dark_theme")
            st.markdown("---")

            if st.button("Logout", key="logout_btn_settings", type="secondary", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        # "Edit Profile" Sub-page
        elif st.session_state.profile_page == 'profile':
            render_profile_update_view()

        # "My Vehicles" Sub-page
        elif st.session_state.profile_page == 'vehicles':
            render_vehicles_view()

        # "Add Vehicle" Sub-page
        elif st.session_state.profile_page == 'add_vehicle':
            render_add_vehicle_view()
        
        # "My Favorites" Sub-page
        elif st.session_state.profile_page == 'favorites':
            render_favorites_view()
        
        # "Payment Methods" Sub-page
        elif st.session_state.profile_page == 'payment':
            render_payment_methods_view()


    def render_admin_view():
        """Renders the admin dashboard to view user activity."""
        st.header("👑 Admin Dashboard")
        st.subheader("User Activity Log")

        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = api_request("GET", "/api/admin/activity-log", headers=headers)

        if response and response.status_code == 200:
            activities = response.json()
            if activities:
                df = pandas.DataFrame(activities)
                df['timestamp'] = pandas.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No user activity has been logged yet.")
        elif response and response.status_code == 403:
            st.error("You do not have permission to view this page.")
        else:
            st.error("Failed to load activity log.")

        if st.button("⬅️ Back to Map", key="exit_admin_btn", use_container_width=True):
            st.session_state.viewing_admin = False
            st.rerun()

    def handle_find_spots(top_n):
        """Logic for the 'Find Spots' button, refactored for clarity."""
        if not st.session_state.dest_lat:
            st.warning("Please set a destination first using 'Set Destination'.")
            return

        with st.spinner("Finding nearest spots and calculating routes..."):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            api_request("POST", "/api/log-activity", headers=headers, json={"action": "find_spots", "details": {"destination_lat": st.session_state.dest_lat, "destination_lng": st.session_state.dest_lng, "top_n": top_n}})

            start_loc = (st.session_state.current_lat, st.session_state.current_lng)
            dest_loc = (st.session_state.dest_lat, st.session_state.dest_lng)
            
            params = {"start_lat": start_loc[0], "start_lon": start_loc[1], "end_lat": dest_loc[0], "end_lon": dest_loc[1], "steps": "false"}
            response = api_request("GET", "/api/route", params=params)
            if response and response.status_code == 200:
                st.session_state.direct_route = response.json().get('geometry')
            else:
                st.warning("Could not calculate direct route to destination.")
            
            target_lat = st.session_state.dest_lat
            target_lng = st.session_state.dest_lng
            response = api_request("GET", f"/api/path/{st.session_state.selected_city}/{target_lat}/{target_lng}", params={'top': top_n})
            if response and response.status_code == 200:
                st.session_state.path_data = response.json()
                st.info("Found nearest spots. Map is now showing results.")
            
            st.session_state.navigation_active = False
            st.session_state.leg1_route = None
            st.session_state.leg2_route = None
            st.session_state.leg2_steps = None
            st.session_state.leg2_summary = None
            st.rerun()

    # --- Main Application Logic ---
    if st.session_state.get('show_reset_password_form', False):
        st.title("Reset Your Password")
        reset_cols = st.columns([1, 2, 1])
        with reset_cols[1]:
            with st.form("reset_password_form"):
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm New Password", type="password")
                submitted = st.form_submit_button("Reset Password")

                if submitted:
                    if not new_password or new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        token = st.session_state.get("reset_token")
                        if not token:
                            st.error("Reset token is missing. Please request a new link.")
                        else:
                            response = api_request(
                                "POST",
                                "/reset-password",
                                json={"token": token, "new_password": new_password}
                            )
                            if response and response.status_code == 200:
                                st.success("Password reset successfully! You can now log in with your new password.")
                                st.session_state.show_reset_password_form = False
                                st.session_state.reset_token = None
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Password reset failed. The link may have expired or is invalid.")

    elif 'token' not in st.session_state or st.session_state.token is None:
        st.title("Express Parking Australia")
        st.info("Please log in or register to access parking features. The map below is for demonstration only.")
        
        main_cols = st.columns([1, 2])
        with main_cols[0]:
            logo_cols = st.columns([1, 2, 1])
            with logo_cols[1]:
                st.image("symball.jpeg", width=150)

            st.header("Welcome")
            tab1, tab2 = st.tabs(["Login", "Register"])
            with tab1:
                with st.form("login_form"):
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
                    submitted = st.form_submit_button("Login")
                    if submitted:
                        response = api_request("POST", "/token", data={"username": username, "password": password})
                        if response and response.status_code == 200:
                            st.session_state.token = response.json()["access_token"]
                            st.session_state.user = username
                            headers = {"Authorization": f"Bearer {st.session_state.token}"}
                            api_request("POST", "/api/log-activity", headers=headers, json={"action": "login"})
                            st.session_state.first_login_refresh_done = False
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
            
            if st.button("Forgot Password?"):
                st.session_state.show_forgot_password = True

            if st.session_state.get('show_forgot_password'):
                with st.form("forgot_password_form"):
                    st.subheader("Request Password Reset")
                    email = st.text_input("Enter your account email")
                    submitted = st.form_submit_button("Send Reset Link")
                    if submitted:
                        response = api_request("POST", "/forgot-password", json={"email": email})
                        if response:
                            st.success("If an account with that email exists, a password reset link has been sent.")
                            st.session_state.show_forgot_password = False
            
            with tab2:
                with st.form("register_form"):
                    reg_username = st.text_input("Choose Username")
                    reg_name = st.text_input("Full Name")
                    reg_email = st.text_input("Email")
                    reg_password = st.text_input("Choose Password", type="password")
                    reg_submitted = st.form_submit_button("Register")
                    if reg_submitted:
                        response = api_request("POST", "/register", json={"username": reg_username, "name": reg_name, "password": reg_password, "email": reg_email})
                        if response and response.status_code == 201:
                            st.success("Registration successful! Please log in.")
                        else:
                            error_detail = response.json().get('detail', 'Unknown error') if response else 'Server Error'
                            if "Username already registered" in error_detail:
                                st.error("Username already exists. Please choose another one.")
                            elif "Email already in use" in error_detail:
                                st.error("This email is already in use. Please use a different email.")
                            else:
                                st.error(f"Registration failed: {error_detail}")
        
        with main_cols[1]:
            m = folium.Map(location=CITY_CENTERS["melbourne"], zoom_start=12, tiles="cartodbdark_matter" if st.session_state.dark_theme else "cartodbpositron", zoom_control=False)
            st_folium(m, width='100%', height=600)

    else:
        # --- LOGGED-IN STATE ---
        # If it's the first time after login or spots are empty, trigger the data load and poll for completion.
        if not st.session_state.get('first_login_refresh_done', False):
            # This call triggers the backend to start caching data in the background
            api_request("GET", f"/api/parking/{st.session_state.selected_city}")

            with st.spinner(f"Finding parking spots in {st.session_state.selected_city.title()}... This may take a moment."):
                max_wait_time = 120  # Wait for up to 2 minutes
                start_time = time.time()
                while time.time() - start_time < max_wait_time:
                    status_resp = api_request("GET", f"/api/cache-status/{st.session_state.selected_city}", timeout=5)
                    if status_resp and status_resp.json().get("status") == "ready":
                        break
                    time.sleep(2) # Poll every 2 seconds

            final_response = api_request("GET", f"/api/parking/{st.session_state.selected_city}")
            if final_response and final_response.status_code == 200:
                st.session_state.spots = final_response.json()
            else:
                st.error("Failed to retrieve data from the server after loading.")
            
            st.session_state.first_login_refresh_done = True
            st.rerun()

        with st.container():
            top_bar_cols = st.columns([1, 4, 1, 1, 1, 1])

            with top_bar_cols[0]:
                cities = list(CITY_CENTERS.keys())
                try:
                    default_index = cities.index(st.session_state.selected_city)
                except ValueError:
                    default_index = cities.index('melbourne') 
                st.selectbox("City", cities, index=default_index, key='selected_city', label_visibility="collapsed")

            selected_city_coords = CITY_CENTERS[st.session_state.selected_city]
            if not st.session_state.location_set_by_user:
                if (st.session_state.current_lat != selected_city_coords[0] or 
                    st.session_state.current_lng != selected_city_coords[1]):
                    st.session_state.current_lat = selected_city_coords[0]
                    st.session_state.current_lng = selected_city_coords[1]
                    st.rerun()
            
            with top_bar_cols[1]:
                if not st.session_state.dest_lat:
                    # --- Autocomplete Search Box ---
                    # The on_change callback now handles setting the destination automatically.
                    st_searchbox(
                        search_function=lambda x, **kwargs: api_request("GET", f"/api/search-places?query={x}").json() if x else [],
                        placeholder="Search for destination...",
                        label="Destination",
                        key="destination_search",
                        on_change=handle_set_destination,
                    )
                else:
                    # Show the set destination address, but disable input
                    st.text_input("Destination", value=st.session_state.get('destination_address_str', 'Destination Set'), label_visibility="collapsed", disabled=True)
            
            with top_bar_cols[2]:
                if st.session_state.dest_lat:
                    if st.button("Clear", use_container_width=True, help="Clear Destination"):
                        st.session_state.dest_lat = None
                        st.session_state.dest_lng = None
                        st.session_state.path_data = None
                        st.session_state.direct_route = None
                        st.rerun()
            
            with top_bar_cols[3]:
                if st.button(f"Find Spots", key="find_spots_btn", use_container_width=True, disabled=not st.session_state.dest_lat):
                    handle_find_spots(3) # Using a fixed value of 3 for simplicity

            with top_bar_cols[4]:
                if st.button(f"Refresh Data", key="refresh_data_btn", use_container_width=True):
                    with st.spinner(f"Fetching data for {st.session_state.selected_city.title()}..."):
                        st.session_state.path_data = None
                        st.session_state.selected_spot = None
                        st.session_state.dest_lat = None
                        st.session_state.dest_lng = None
                        st.session_state.direct_route = None
                        response = api_request("GET", f"/api/parking/{st.session_state.selected_city}", timeout=120)
                        if response and response.status_code == 200:
                            st.session_state.spots = response.json()
                            st.success(f"Found {len(st.session_state.spots)} spots.")
            
            with top_bar_cols[5]:
                menu_cols = st.columns(5)
                with menu_cols[0]:
                    if st.button("📖", key="view_bookings_btn", help="View My Bookings", use_container_width=True):
                        st.session_state.viewing_bookings = True
                        st.session_state.viewing_settings = False
                        st.session_state.viewing_admin = False
                        st.rerun()
                with menu_cols[1]:
                    if st.button("👑", key="view_admin_btn", help="Admin Dashboard", use_container_width=True):
                        st.session_state.viewing_admin = True
                        st.session_state.viewing_bookings = False
                        st.session_state.viewing_settings = False
                        st.rerun()
                with menu_cols[2]:
                    if st.session_state.viewing_settings:
                        if st.button("✕", help="Close Menu", use_container_width=True):
                            st.session_state.viewing_settings = False
                            st.rerun()
                    else:
                        if st.button("☰", help="Profile & Settings", use_container_width=True):
                            st.session_state.viewing_settings = True
                            st.rerun()
                with menu_cols[3]:
                    if st.button("⌖", key="recenter_btn", help="Recenter on your location", use_container_width=True):
                        st.session_state.recenter_map = True
                        st.rerun()


        map_target = st.container()

        if st.session_state.navigation_active:
            nav_cols = st.columns([3, 1])
            with nav_cols[1]:
                render_navigation_view()
            map_target = nav_cols[0]
        
        elif st.session_state.viewing_bookings:
            book_cols = st.columns([3, 1])
            with book_cols[1]:
                render_bookings_view()
            map_target = book_cols[0]

        elif st.session_state.viewing_settings:
            settings_cols = st.columns([3, 1])
            with settings_cols[1]:
                render_settings_view() # This function now handles its own sub-pages
            map_target = settings_cols[0]
        
        elif st.session_state.viewing_admin:
            admin_cols = st.columns([3, 1])
            with admin_cols[1]:
                render_admin_view()
            map_target = admin_cols[0]

        with map_target:
            if not st.session_state.get('location_set_by_user', False):
                st.warning("Please click your starting location on the map to enable route finding.")
            else:
                with st.spinner("Fetching address..."):
                    address = get_address_from_coords(st.session_state.current_lat, st.session_state.current_lng)
                    st.success(f"Start Location: {address}")

            if st.session_state.spots:
                total_spots = len(st.session_state.spots)
                occupied_spots = len([s for s in st.session_state.spots if s.get('occupied')])
                available_spots = total_spots - occupied_spots 

                if total_spots > 0:
                    # Calculate percentages
                    # available_percent = available_spots / total_spots
                    
                    # Display stats in columns
                    st.markdown(f"""
                    <div style="display: flex; gap: 20px; align-items: center; justify-content: flex-start; height: 100%; padding-bottom: 10px;">
                        <span title="Available"><span style="color: #28a745;">●</span> Available: {available_spots}</span>
                        <span title="Occupied"><span style="color: #dc3545;">●</span> Occupied: {occupied_spots}</span>
                        <span title="Total Spots"><strong>Σ</strong> Total: {total_spots}</span>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("---",)

            map_center = CITY_CENTERS.get(st.session_state.selected_city, CITY_CENTERS["melbourne"])
            m = folium.Map(location=map_center, zoom_start=14, tiles="cartodbdark_matter" if st.session_state.dark_theme else "cartodbpositron")
            from folium.plugins import Fullscreen
            Fullscreen().add_to(m)
            folium.LayerControl().add_to(m)
            
            bounds = []
            if st.session_state.path_data and not st.session_state.navigation_active:
                nearest_spot = st.session_state.path_data.get('nearest', {})
                if nearest_spot and nearest_spot.get('route'):
                    route_line = folium.PolyLine(nearest_spot['route'], color="blue", weight=5, opacity=0.8, tooltip="Route to nearest spot")
                    route_line.add_to(m)
                    bounds.extend(route_line.get_bounds())

            if st.session_state.direct_route:
                direct_line = folium.PolyLine(st.session_state.direct_route, color="green", weight=5, opacity=0.7, dash_array='10, 5', tooltip="Direct Route to Destination")
                direct_line.add_to(m)
                bounds.extend(direct_line.get_bounds())

            if st.session_state.navigation_active:
                if st.session_state.leg1_route:
                    leg1_line = folium.PolyLine(st.session_state.leg1_route, color="blue", weight=7, opacity=0.8, tooltip="Leg 1: To Parking")
                    leg1_line.add_to(m)
                    bounds.extend(leg1_line.get_bounds())
                
                if st.session_state.leg2_route:
                    leg2_line = folium.PolyLine(st.session_state.leg2_route, color="red", weight=7, opacity=0.8, tooltip="Leg 2: To Destination")
                    leg2_line.add_to(m)
                    bounds.extend(leg2_line.get_bounds())
            
            spots_to_display = []
            if st.session_state.path_data:
                nearest = st.session_state.path_data.get('nearest')
                if nearest: spots_to_display.append(nearest)
                spots_to_display.extend(st.session_state.path_data.get('alternatives', []))
            elif st.session_state.spots:
                spots_to_display = st.session_state.spots
            
            now_melbourne = datetime.now(ZoneInfo("Australia/Melbourne"))
            weekday = now_melbourne.weekday()
            hour = now_melbourne.hour

            current_fee = 2.00 # Default/fallback fee
            fee_type = "Off-Peak"
            if weekday < 5:
                if 7 <= hour < 19:
                    current_fee = 4.00
                    fee_type = "Peak"
            else:
                fee_type = "Weekend"

            for spot in spots_to_display:
                is_occupied = spot.get('occupied', False)
                color = "red" if is_occupied else "green"
                last_updated_str = spot.get('last_updated', 'N/A')
                if 'Z' in last_updated_str: last_updated_str = last_updated_str.replace('Z', '+00:00')
                try:
                    last_updated_dt = datetime.fromisoformat(last_updated_str).strftime('%d %b, %I:%M %p')
                except (ValueError, TypeError):
                    last_updated_dt = "N/A"
                
                # Only perform reverse geocoding if we have a small, filtered list of spots.
                if st.session_state.path_data:
                    address = get_address_from_coords(spot.get('lat'), spot.get('lng'))
                else:
                    address = spot.get('street', 'N/A')

                kerbside_id = spot.get('kerbsideid')
                zone_number = spot.get('zone_number')
                #  print(spot)
                #  print(kerbside_id, zone_number)
                popup_html = f"""
                <div style="font-family: sans-serif; font-size: 14px;">
                    <b>Spot ID: {spot.get('name', 'N/A')}</b><br>
                    <b>Kerbside: {kerbside_id or 'N/A'}</b><br>
                    <b>Zone: {zone_number or 'N/A'}</b><br>
                    <b>Status: {'Occupied' if is_occupied else 'Available'}</b><br>
                    <b>Address:</b> {address}<br>

                    <b>⚠️ Important Notice:
                    Please double-check the fee amount before proceeding. The fees shown here are based on publicly available notices found online and may not reflect the most current or official pricing. The price displayed at the parking location will be considered final and authoritative.
                    </b><br>
                    <i>{spot.get('status_note', 'N/A')}</i><br>
                    Last Updated: {last_updated_dt}<br>
                    <hr style="margin: 5px 0;">
                    <div class="spot-id" style="display:none;">{spot.get('name')}</div>
                    <button onclick="parent.document.getElementById('select-spot-{spot.get('name')}').click();" style="width: 100%; border: none; background-color: #007bff; color: white; padding: 8px; border-radius: 4px; cursor: pointer;">Book</button>
                </div>
                """
                folium.Marker(location=[spot['lat'], spot['lng']], popup=folium.Popup(popup_html, max_width=250), tooltip=f"ID: {spot.get('name', 'N/A')}", icon=folium.Icon(color=color, icon='car', prefix='fa')).add_to(m)

            folium.Marker(location=[st.session_state.current_lat, st.session_state.current_lng], popup="Your Current Location (Click map to move)", icon=folium.Icon(color='blue', icon='user', prefix='fa')).add_to(m)
            
            if st.session_state.dest_lat and st.session_state.dest_lng:
                folium.Marker(location=[st.session_state.dest_lat, st.session_state.dest_lng], popup="Your Destination", icon=folium.Icon(color='orange', icon='flag')).add_to(m)

            if bounds:
                m.fit_bounds(bounds, padding=(50, 50))

            map_data = st_folium(m, width='100%', height=700, returned_objects=['last_object_clicked', 'last_clicked'])

            if map_data and map_data.get("last_clicked") and not st.session_state.path_data:
                st.session_state.current_lat = map_data['last_clicked']['lat']
                st.session_state.current_lng = map_data['last_clicked']['lng']
                st.session_state.location_set_by_user = True
                st.rerun()

            if map_data and map_data.get("last_object_clicked_popup"):
                popup_content = map_data['last_object_clicked_popup']
                if popup_content:
                    try:
                        spot_id_search = '<div class="spot-id" style="display:none;">'
                        if spot_id_search in popup_content:
                            spot_id = popup_content.split(spot_id_search)[1].split('</div>')[0]
                            selected = next((s for s in st.session_state.spots if str(s.get('name')) == str(spot_id)), None)
                            if selected and (st.session_state.selected_spot is None or st.session_state.selected_spot.get('name') != selected.get('name')):
                                st.session_state.selected_spot = selected
                                st.rerun()
                    except (IndexError, StopIteration):
                        pass

        if st.session_state.spots:
            unique_spots = []
            seen_names = set()
            for spot in st.session_state.spots:
                if spot.get('name') not in seen_names:
                    unique_spots.append(spot)
                    seen_names.add(spot.get('name'))

        if st.session_state.selected_spot:
            st.markdown("---")
            spot_details = st.session_state.selected_spot
            st.subheader(f"Details for: {spot_details.get('name')}")
            
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Status", "Occupied" if spot_details.get('occupied') else "Available")
            with col_b:
                if spot_details.get('current_fee') is not None:
                    st.metric(f"Current {spot_details.get('fee_type', '')} Rate", f"${spot_details['current_fee']:.2f}/hr")
                else:
                    st.metric("Fee", f"${spot_details.get('fee', 0.0):.2f}/hr")
            with col_c:
                st.metric("Area Type", spot_details.get('area_type', 'N/A'))

            st.write(f"**Location:** {spot_details.get('street', 'N/A')}")
            st.caption("""
                Disclaimer: Parking rates are provided for informational purposes only and are based on public data. Rates are subject to change and may not be guaranteed. Please verify all pricing and restrictions on the official parking meters or signage before parking.
            """)
            st.info(f"**Note:** {spot_details.get('status_note', 'No additional information.')}")
            
            last_updated_str = spot_details.get('last_updated')
            if last_updated_str:
                try:
                    if 'Z' in last_updated_str: last_updated_str = last_updated_str.replace('Z', '+00:00')
                    dt_object = datetime.fromisoformat(last_updated_str)
                    st.caption(f"Last updated: {dt_object.strftime('%d %b %Y, %I:%M %p %Z')}")
                except (ValueError, TypeError):
                    st.caption(f"Last updated: {last_updated_str}")

            button_cols = st.columns(4)
            with button_cols[0]:
                if st.session_state.dest_lat:
                    if st.button("Start Navigation", disabled=not st.session_state.location_set_by_user, use_container_width=True, key="start_nav_btn"):
                        with st.spinner("Calculating full journey..."):
                            start_loc = (st.session_state.current_lat, st.session_state.current_lng)
                            parking_loc = (spot_details['lat'], spot_details['lng'])
                            dest_loc = (st.session_state.dest_lat, st.session_state.dest_lng)
                            
                            st.session_state.leg1_route = None
                            st.session_state.leg2_route = None
                            st.session_state.leg2_steps = None
                            st.session_state.leg2_summary = None

                            params1 = {"start_lat": start_loc[0], "start_lon": start_loc[1], "end_lat": parking_loc[0], "end_lon": parking_loc[1], "steps": "false"}
                            response1 = api_request("GET", "/api/route", params=params1)
                            if response1 and response1.status_code == 200:
                                leg1_data = response1.json()
                                st.session_state.leg1_route = leg1_data.get('geometry')

                            params2 = {"start_lat": parking_loc[0], "start_lon": parking_loc[1], "end_lat": dest_loc[0], "end_lon": dest_loc[1], "steps": "true"}
                            response2 = api_request("GET", "/api/route", params=params2)
                            if response2 and response2.status_code == 200:
                                leg2_data = response2.json()
                                st.session_state.leg2_route = leg2_data.get('geometry')
                                st.session_state.leg2_steps = leg2_data.get('steps')
                                st.session_state.leg2_summary = leg2_data.get('summary')
                            
                            if st.session_state.leg1_route or st.session_state.leg2_route:
                                st.session_state.navigation_active = True
                                st.rerun()
                            else:
                                st.error("Could not calculate routes for this journey. Please check your connection and try again.")

            with button_cols[1]:
                if st.session_state.selected_spot and not st.session_state.selected_spot.get('occupied'):
                    if not st.session_state.stripe_pk:
                        pk_response = api_request("GET", "/config")
                        if pk_response and pk_response.status_code == 200 and pk_response.json().get("publishableKey"):
                            st.session_state.stripe_pk = pk_response.json().get("publishableKey")

                    if st.session_state.stripe_pk:
                        booking_fee_cents = int(spot_details.get('fee', 2.5) * 100)
                        payment_url = f"http://localhost:8000/payment.html?spot_id={spot_details.get('name')}&amount={booking_fee_cents}&token={st.session_state.token}&pk={st.session_state.stripe_pk}"
                        st.link_button(f"Pay ${spot_details.get('fee', 2.5):.2f} and Book", url=payment_url, use_container_width=True, type="primary")
                    else:
                        st.error("Stripe is not configured. Please add keys to the .env file.")

            with button_cols[2]:
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                if st.button("❤️ Add to Favorites", use_container_width=True):
                    fav_resp = api_request("POST", f"/api/favorites/{spot_details.get('name')}", headers=headers, json={"nickname": spot_details.get('street')})
                    if fav_resp and fav_resp.status_code == 200:
                        st.success(f"Added Spot {spot_details.get('name')} to your favorites!")
                    elif fav_resp and fav_resp.status_code == 409:
                        st.warning("This spot is already in your favorites.")
                    time.sleep(1.5)

            with button_cols[3]:
                if st.button("Deselect Spot", key="deselect_spot_btn", use_container_width=True):
                    st.session_state.selected_spot = None
                    st.rerun()

        google_maps_css = """
            <style>
                /* --- General App Styling --- */
                #MainMenu, footer, header { visibility: hidden; }
                .stApp { margin-top: 0; }

                /* --- Android-style Buttons --- */
                div[data-testid="stButton"] > button {
                    border-radius: 20px; /* Fully rounded corners */
                    padding: 10px 20px;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                    transition: all 0.2s ease-in-out;
                    border: none;
                    background-color: #4285F4; /* Google Blue */
                    color: white;
                }
                /* Hover and active states for a tactile feel */
                div[data-testid="stButton"] > button:hover:not(:disabled) {
                    box-shadow: 0 4px 8px rgba(0,0,0,0.25);
                    transform: translateY(-1px);
                    background-color: #5a95f5;
                }
                div[data-testid="stButton"] > button:active:not(:disabled) {
                    transform: translateY(1px);
                    box-shadow: 0 1px 2px rgba(0,0,0,0.2);
                }
                /* Style for secondary/less important buttons */
                div[data-testid="stButton"] > button[kind="secondary"] {
                    background-color: #f1f3f4; /* Light gray */
                    color: #202124; /* Dark gray text */
                }
                div[data-testid="stButton"] > button[kind="secondary"]:hover:not(:disabled) {
                    background-color: #e8eaed;
                }
                /* Disabled button style */
                div[data-testid="stButton"] > button:disabled {
                    background-color: #f1f3f4;
                    color: #bdc1c6;
                    cursor: not-allowed;
                }
            </style>
        """
        
        st.markdown(google_maps_css, unsafe_allow_html=True)
        st.markdown("""
            <style>
            .leaflet-marker-icon.green, .leaflet-marker-icon.red { animation: fadeIn 0.5s ease-in-out, pulse 2s infinite 1s; }
            .leaflet-polyline { animation: fadeIn 2s ease-in-out; }
            @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
            @keyframes fadeIn { 0% { opacity: 0; } 100% { opacity: 1; } }
            </style>
        """, unsafe_allow_html=True)
@backend_app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serves the main HTML frontend."""
    try:
        with open(os.path.join(BASE_DIR, "parking.html"), "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="parking.html not found. Please create it.")

# ==============================================================================
# --- 3. APP RUNNER ---
    uvicorn.run(backend_app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    # Check if the backend is already running (e.g., in a Streamlit rerun)
    try:
        requests.get("http://localhost:8000/docs", timeout=1)
        logger.info("Backend is already running.")
    except requests.ConnectionError:
        logger.info("Backend not found, starting it in a new thread.")
        backend_thread = threading.Thread(target=run_backend, daemon=True)
        backend_thread.start()
        time.sleep(2) # Give the backend a moment to start

    # Run the Streamlit frontend
    run_frontend()
    # This will run the FastAPI backend directly.
    # To see the frontend, open your browser to http://localhost:8000
    logger.info("Starting FastAPI server...")
    logger.info("Access the application at http://localhost:8000")
    run_backend()