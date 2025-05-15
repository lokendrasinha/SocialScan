import streamlit as st
import json
import httpx
from PIL import Image
from io import BytesIO
import time
from pymongo import MongoClient
import os
from datetime import datetime
import pandas as pd
import traceback
from groq import Groq

# ===================== PAGE CONFIG =====================
st.set_page_config(
    page_title="SocialScan",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===================== MONGODB CONNECTION =====================
try:
    MONGO_URI = "mongodb://localhost:27017/"
    client_mongo = MongoClient(MONGO_URI)
    db = client_mongo["instagram_user"]
    collection = db["users"]
except Exception as e:
    st.error(f"Failed to connect to MongoDB: {e}")
    collection = None

# ===================== HTTP CLIENT SETUP =====================
client = httpx.Client(
    headers={
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "/",
    },
    cookies={
        "sessionid": "REPLACE_WITH_YOUR_SESSION_ID"
    }
)

# ===================== GROQ CLIENT SETUP =====================
def get_groq_client():
    """Initialize and return the Groq client with comprehensive error handling."""
    try:
        # Try multiple methods to get the API key
        api_key = (
            os.getenv("GROQ_API_KEY") or                  # 1. Check environment variables
            st.secrets.get("GROQ_API_KEY") or             # 2. Check Streamlit secrets
            st.session_state.get("temp_groq_key")         # 3. Check for temporary session key
        )

        # If no key found, guide user to configure it
        if not api_key:
            with st.expander("🔑 Groq API Key Configuration", expanded=True):
                st.warning("Groq API key not found. Please configure it to enable AI features.")
                
                # Option 1: Direct input (temporary for current session)
                temp_key = st.text_input(
                    "Enter your Groq API key (temporary for this session):",
                    type="password",
                    help="This won't be saved after you close the app."
                )
                
                if temp_key:
                    st.session_state.temp_groq_key = temp_key
                    st.rerun()  # Refresh to use the new key
                
                # Option 2: Instructions for permanent setup
                st.markdown("""
                *For permanent setup, choose one method:*
                
                1️⃣ *Environment Variable*  
                bash
                export GROQ_API_KEY="your-api-key-here"
                
                
                2️⃣ *Secrets File*  
                Create .streamlit/secrets.toml with:
                toml
                GROQ_API_KEY = "your-api-key-here"
                
                """)
            return None

        # Initialize client with the found key
        return Groq(api_key=api_key)

    except FileNotFoundError:
        # Handle missing secrets.toml specifically
        st.info(
            "Secrets file not found. Using session-based key or environment variables.",
            icon="ℹ"
        )
        return None
    except Exception as e:
        st.error(f"Error initializing Groq client: {str(e)}")
        return None

# ===================== HELPER FUNCTIONS =====================
def get_saved_usernames():
    """Get list of saved usernames with their scrape dates."""
    saved_users = []
    
    if collection is None:
        st.error("MongoDB connection not available")
        return saved_users
    
    try:
        for user in collection.find({}, {"user_info.Username": 1, "timestamp": 1}):
            if "user_info" in user and "Username" in user["user_info"]:
                username = user["user_info"]["Username"]
                date = datetime.fromtimestamp(user.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M")
                saved_users.append((username, date))
    except Exception as e:
        st.error(f"Error fetching saved usernames: {e}")
    
    return saved_users

def load_saved_user(username):
    """Load saved user data from MongoDB."""
    if collection is None:
        st.error("MongoDB connection not available")
        return {"Error": "Database connection error"}, []
    
    try:
        user_data = collection.find_one({"user_info.Username": username})
        if user_data:
            return user_data.get("user_info", {}), user_data.get("images", [])
        else:
            return {"Error": "User not found"}, []
    except Exception as e:
        st.error(f"Error loading user data: {e}")
        return {"Error": str(e)}, []

def export_user_data_to_csv(username):
    """Export user data to CSV file."""
    if collection is None:
        st.error("MongoDB connection not available")
        return False, "Database connection error"
    
    try:
        user_data = collection.find_one({"user_info.Username": username})
        if not user_data:
            return False, f"User '{username}' not found in database."
        
        # Create filename with timestamp
        filename = f"{username}export{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Extract user info
        user_info = user_data.get("user_info", {})
        
        # Create DataFrame from user info
        data = {key: [value] for key, value in user_info.items()}
        
        # Add image data
        images = user_data.get("images", [])
        for i, image in enumerate(images):
            for key, value in image.items():
                data[f"image_{i}_{key}"] = [value]
        
        # Create DataFrame and export
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        
        return True, filename
    except Exception as e:
        return False, f"Error exporting data: {e}"

# ===================== SCRAPER FUNCTION =====================
def scrape_user(username: str):
    """
    Scrape Instagram user profile and posts.
    
    Args:
        username: Instagram username to scrape
        
    Returns:
        tuple: (user_info dict, images list)
    """
    if not username:
        return {"Error": "Username is required"}, []
        
    try:
        # Make API request to Instagram
        response = client.get(f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}")

        # Check response status
        if response.status_code != 200:
            return {"Error": f"Failed to retrieve data. Status code: {response.status_code}"}, []

        # Parse response data
        data = response.json()
        
        # Check for valid user data
        if "data" not in data or "user" not in data.get("data", {}):
            return {"Error": "Invalid response format from Instagram API"}, []
            
        user_info = data.get("data", {}).get("user", {})
        if not user_info:
            return {"Error": "User not found or unable to retrieve data"}, []

        # Extract user profile information
        user = {
            "Username": user_info.get("username", "N/A"),
            "Full Name": user_info.get("full_name", "N/A"),
            "ID": user_info.get("id", "N/A"),
            "Category": user_info.get("category_name", "N/A"),
            "Business Category": user_info.get("business_category_name", "N/A"),
            "Phone": user_info.get("business_phone_number", "N/A"),
            "Email": user_info.get("business_email", "N/A"),
            "Biography": user_info.get("biography", "N/A"),
            "Bio Links": [],  # Initialize as empty list to avoid potential errors
            "Homepage": user_info.get("external_url", "N/A"),
            "Followers": "N/A",
            "Following": "N/A",
            "Facebook ID": user_info.get("fbid", "N/A"),
            "Is Private": user_info.get("is_private", False),
            "Is Verified": user_info.get("is_verified", False),
            "Profile Image": user_info.get("profile_pic_url_hd", "N/A"),
            "Image Count": 0,
        }
        
        # Safely extract bio links
        if "bio_links" in user_info and isinstance(user_info["bio_links"], list):
            user["Bio Links"] = [link.get("url") for link in user_info["bio_links"] if isinstance(link, dict) and "url" in link]
        
        # Safely extract follower and following counts
        if "edge_followed_by" in user_info and isinstance(user_info["edge_followed_by"], dict) and "count" in user_info["edge_followed_by"]:
            user["Followers"] = f"{user_info['edge_followed_by']['count']:,}"
        
        if "edge_follow" in user_info and isinstance(user_info["edge_follow"], dict) and "count" in user_info["edge_follow"]:
            user["Following"] = f"{user_info['edge_follow']['count']:,}"
        
        # Safely extract image count
        if "edge_owner_to_timeline_media" in user_info and isinstance(user_info["edge_owner_to_timeline_media"], dict):
            user["Image Count"] = user_info["edge_owner_to_timeline_media"].get("count", 0)
        
        # Extract user's media/posts
        image_info = []
        
        # Check if media data exists and is in expected format
        if "edge_owner_to_timeline_media" in user_info and isinstance(user_info["edge_owner_to_timeline_media"], dict):
            image_edges = user_info["edge_owner_to_timeline_media"].get("edges", [])
            
            for edge in image_edges:
                if not isinstance(edge, dict) or "node" not in edge:
                    continue  # Skip invalid entries
                
                node = edge["node"]
                post_id = node.get("id", "N/A")
                
                # Extract comments if available
                comments = []
                if isinstance(node.get("edge_media_to_comment"), dict) and node["edge_media_to_comment"].get("count", 0) > 0:
                    try:
                        comment_req = client.get(f"https://i.instagram.com/api/v1/media/{post_id}/comments/")
                        if comment_req.status_code == 200:
                            comment_data = comment_req.json()
                            if "comments" in comment_data and isinstance(comment_data["comments"], list):
                                comments = [c.get("text", "") for c in comment_data["comments"] if isinstance(c, dict)]
                    except Exception as e:
                        st.warning(f"Could not fetch comments for post {post_id}: {e}")
                
                # Extract caption safely
                caption = "N/A"
                if ("edge_media_to_caption" in node and 
                    isinstance(node["edge_media_to_caption"], dict) and 
                    "edges" in node["edge_media_to_caption"] and 
                    len(node["edge_media_to_caption"]["edges"]) > 0):
                    
                    caption_node = node["edge_media_to_caption"]["edges"][0].get("node", {})
                    caption = caption_node.get("text", "N/A") if isinstance(caption_node, dict) else "N/A"
                
                # Extract likes count safely
                likes_count = 0
                if "edge_liked_by" in node and isinstance(node["edge_liked_by"], dict):
                    likes_count = node["edge_liked_by"].get("count", 0)
                
                # Add post information to collection
                image_info.append({
                    "ID": post_id,
                    "Source": node.get("display_url", "N/A"),
                    "Likes": likes_count,
                    "Caption": caption,
                    "Comments": comments
                })

        # Return collected data
        return user, image_info

    except Exception as e:
        error_details = traceback.format_exc()
        st.error(f"Exception in scrape_user: {error_details}")
        return {"Error": f"An error occurred: {str(e)}"}, []

# ===================== SAVE TO MONGO =====================
def save_to_mongo(user_info, images):
    """Save scraped user data to MongoDB."""
    if collection is None:
        st.error("MongoDB connection not available")
        return False
    
    # Check for errors in user_info
    if isinstance(user_info, str) or "Error" in user_info:
        error_msg = user_info if isinstance(user_info, str) else user_info.get("Error", "Unknown error")
        st.error(error_msg)
        return False

    try:
        # Prepare data for MongoDB
        user_data = {
            "user_info": user_info,
            "images": images,
            "timestamp": time.time(),
        }

        # Check if user already exists in database
        username = user_info.get("Username")
        if not username or username == "N/A":
            st.error("Invalid username in user data")
            return False
            
        existing = collection.find_one({"user_info.Username": username})
        
        # Update or insert data
        if existing:
            collection.update_one({"user_info.Username": username}, {"$set": user_data})
            st.success(f"User data for '{username}' updated in MongoDB.")
        else:
            collection.insert_one(user_data)
            st.success(f"Data for '{username}' saved to MongoDB.")
        return True
    except Exception as e:
        st.error(f"Failed to save to MongoDB: {e}")
        return False

# ===================== FETCH IMAGE =====================
def fetch_image(url):
    """Fetch an image from URL and return PIL Image object."""
    if not url or url == "N/A":
        return create_placeholder_image()
        
    try:
        res = client.get(url, timeout=5)
        if res.status_code == 200:
            return Image.open(BytesIO(res.content))
        else:
            st.warning(f"Failed to load image from {url}: Status code {res.status_code}")
            return create_placeholder_image()
    except Exception as e:
        st.warning(f"Error loading image: {e}")
        return create_placeholder_image()

def create_placeholder_image():
    """Create a placeholder image when actual image cannot be loaded."""
    try:
        # Try to load placeholder image file if it exists
        if os.path.exists("placeholder.png"):
            return Image.open("placeholder.png")
        else:
            # Create a simple gray placeholder with text
            img = Image.new('RGB', (300, 300), color='gray')
            return img
    except Exception:
        # Last resort fallback
        return Image.new('RGB', (100, 100), color='gray')

# ===================== DISPLAY FUNCTIONS =====================
def display_user_info(user_info):
    """Display user profile information in the UI."""
    st.subheader("📋 User Information")
    
    # Check for errors
    if not user_info:
        st.error("No user information available")
        return
        
    if isinstance(user_info, str):
        st.error(user_info)
        return
        
    if "Error" in user_info:
        st.error(user_info["Error"])
        return
    
    # Display user profile data
    try:
        for key, value in user_info.items():
            # Skip displaying bio links as it will be shown separately
            if key == "Bio Links":
                continue
                
            # Format display of different types of values
            if isinstance(value, list):
                st.write(f"{key}:** {', '.join(str(v) for v in value)}")
            elif isinstance(value, bool):
                st.write(f"{key}:** {'Yes' if value else 'No'}")
            else:
                st.write(f"{key}:** {value}")
        
        # Display bio links as clickable links
        if "Bio Links" in user_info and user_info["Bio Links"]:
            st.write("*Bio Links:*")
            for link in user_info["Bio Links"]:
                st.markdown(f"- [{link}]({link})")

        # Display profile image
        if "Profile Image" in user_info and user_info["Profile Image"] and user_info["Profile Image"] != "N/A":
            st.subheader("Profile Picture")
            img = fetch_image(user_info["Profile Image"])
            st.image(img, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error displaying user information: {e}")
        st.write("Raw user data:", user_info)

def display_media_grid(media_list, columns=3):
    """Display media posts in a grid layout."""
    st.subheader("🖼 Latest Posts")
    
    # Check for empty media list
    if not media_list:
        st.warning("No media found.")
        return
    
    try:
        # Create rows for the grid view
        media_rows = [media_list[i:i+columns] for i in range(0, len(media_list), columns)]
        
        # Display each row
        for row in media_rows:
            # Create columns for this row
            cols = st.columns(columns)
            
            # Fill each column with content
            for idx, media in enumerate(row):
                if idx < len(cols):  # Ensure we stay within bounds
                    with cols[idx]:
                        try:
                            # Only fetch and display image if Source exists and is valid
                            if "Source" in media and media["Source"] and media["Source"] != "N/A":
                                img = fetch_image(media["Source"])
                                st.image(img, use_container_width=True)
                            else:
                                st.image(create_placeholder_image(), use_container_width=True)
                                st.caption("Image not available")
                            
                            # Display post details
                            likes = media.get("Likes", 0)
                            st.write(f"❤ {likes:,} Likes")
                            
                            post_id = media.get("ID", "N/A")
                            st.caption(f"🆔 Post ID: {post_id}")
                            
                            # Show caption in expander
                            caption = media.get("Caption", "No caption")
                            with st.expander("📄 Caption"):
                                st.write(caption)
                            
                            # Show comments if available
                            comments = media.get("Comments", [])
                            if comments:
                                with st.expander(f"💬 Comments ({len(comments)})"):
                                    for comment in comments:
                                        st.markdown(f"- {comment}")
                                        
                        except Exception as e:
                            st.error(f"Error displaying media item: {e}")
                
    except Exception as e:
        st.error(f"Error displaying media grid: {e}")
        st.write("Raw media data:", media_list[:1])  # Show just first item to avoid clutter

# ===================== ANALYSIS FUNCTIONS =====================
def analyze_behavior(username):
    """Comprehensive analysis of Instagram user behavior using MongoDB data."""
    if collection is None:
        st.error("MongoDB connection not available")
        return None
    
    try:
        # Load user data from MongoDB
        user_data = collection.find_one({"user_info.Username": username})
        if not user_data:
            st.error(f"No data found for user: {username}")
            return None

        # Extract and structure profile information
        user_info = user_data.get("user_info", {})
        profile_data = {
            'username': username,
            'full_name': user_info.get("Full Name", "N/A"),
            'category': user_info.get("Category", user_info.get("category_name", "Unknown")),
            'followers': user_info.get("Followers", "0"),
            'following': user_info.get("Following", "0"),
            'biography': user_info.get("Biography", ""),
            'related_profiles': user_info.get("Related Profiles", "None"),
            'is_verified': user_info.get("Is Verified", False),
            'profile_image': user_info.get("Profile Image", "N/A"),
            'external_url': user_info.get("Homepage", "N/A")
        }

        # Process engagement data
        engagement_data = []
        total_likes = 0
        valid_posts = 0

        for image in user_data.get("images", []):
            likes = image.get("Likes", 0)
            caption = image.get("Caption", "")
            
            # Convert likes to integer if string
            if isinstance(likes, str):
                likes = int(likes.replace(',', '')) if likes.replace(',', '').isdigit() else 0
            
            if likes > 0 and caption:
                engagement_data.append({
                    'likes': likes,
                    'caption': caption,
                    'comments': image.get("Comments", []),
                    'post_id': image.get("ID", "N/A"),
                    'image_url': image.get("Source", "N/A")
                })
                total_likes += likes
                valid_posts += 1

        if not engagement_data:
            st.warning("No valid engagement data found for this user")
            return None
        
        # Calculate metrics
        avg_likes = total_likes / valid_posts if valid_posts > 0 else 0
        sorted_posts = sorted(engagement_data, key=lambda x: x['likes'], reverse=True)

        return {
            'profile': profile_data,
            'engagement': {
                'avg_likes': avg_likes,
                'total_posts': valid_posts,
                'top_posts': sorted_posts[:5],
                'all_posts': sorted_posts,
                'total_likes': total_likes
            }
        }

    except Exception as e:
        st.error(f"Error in behavior analysis: {e}")
        st.error(traceback.format_exc())
        return None

def format_analysis_response(analysis_type, profile_data, engagement_data, query_response):
    """Format the AI response with professional templates."""
    base_template = f"""
    ## {analysis_type} Analysis for @{profile_data['username']}
    
    *Profile Overview*
    - 🏷 *Category:* {profile_data['category']}
    - 👥 *Followers:* {profile_data['followers']}
    - 🔄 *Following:* {profile_data['following']}
    - ✅ *Verified:* {'Yes' if profile_data['is_verified'] else 'No'}
    
    *Engagement Metrics*
    - 🔥 *Average Likes:* {engagement_data['avg_likes']:,.0f}
    - 📊 *Posts Analyzed:* {engagement_data['total_posts']}
    - ❤ *Total Likes:* {engagement_data['total_likes']:,.0f}
    """
    
    type_specific = {
        "Content Strategy": f"""
        *Content Strategy Recommendations*
        {query_response}
        
        *Action Items*
        1. Content Theme Optimization
        2. Posting Frequency Adjustment
        3. Caption Strategy Enhancement
        """,
        
        "Engagement Patterns": f"""
        *Engagement Insights*
        {query_response}
        
        *Top Performing Posts*
        {chr(10).join(f"- {post['likes']:,.0f} likes: {post['caption'][:80]}..." for post in engagement_data['top_posts'])}
        """,
        
        "Audience Insights": f"""
        *Audience Demographics*
        {query_response}
        
        *Psychographic Profile*
        1. Interests:
        2. Behaviors:
        3. Preferences:
        """,
        
        "Competitive Analysis": f"""
        *Competitive Landscape*
        {query_response}
        
        *Competitive Advantages*
        1. Strength:
        2. Opportunity:
        3. Threat:
        """
    }
    
    if analysis_type in type_specific:
        return base_template + type_specific[analysis_type]
    else:
        return f"""
        ## Custom Analysis Report
        
        *Query Response*
        {query_response}
        
        *Supporting Data*
        - Average Engagement: {engagement_data['avg_likes']:,.0f} likes/post
        - Top Post: {engagement_data['top_posts'][0]['likes']:,.0f} likes
        - Bio: {profile_data['biography'][:150]}...
        """

def generate_prompt(username, analysis_type, custom_query=""):
    """Generate tailored prompts for Groq's LLaMA model."""
    behavior = analyze_behavior(username)
    if not behavior:
        return "No data available for analysis."

    # Base context
    context = f"""
    Analyze Instagram account @{username} with:
    - {behavior['profile']['followers']} followers
    - Category: {behavior['profile']['category']}
    - Avg. likes: {behavior['engagement']['avg_likes']:,.0f}
    - Verified: {behavior['profile']['is_verified']}
    """

    # Type-specific prompts
    prompts = {
        "Content Strategy": f"""
        {context}
        Provide detailed content strategy recommendations focusing on:
        1. Content themes that resonate with current audience
        2. Optimal posting frequency based on engagement patterns
        3. Caption strategies that drive engagement
        4. Visual content improvements
        """,
        
        "Engagement Patterns": f"""
        {context}
        Analyze engagement patterns considering:
        1. Best performing content types
        2. Ideal posting times
        3. Engagement rate trends
        4. Follower growth correlation
        """,
        
        "Audience Insights": f"""
        {context}
        Deduce audience characteristics including:
        1. Demographic estimates (age, gender, location)
        2. Psychographic traits (interests, behaviors)
        3. Content preferences
        4. Potential audience growth segments
        """,
        
        "Competitive Analysis": f"""
        {context}
        Perform competitive analysis covering:
        1. Relative engagement rates in category
        2. Content differentiation opportunities
        3. Unique value proposition development
        4. Growth strategy recommendations
        """
    }

    prompt = prompts.get(analysis_type, f"""
    {context}
    Provide detailed analysis responding to this specific query:
    {custom_query}
    """)

    # Initialize Groq client
    groq_client = get_groq_client()
    if not groq_client:
        return "AI analysis unavailable - please configure API key"

    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a professional social media analyst."},
                {"role": "user", "content": prompt}
            ],
            model="llama3-70b-8192",
            temperature=0.7,
            max_tokens=1024,
            top_p=1
        )
        
        return format_analysis_response(
            analysis_type,
            behavior['profile'],
            behavior['engagement'],
            response.choices[0].message.content
        )
        
    except Exception as e:
        return f"❌ Analysis failed: {str(e)}"

# ===================== BATCH SCRAPE FUNCTION =====================
def batch_scrape_usernames(usernames_input, rate_limit):
    """
    Batch scrape Instagram profiles based on a list of usernames.
    Args:
        usernames_input (str): Multiline string of usernames.
        rate_limit (int): Delay between requests in seconds.
    Returns:
        tuple: (successful, failed) lists of usernames and their statuses.
    """
    # Parse usernames
    usernames = [u.strip() for u in usernames_input.split("\n") if u.strip()]
    
    if not usernames:
        st.error("No valid usernames found.")
        return [], []

    # Initialize progress bar and status
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Results containers
    successful = []
    failed = []

    # Process each username
    for i, username in enumerate(usernames):
        status_text.text(f"Processing {i+1}/{len(usernames)}: {username}...")
        
        try:
            # Scrape user data
            user_info, images = scrape_user(username)
            
            # Save to MongoDB if successful
            if not isinstance(user_info, str) and "Error" not in user_info and save_to_mongo(user_info, images):
                successful.append(username)
            else:
                error_msg = user_info if isinstance(user_info, str) else user_info.get("Error", "Unknown error")
                failed.append((username, error_msg))
        except Exception as e:
            failed.append((username, str(e)))
        
        # Update progress
        progress_bar.progress((i + 1) / len(usernames))
        
        # Sleep to avoid rate limiting
        time.sleep(rate_limit)

    return successful, failed

# ===================== STREAMLIT APP =====================
def main():
    st.title("📊 SocialScan")
    st.markdown("### Advanced Instagram Analytics Platform")
    
    # Navigation sidebar
    st.sidebar.title("Modules")
    app_mode = st.sidebar.radio(
        "Select Module:",
        ["Profile Scraper", "Behavioural Analysis"],
        label_visibility="collapsed"
    )
    
    # Profile Scraper Module
    if app_mode == "Profile Scraper":
        st.header("Instagram Profile Scraper")
        scraper_option = st.radio(
            "Scraping Mode:",
            ["Single Profile", "Batch Scrape", "View Saved"],
            horizontal=True
        )
        
        if scraper_option == "Single Profile":
            st.subheader("Scrape Single Profile")
            username = st.text_input("Enter Instagram username:")
            if st.button("Scrape Now"):
                if username:
                    with st.spinner(f"Scraping @{username}..."):
                        user_info, images = scrape_user(username)
                        if "Error" in user_info:
                            st.error(user_info["Error"])
                        else:
                            save_to_mongo(user_info, images)
                            display_user_info(user_info)
                            display_media_grid(images)
                else:
                    st.warning("Please enter a username")
        
        elif scraper_option == "Batch Scrape":
            st.subheader("Batch Scrape Profiles")
            usernames = st.text_area("Enter usernames (one per line):")
            rate_limit = st.slider("Delay between requests (seconds):", 1, 10, 3)
            if st.button("Start Batch Scrape"):
                if usernames:
                    successful, failed = batch_scrape_usernames(usernames, rate_limit)
                    st.success(f"Completed: {len(successful)} successful, {len(failed)} failed")
                    if failed:
                        with st.expander("Failed Scrapes"):
                            for username, error in failed:
                                st.error(f"{username}: {error}")
                else:
                    st.warning("Please enter at least one username")
        
        elif scraper_option == "View Saved":
            st.subheader("View Saved Profiles")
            saved_users = get_saved_usernames()
            if not saved_users:
                st.warning("No saved profiles found")
            else:
                selected = st.selectbox(
                    "Select profile:",
                    [f"{u[0]} (scraped {u[1]})" for u in saved_users]
                )
                if selected:
                    username = selected.split(" (scraped")[0]
                    if st.button("Load Profile"):
                        user_info, images = load_saved_user(username)
                        display_user_info(user_info)
                        display_media_grid(images)
                    if st.button("Export to CSV"):
                        success, filename = export_user_data_to_csv(username)
                        if success:
                            with open(filename, "rb") as f:
                                st.download_button(
                                    "Download CSV",
                                    f,
                                    file_name=filename,
                                    mime="text/csv"
                                )
    
    # AI Analysis Module
    elif app_mode == "Behavioural Analysis":
        st.header("AI-Powered Profile Analysis")
        
        if collection is None:
            st.error("Database connection unavailable")
            return
            
        # Get available usernames
        try:
            usernames = [user["user_info"]["Username"] for user in collection.find(
                {}, {"user_info.Username": 1}) if "user_info" in user]
            
            if not usernames:
                st.warning("No profiles found. Please scrape data first.")
                return
                
        except Exception as e:
            st.error(f"Error loading profiles: {e}")
            return
        
        # Analysis configuration
        col1, col2 = st.columns([3, 2])
        with col1:
            selected_user = st.selectbox("Select Profile", usernames)
        with col2:
            analysis_type = st.selectbox(
                "Analysis Type",
                ["Content Strategy", "Engagement Patterns", 
                 "Audience Insights", "Competitive Analysis", "Custom Query"]
            )
        
        # Custom query input
        custom_query = ""
        if analysis_type == "Custom Query":
            custom_query = st.text_area(
                "Your Analysis Query:",
                placeholder="What specific insights would you like?",
                height=100
            )
        
        if st.button("Generate Analysis", type="primary"):
            with st.status("Analyzing profile...", expanded=True) as status:
                try:
                    # Show metrics first
                    st.write("📊 Loading profile metrics...")
                    behavior = analyze_behavior(selected_user)
                    
                    if not behavior:
                        st.error("Analysis failed")
                        return
                    
                    # Display quick stats
                    metric_cols = st.columns(4)
                    metric_cols[0].metric("Followers", behavior['profile']['followers'])
                    metric_cols[1].metric("Following", behavior['profile']['following'])
                    metric_cols[2].metric("Avg Likes", f"{behavior['engagement']['avg_likes']:,.0f}")
                    metric_cols[3].metric("Posts", behavior['engagement']['total_posts'])
                    
                    # Generate AI analysis
                    st.write("🧠 Processing AI insights...")
                    analysis_result = generate_prompt(
                        selected_user, 
                        analysis_type,
                        custom_query
                    )
                    
                    status.update(label="Analysis Complete", state="complete")
                    
                    # Display results
                    st.markdown("---")
                    st.markdown(analysis_result)
                    
                    # Download option
                    st.download_button(
                        "📥 Download Report",
                        data=analysis_result,
                        file_name=f"{selected_user}{analysis_type.replace(' ', '')}_report.txt",
                        mime="text/plain"
                    )
                    
                except Exception as e:
                    status.update(label="Analysis Failed", state="error")
                    st.error(f"Error during analysis: {e}")
                    st.error(traceback.format_exc())

if __name__ == "__main__":
    main()