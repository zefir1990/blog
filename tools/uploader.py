#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import sys
import argparse
import base64
import time
from dotenv import load_dotenv
import os

load_dotenv()

parser = argparse.ArgumentParser(description="Upload or update a WordPress post.")
parser.add_argument("--post", required=True, help="Path to the post file.")
parser.add_argument("--blog", required=True, help="Path to the auth file with login and Application Password.")

args = parser.parse_args()
file_path = args.post
auth_file = args.blog

REQUEST_TIMEOUT = 60

site_url = os.environ["SITE_URL"]
username = os.environ["SITE_USER"]
app_password = os.environ["SITE_PASSWORD"]

auth_token = base64.b64encode(f"{username}:{app_password}".encode()).decode()

api_url_posts = f"{site_url}/wp-json/wp/v2/posts"
api_url_categories = f"{site_url}/wp-json/wp/v2/categories"

auth_headers = {
    "Authorization": f"Basic {auth_token}",
    "Accept": "application/json"
}

post_headers = {
    "Authorization": f"Basic {auth_token}",
    "Content-Type": "application/json"
}

def get_all_categories():
    categories = []
    page = 1
    max_pages = 10
    
    while page <= max_pages:
        print(f"Fetching categories page {page}...")
        try:
            print(api_url_categories)
            response = requests.get(
                api_url_categories, 
                headers=auth_headers, 
                params={"per_page": 100, "page": page},
                timeout=REQUEST_TIMEOUT
            )
            print(f"Response received: {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"Request timed out after {REQUEST_TIMEOUT} seconds")
            sys.exit(1)
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error: {e}")
            sys.exit(1)
            
        if response.status_code == 200:
            try:
                data = response.json()
                # Debug the actual structure of the data
                print(f"Data type: {type(data)}")
                if isinstance(data, list):
                    print(f"Received {len(data)} categories on page {page}")
                    if len(data) > 0:
                        print(f"First category structure: {type(data[0])}")
                        # Print first category keys if it's a dictionary
                        if isinstance(data[0], dict):
                            print(f"First category keys: {data[0].keys()}")
                else:
                    print(f"Data is not a list but: {type(data)}")
                    print(f"Data content: {data}")
                
                if not data:
                    print("No more categories found, breaking loop")
                    break
                    
                # Make sure we're adding the right kind of data
                if isinstance(data, list):
                    categories.extend(data)
                else:
                    # If it's not a list, try to handle it appropriately
                    print("Warning: Expected a list of categories but received something else")
                    # If it's a dict with 'categories' key, use that
                    if isinstance(data, dict) and 'categories' in data:
                        categories.extend(data['categories'])
                    # Otherwise just append it
                    else:
                        categories.append(data)
                
                # Check if we've received fewer items than requested per_page
                # This means we've reached the last page
                if isinstance(data, list) and len(data) < 100:
                    print("Last page reached (fewer than 100 items returned)")
                    break
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                print(f"Response content: {response.text[:500]}...")
                break
                
            page += 1
        else:
            print(f"Failed to fetch categories. Status code: {response.status_code}")
            try:
                error_details = response.json()
                print(f"Error details: {error_details}")
            except:
                print(f"Response content: {response.text}")
            sys.exit(1)
    return categories

def get_category_ids(category_names):
    all_categories = get_all_categories()
    print(f"Total categories fetched: {len(all_categories)}")
    # If we have any categories, print the first one as example
    if len(all_categories) > 0:
        print(f"Example category data: {all_categories[0]}")
    
    category_ids = []
    for name in category_names:
        print(f"Looking for category: '{name}'")
        found = False
        for category in all_categories:
            # Make sure category is a dictionary before accessing keys
            if isinstance(category, dict) and 'slug' in category:
                if category['slug'].lower() == name.lower().strip():
                    category_ids.append(category['id'])
                    found = True
                    print(f"Found category '{name}' with ID {category['id']}")
                    break
            elif isinstance(category, str):
                # If category is a string, compare directly
                if category.lower() == name.lower().strip():
                    # We might not have an ID if it's just a string
                    # In this case we'll use the name as the ID
                    print(f"Category '{name}' is a string, not an object with ID")
                    category_ids.append(name)
                    found = True
                    break
            else:
                print(f"Unexpected category type: {type(category)}")
        if not found:
            print(f"Category '{name}' not found.")
            sys.exit(1)
    return category_ids

with open(file_path, "r", encoding="utf-8") as file:
    lines = file.readlines()
    if len(lines) < 4:
        print("File must contain at least four lines: slug, title, categories, and content.")
        sys.exit(1)
    
    slug = lines[0].strip()
    post_title = lines[1].strip()
    category_names = lines[2].strip().split(",")
    content = ''.join(lines[3:]).strip()

category_ids = get_category_ids(category_names)

search_params = {"slug": slug}
try:
    response = requests.get(
        api_url_posts, 
        headers=auth_headers, 
        params=search_params,
        timeout=REQUEST_TIMEOUT
    )
except requests.exceptions.Timeout:
    print(f"Request timed out after {REQUEST_TIMEOUT} seconds")
    sys.exit(1)
except requests.exceptions.ConnectionError as e:
    print(f"Connection error: {e}")
    sys.exit(1)
posts = response.json()

if posts:
    for post in posts:
        post_id = post["id"]
        post_url = post.get("link", f"{site_url}?p={post_id}")
        print(f"Removing old post: ID {post_id}, URL {post_url}")

        try:
            delete_response = requests.delete(
                f"{api_url_posts}/{post_id}",
                headers=auth_headers,
                params={"force": "true"},
                timeout=REQUEST_TIMEOUT
            )
        except requests.exceptions.Timeout:
            print(f"Request timed out after {REQUEST_TIMEOUT} seconds")
            sys.exit(1)
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error: {e}")
            sys.exit(1)

        if delete_response.status_code != 200:
            print(f"Failed to remove old post: {delete_response.status_code}")
            print(f"Response content: {delete_response.text}")
            sys.exit(1)

        print(f"Old post removed. ID: {post_id}")

create_data = {
    "title": post_title,
    "content": content,
    "slug": slug,
    "status": "publish",
    "categories": category_ids
}

try:
    create_response = requests.post(
        api_url_posts,
        headers=post_headers,
        json=create_data,
        timeout=REQUEST_TIMEOUT
    )
except requests.exceptions.Timeout:
    print(f"Request timed out after {REQUEST_TIMEOUT} seconds")
    sys.exit(1)
except requests.exceptions.ConnectionError as e:
    print(f"Connection error: {e}")
    sys.exit(1)
if create_response.status_code == 201:
    new_post_id = create_response.json()["id"]
    print(f"Post created successfully. ID: {new_post_id}")
else:
    print(f"Failed to create post: {create_response.status_code}")
    try:
        error_details = create_response.json()
        print(f"Error details: {error_details}")
    except:
        print(f"Response content: {create_response.text}")
