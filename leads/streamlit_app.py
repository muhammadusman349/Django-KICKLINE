"""
Kickline Sports Leads - Streamlit Frontend with Manual Selection
"""

import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

# API Configuration
API_BASE_URL = "http://127.0.0.1:8000/api/leads"

# Configure page
st.set_page_config(
    page_title="Kickline Sports Lead Scraper",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'scraping_tasks' not in st.session_state:
    st.session_state.scraping_tasks = {}


def make_api_request(method, endpoint, **kwargs):
    """Make API request with error handling"""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=30, **kwargs)
        elif method == "POST":
            response = requests.post(url, timeout=60, **kwargs)
        else:
            response = requests.request(method, url, timeout=10, **kwargs)
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to Django API. Start server with: `python manage.py runserver`")
        return None
    except requests.exceptions.Timeout:
        st.warning("⏱️ Request timed out. Scraping may still be processing.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ API Error: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return None


# ============================================================================
# MAIN APP - Manual Selection Workflow
# ============================================================================

def main():
    st.title("⚽ Kickline Sports Lead Scraper")
    st.caption("Search for sports companies, then selectively scrape emails, phone numbers, and social media links")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", [
        "🔍 Step 1: Search Companies",
        "✅ Step 2: Select & Scrape",
        "📋 View Leads",
        "🔄 Check Tasks"
    ])
    
    if page == "🔍 Step 1: Search Companies":
        render_search_page()
    elif page == "✅ Step 2: Select & Scrape":
        render_select_scrape_page()
    elif page == "📋 View Leads":
        render_leads_page()
    elif page == "🔄 Check Tasks":
        render_tasks_page()


def render_search_page():
    """Step 1: Search for companies (NO scraping yet)"""
    st.header("🔍 Step 1: Search for Companies")
    st.info("Search finds sports companies but does NOT scrape them yet. You'll select which ones to scrape in the next step. You can also scrape ALL companies at once using 'Run All Tasks'.")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input(
            "Search Query",
            value="football sports manufacturer germany",
            placeholder="e.g., soccer supplier usa, cricket equipment india"
        )
    
    with col2:
        max_results = st.number_input("Max Results", min_value=1, max_value=50, value=15)
    
    if st.button("🔍 Search Companies", type="primary", use_container_width=True):
        with st.spinner("Searching DuckDuckGo for companies..."):
            result = make_api_request("GET", "/search/", params={"q": query, "max_results": max_results})
            
            if result:
                st.session_state.search_results = result.get('companies', [])
                st.success(f"Found {result.get('total_found', 0)} companies!")
                st.info("👈 Go to 'Step 2: Select & Scrape' to choose which companies to scrape")
    
    # Display current search results
    if st.session_state.search_results:
        st.divider()
        st.subheader("Current Search Results")

        new_count = len([c for c in st.session_state.search_results if not c.get('already_exists')])
        existing_count = len([c for c in st.session_state.search_results if c.get('already_exists')])

        col_a, col_b, col_c = st.columns([1, 1, 2])
        with col_a:
            st.metric("New Companies", new_count)
        with col_b:
            st.metric("Already in Database", existing_count)
        with col_c:
            # Add Run All Tasks button
            if new_count > 0:
                if st.button("🚀 Run All Tasks - Scrape All New Companies", type="primary", use_container_width=True):
                    scrape_all_companies(new_count)

        # Show results table
        df = pd.DataFrame(st.session_state.search_results)
        st.dataframe(df, use_container_width=True, hide_index=True)


def scrape_all_companies(new_count):
    """Scrape all new companies at once"""
    new_companies = [c for c in st.session_state.search_results if not c.get('already_exists')]

    if not new_companies:
        st.warning("No new companies to scrape!")
        return

    st.info(f"Queuing {len(new_companies)} companies for scraping...")

    task_count = 0
    for company in new_companies:
        result = make_api_request("POST", "/scrape/single/", json={
            "name": company.get('name'),
            "website": company.get('website'),
            "max_pages": 5,
        })

        if result:
            task_id = result.get('celery_task_id')
            if task_id:
                st.session_state.scraping_tasks[task_id] = {
                    'name': company.get('name'),
                    'website': company.get('website'),
                    'started': datetime.now(),
                    'status': 'pending'
                }
                task_count += 1

    if task_count > 0:
        st.success(f"✅ Queued {task_count} companies for scraping!")
        st.info("Go to '🔄 Check Tasks' page to monitor progress")
    else:
        st.error("❌ Failed to queue any tasks")


def render_select_scrape_page():
    """Step 2: Select companies and scrape individually"""
    st.header("✅ Step 2: Select & Scrape")

    if not st.session_state.search_results:
        st.warning("No search results yet. Go to 'Step 1: Search Companies' first.")
        return

    # Filter options
    show_option = st.radio("Show:", ["All Results", "New Only (not in database)", "Existing Only"], horizontal=True)

    # Filter companies based on selection
    companies = st.session_state.search_results
    if show_option == "New Only (not in database)":
        companies = [c for c in companies if not c.get('already_exists')]
    elif show_option == "Existing Only":
        companies = [c for c in companies if c.get('already_exists')]

    st.caption(f"Showing {len(companies)} companies")

    # Scraping settings
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        max_pages = st.number_input("Pages to crawl per site", min_value=1, max_value=10, value=5)
    with col3:
        # Add Run All button here too
        if len([c for c in companies if not c.get('already_exists')]) > 0:
            if st.button("🚀 Run All", type="primary", use_container_width=True):
                scrape_all_companies(len(companies))

    st.divider()
    
    # Display each company with Scrape button
    for i, company in enumerate(companies):
        with st.container():
            col_name, col_info, col_action = st.columns([2, 2, 1])
            
            with col_name:
                st.markdown(f"**{company.get('name', 'Unknown')}**")
                st.caption(f"🌐 [{company.get('website', 'N/A')}]({company.get('website', '#')})")
            
            with col_info:
                if company.get('already_exists'):
                    st.error("⚠️ Already in database")
                else:
                    snippet = company.get('snippet', '')
                    if snippet:
                        st.caption(snippet[:100] + "..." if len(snippet) > 100 else snippet)
            
            with col_action:
                if company.get('already_exists'):
                    st.button("Exists", disabled=True, key=f"btn_{i}")
                else:
                    btn_key = f"scrape_{i}_{company.get('website', '')}"
                    if st.button("🚀 Scrape", type="primary", key=btn_key):
                        scrape_company(company, max_pages)
            
            st.divider()


def scrape_company(company, max_pages):
    """Scrape a single selected company"""
    with st.spinner(f"Scraping {company.get('name')}..."):
        # Use async endpoint for background processing
        result = make_api_request("POST", "/scrape/single/", json={
            "name": company.get('name'),
            "website": company.get('website'),
            "max_pages": max_pages,
        })
        
        if result:
            task_id = result.get('celery_task_id')
            if task_id:
                st.session_state.scraping_tasks[task_id] = {
                    'name': company.get('name'),
                    'website': company.get('website'),
                    'started': datetime.now(),
                    'status': 'pending'
                }
                st.success(f"✅ Queued! Task ID: `{task_id}`")
                st.info("Check 'Check Tasks' page for progress")
            else:
                st.error(f"❌ No task ID returned. Response: {result}")
        else:
            st.error("❌ Failed to queue task. Check API connection and Celery worker.")


def render_leads_page():
    """View scraped leads with phone numbers and social media"""
    st.header("📋 Scraped Leads")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Status", ["All", "new", "contacted", "responded", "converted"])
    with col2:
        email_filter = st.selectbox("Email", ["All", "Has Email", "No Email"])
    with col3:
        refresh = st.button("🔄 Refresh")

    # Build params
    params = {}
    if status_filter != "All":
        params['status'] = status_filter
    if email_filter == "Has Email":
        params['has_email'] = True
    elif email_filter == "No Email":
        params['has_email'] = False

    # Fetch leads
    with st.spinner("Loading leads..."):
        data = make_api_request("GET", "/leads/", params=params)

    if data and 'results' in data:
        leads = data['results']
        st.caption(f"Found {len(leads)} leads")

        for lead in leads:
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])

                with col1:
                    st.markdown(f"**{lead.get('name', 'Unknown')}**")
                    st.caption(f"🌐 [{lead.get('domain', 'N/A')}]({lead.get('website', '#')})")

                    # Show phone if available
                    phone = lead.get('phone', '')
                    if phone:
                        st.caption(f"📞 {phone}")

                    # Show location if available
                    country = lead.get('country', '')
                    city = lead.get('city', '')
                    if country or city:
                        location = f"📍 {city}, {country}" if (city and country) else f"📍 {city or country}"
                        st.caption(location)

                with col2:
                    email = lead.get('email', '')
                    if email:
                        validated = "✅" if lead.get('email_validated') else "⚠️"
                        st.markdown(f"{validated} **{email}**")
                    else:
                        st.caption("❌ No email")
                    st.caption(f"Status: `{lead.get('status', 'new')}`")

                    # Show social media links
                    social = lead.get('social_media', {})
                    social_links = []
                    if social.get('linkedin'):
                        social_links.append(f"[LinkedIn]({social['linkedin']})")
                    if social.get('facebook'):
                        social_links.append(f"[Facebook]({social['facebook']})")
                    if social.get('instagram'):
                        social_links.append(f"[Instagram]({social['instagram']})")
                    if social.get('twitter'):
                        social_links.append(f"[Twitter]({social['twitter']})")

                    if social_links:
                        st.caption(" | ".join(social_links))

                with col3:
                    if lead.get('website'):
                        st.link_button("Visit", lead['website'], use_container_width=True)
                    if email:
                        st.link_button("Email", f"mailto:{email}", use_container_width=True)

                st.divider()


def render_tasks_page():
    """Check scraping task status"""
    st.header("🔄 Scraping Tasks")
    
    # Check individual task status
    task_id = st.text_input("Enter Task ID to check status", placeholder="paste-task-id-here")
    if task_id and st.button("Check Status"):
        with st.spinner("Checking..."):
            result = make_api_request("GET", f"/tasks/{task_id}/status/")
            if result:
                st.json(result)
                
                if result.get('ready') and result.get('status') == 'SUCCESS':
                    task_result = result.get('result', {})
                    if task_result.get('status') == 'success':
                        st.success(f"✅ Lead created! Email: {task_result.get('email')}")
                    elif task_result.get('status') == 'duplicate':
                        st.warning("⚠️ Duplicate - already exists")
                    elif task_result.get('status') == 'no_emails':
                        st.info("ℹ️ No emails found on this website")
    
    # Show recent tasks
    if st.session_state.scraping_tasks:
        st.divider()
        st.subheader("Your Recent Scraping Tasks")
        
        for task_id, task_info in st.session_state.scraping_tasks.items():
            with st.expander(f"{task_info['name']} ({task_info['website'][:30]}...)"):
                st.write(f"**Task ID:** `{task_id}`")
                st.write(f"**Started:** {task_info['started'].strftime('%H:%M:%S')}")
                elapsed = (datetime.now() - task_info['started']).seconds
                st.write(f"**Elapsed:** {elapsed}s")
                
                if st.button("Check This Task", key=f"check_{task_id}"):
                    result = make_api_request("GET", f"/tasks/{task_id}/status/")
                    if result:
                        st.json(result)


if __name__ == "__main__":
    main()
