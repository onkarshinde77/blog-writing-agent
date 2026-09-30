# from __future__ import annotations
# import argparse
# import os
# from datetime import datetime, timezone
# from urllib.parse import quote
# import requests
# from dotenv import load_dotenv


# TIMEOUT = 25
# load_dotenv()


# def _error_detail(response: requests.Response) -> str:
#     """Return a short API error description without printing headers or tokens."""
#     try:
#         payload = response.json()
#     except ValueError:
#         return (response.text or "No response body")[:400]
#     if isinstance(payload, dict):
#         details = payload.get("message") or payload.get("error_description") or payload.get("error") or payload
#         return str(details)[:400]
#     return str(payload)[:400]


# def _report(label: str, response: requests.Response) -> bool:
#     if response.ok:
#         print(f"[PASS] {label}: HTTP {response.status_code}")
#         return True
#     print(f"[FAIL] {label}: HTTP {response.status_code} — {_error_detail(response)}")
#     return False


# def _probe_api(label: str, url: str) -> bool:
#     """Check that the provider responds even when no OAuth token is configured."""
#     try:
#         response = requests.get(url, timeout=TIMEOUT)
#     except requests.RequestException as exc:
#         print(f"[FAIL] {label} reachability: network error: {exc}")
#         return False
#     print(f"[INFO] {label} endpoint reachable: HTTP {response.status_code} without credentials")
#     return True


# def _wordpress_credentials() -> tuple[str | None, str | None]:
#     try:
#         from src.publishing.linkedin_oauth import get_wordpress_site_id, get_wordpress_token

#         return get_wordpress_token(), os.getenv("WORDPRESS_SITE_ID") or get_wordpress_site_id()
#     except Exception as exc:
#         print(f"[FAIL] WordPress local OAuth storage: {type(exc).__name__}: {exc}")
#         return None, None


# def check_wordpress(post_test: bool) -> bool:
#     print("\nWordPress.com")
#     token, site = _wordpress_credentials()
#     site_path = quote(str(site).strip(), safe=".-_") if site else None
#     if not token:
#         probe_url = (
#             f"https://public-api.wordpress.com/rest/v1.1/sites/{site_path}"
#             if site_path else "https://public-api.wordpress.com/rest/v1.1/me"
#         )
#         reachable = _probe_api("WordPress.com", probe_url)
#         print("[FAIL] No usable WordPress OAuth token. Connect WordPress.com in the app first.")
#         if not reachable:
#             print("       The host could not be reached from this machine; check DNS/firewall/VPN.")
#         return False
#     if not site:
#         print("[FAIL] No WordPress site ID/URL. Set WORDPRESS_SITE_ID or reconnect the site.")
#         return False

#     headers = {"Authorization": f"Bearer {token}"}
#     try:
#         response = requests.get(
#             f"https://public-api.wordpress.com/rest/v1.1/sites/{site_path}",
#             headers=headers,
#             timeout=TIMEOUT,
#         )
#     except requests.RequestException as exc:
#         print(f"[FAIL] WordPress site check: network error: {exc}")
#         return False
#     ok = _report("OAuth token and site access", response)
#     if not ok:
#         return False
#     try:
#         details = response.json()
#         print(f"       Site: {details.get('name') or details.get('URL') or site}")
#     except ValueError:
#         pass

#     if not post_test:
#         print("[SKIP] Post creation (run with --post-test to create a draft).")
#         return True

#     stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
#     title = f"Publishing API test — {stamp}"
#     form = {
#         "title": title,
#         "content": "<p>Temporary WordPress.com API integration test. This post was created as a draft.</p>",
#         "excerpt": "Temporary API test draft; safe to delete.",
#         "status": "draft",
#     }
#     try:
#         response = requests.post(
#             f"https://public-api.wordpress.com/rest/v1.1/sites/{site_path}/posts/new/",
#             headers=headers,
#             data=form,
#             timeout=TIMEOUT,
#         )
#     except requests.RequestException as exc:
#         print(f"[FAIL] WordPress draft creation: network error: {exc}")
#         return False
#     ok = _report("Create WordPress draft", response)
#     if ok:
#         result = response.json()
#         print(f"       Draft ID: {result.get('ID') or result.get('id', 'unknown')}")
#         if result.get("URL") or result.get("url"):
#             print(f"       Draft URL: {result.get('URL') or result.get('url')}")
#     return ok


# def _linkedin_credentials() -> tuple[str | None, str | None]:
#     try:
#         from src.publishing.linkedin_oauth import get_linkedin_author, get_linkedin_token

#         token = get_linkedin_token() or os.getenv("LINKEDIN_ACCESS_TOKEN")
#         author = get_linkedin_author() or os.getenv("LINKEDIN_AUTHOR_URN")
#         return token, author
#     except Exception as exc:
#         print(f"[FAIL] LinkedIn local OAuth storage: {type(exc).__name__}: {exc}")
#         return os.getenv("LINKEDIN_ACCESS_TOKEN"), os.getenv("LINKEDIN_AUTHOR_URN")


# def check_linkedin(post_test: bool) -> bool:
#     print("\nLinkedIn")
#     token, author = _linkedin_credentials()
#     if not token:
#         _probe_api("LinkedIn", "https://api.linkedin.com/v2/userinfo")
#         print("[FAIL] No usable LinkedIn OAuth token. Connect LinkedIn in the app first.")
#         return False
#     if not author or not author.startswith("urn:li:person:"):
#         print("[FAIL] Missing/invalid member author URN. Reconnect LinkedIn or set LINKEDIN_AUTHOR_URN.")
#         return False

#     headers = {"Authorization": f"Bearer {token}"}
#     try:
#         response = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=TIMEOUT)
#     except requests.RequestException as exc:
#         print(f"[FAIL] LinkedIn identity check: network error: {exc}")
#         return False
#     identity_ok = _report("OAuth token and member identity", response)
#     if identity_ok:
#         try:
#             profile = response.json()
#             print(f"       Member: {profile.get('name') or 'identity verified'}")
#         except ValueError:
#             pass

#     if not post_test:
#         print("[SKIP] Post creation (run with --post-test to publish a clearly labeled test post).")
#         return identity_ok

#     stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
#     version = os.getenv("LINKEDIN_API_VERSION", "202608")
#     headers.update({
#         "LinkedIn-Version": version,
#         "X-Restli-Protocol-Version": "2.0.0",
#         "Content-Type": "application/json",
#     })
#     payload = {
#         "author": author,
#         "commentary": f"Publishing API test ({stamp}). This is a temporary test post from my blog-writing agent.",
#         "visibility": "PUBLIC",
#         "distribution": {
#             "feedDistribution": "MAIN_FEED",
#             "targetEntities": [],
#             "thirdPartyDistributionChannels": [],
#         },
#         "lifecycleState": "PUBLISHED",
#         "isReshareDisabledByAuthor": True,
#     }
#     try:
#         response = requests.post(
#             "https://api.linkedin.com/rest/posts",
#             headers=headers,
#             json=payload,
#             timeout=TIMEOUT,
#         )
#     except requests.RequestException as exc:
#         print(f"[FAIL] LinkedIn test post: network error: {exc}")
#         return False
#     ok = _report("Publish LinkedIn test post", response)
#     if ok:
#         post_id = response.headers.get("x-restli-id", "unknown")
#         print(f"       Post ID: {post_id}")
#         if post_id != "unknown":
#             print(f"       Post URL: https://www.linkedin.com/feed/update/{post_id}")
#     return ok and identity_ok


# def main() -> int:
#     parser = argparse.ArgumentParser(description="Check WordPress.com and LinkedIn publishing APIs.")
#     parser.add_argument(
#         "--post-test",
#         action="store_true",
#         help="Create a WordPress draft and publish a clearly labeled PUBLIC LinkedIn test post.",
#     )
#     args = parser.parse_args()

#     results = [check_wordpress(args.post_test), check_linkedin(args.post_test)]
#     print("\nSummary: " + ("both checks passed" if all(results) else "one or more checks failed"))
#     return 0 if all(results) else 1


# if __name__ == "__main__":
#     raise SystemExit(main())



""" This Code is used for get site code of wordpress """ 
# from __future__ import annotations
# import os
# import webbrowser
# import requests
# from urllib.parse import urlencode
# from dotenv import load_dotenv
# load_dotenv()

# TOKEN_URL = "https://public-api.wordpress.com/oauth2/token"
# AUTH_URL = "https://public-api.wordpress.com/oauth2/authorize"
# CLIENT_ID = os.getenv("WORDPRESS_CLIENT_ID")
# CLIENT_SECRET = os.getenv("WORDPRESS_CLIENT_SECRET")
# REDIRECT_URI = os.getenv(
#     "WORDPRESS_REDIRECT_URI",
#     "http://localhost:8000/auth/wordpress/callback",
# )
# SITE_URL = os.getenv("WORDPRESS_SITE_URL","https://onkarai.wordpress.com",)
# TIMEOUT = 30

# # STEP 1: Create WordPress OAuth authorization URL
# def create_auth_url():
#     print("\n[1] Creating WordPress authorization URL...")
#     # Request access only to the selected WordPress site.
#     params = {
#         "client_id": CLIENT_ID,
#         "redirect_uri": REDIRECT_URI,
#         "response_type": "code",
#         "blog": SITE_URL,
#         "scope": "posts",
#     }

#     url = AUTH_URL + "?" + urlencode(params)
#     print("\nOpen this URL:")
#     print(url)
#     webbrowser.open(url)
#     return url

# # STEP 2: Get authorization code
# def get_authorization_code():
#     print("\n[2] Login to WordPress and click Allow.")
#     print("\nAfter approval, WordPress will redirect to something like:")
#     print(f"{REDIRECT_URI}?code=XXXXXXXX")
#     code = input("\nPaste only the value after 'code=': ").strip()
#     if not code:
#         raise RuntimeError("Authorization code is empty.")
#     print("[PASS] Authorization code received.")
#     return code

# # STEP 3: Exchange authorization code for access token
# def get_access_token(code):
#     print("\n[3] Exchanging authorization code for access token...")
#     response = requests.post(
#         TOKEN_URL,
#         data={
#             "client_id": CLIENT_ID,
#             "client_secret": CLIENT_SECRET,
#             "code": code,
#             "grant_type": "authorization_code",
#             "redirect_uri": REDIRECT_URI,
#         },
#         timeout=TIMEOUT,
#     )
#     print("HTTP:", response.status_code)
#     if not response.ok:
#         print("Response:")
#         print(response.text)
#         raise RuntimeError("Failed to get access token.")

#     data = response.json()
#     access_token = data.get("access_token")
#     if not access_token:
#         print("Response:")
#         print(data)
#         raise RuntimeError("No access token returned.")

#     blog_id = data.get("blog_id")
#     blog_url = data.get("blog_url")

#     print("[PASS] Access token received.")
#     print("[INFO] Blog ID :", blog_id)
#     print("[INFO] Blog URL:", blog_url)
#     return data

# # STEP 4: Print final WordPress site information
# def print_site_information(token_data):
#     print("\n[4] WordPress site information...")

#     access_token = token_data.get("access_token")
#     site_id = token_data.get("blog_id")
#     site_url = token_data.get("blog_url")

#     if not site_id:
#         raise RuntimeError(
#             "WordPress did not return blog_id in the token response."
#         )

#     print("\n========================================")
#     print("WORDPRESS OAUTH SUCCESS")
#     print("========================================")
#     print("Access Token : received")
#     print("Site ID      :", site_id)
#     print("Site URL     :", site_url)
#     print("========================================")

#     print("\nAdd this to your .env:")
#     print(f"WORDPRESS_SITE_ID={site_id}")
#     return access_token, site_id, site_url

# # MAIN
# def main():
#     create_auth_url()
#     code = get_authorization_code()
#     token_data = get_access_token(code)
#     print_site_information(token_data)

# if __name__ == "__main__":
#     main()



""" Linkedin Access Token """
# import secrets
# import threading
# import os
# import time
# import webbrowser
# from http.server import BaseHTTPRequestHandler, HTTPServer
# from urllib.parse import urlencode, urlparse, parse_qs
# from dotenv import load_dotenv
# load_dotenv()
# import requests

# # CONFIGURATION
# CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
# CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
# REDIRECT_URI = "http://localhost:8000/auth/linkedin/callback"
# SCOPES = "openid profile email"
# AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
# TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
# USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

# # Generate CSRF protection state
# STATE = secrets.token_urlsafe(32)
# # GLOBAL VARIABLES
# authorization_code = None
# oauth_error = None
# # CALLBACK SERVER

# class OAuthCallbackHandler(BaseHTTPRequestHandler):
#     def do_GET(self):
#         global authorization_code
#         global oauth_error
#         query = parse_qs(urlparse(self.path).query)
#         returned_state = query.get("state", [None])[0]
#         authorization_code = query.get("code", [None])[0]
#         oauth_error = query.get("error", [None])[0]

#         # Validate state
#         if returned_state != STATE:
#             authorization_code = None
#             oauth_error = "Invalid OAuth state."

#         # Send response to browser
#         self.send_response(200)
#         self.send_header("Content-Type", "text/html")
#         self.end_headers()

#         if authorization_code:
#             self.wfile.write(
#                 b"""
#                 <html>
#                 <body>
#                     <h2>LinkedIn authorization successful.</h2>
#                     <p>You can close this browser window.</p>
#                 </body>
#                 </html>
#                 """
#             )
#         else:
#             self.wfile.write(
#                 b"""
#                 <html>
#                 <body>
#                     <h2>LinkedIn authorization failed.</h2>
#                     <p>You can close this browser window.</p>
#                 </body>
#                 </html>
#                 """
#             )

#     def log_message(self, format, *args):
#         # Disable HTTP server logs
#         pass

# # START LOCAL CALLBACK SERVER
# def start_callback_server():
#     server = HTTPServer(("localhost", 8000),OAuthCallbackHandler)
#     thread = threading.Thread(target=server.handle_request,daemon=True)
#     thread.start()
#     return server

# # CREATE LINKEDIN AUTHORIZATION URL
# def create_authorization_url():
#     params = {
#         "response_type": "code",
#         "client_id": CLIENT_ID,
#         "redirect_uri": REDIRECT_URI,
#         "state": STATE,
#         "scope": SCOPES,
#     }
#     return f"{AUTH_URL}?{urlencode(params)}"

# # EXCHANGE AUTHORIZATION CODE FOR ACCESS TOKEN
# def get_access_token(code):
#     data = {
#         "grant_type": "authorization_code",
#         "code": code,
#         "client_id": CLIENT_ID,
#         "client_secret": CLIENT_SECRET,
#         "redirect_uri": REDIRECT_URI,
#     }

#     response = requests.post(
#         TOKEN_URL,
#         data=data,
#         timeout=30
#     )

#     response.raise_for_status()
#     return response.json()

# # GET LINKEDIN USER INFORMATION
# def get_user_info(access_token):
#     headers = {"Authorization": f"Bearer {access_token}"}
#     response = requests.get(USERINFO_URL,headers=headers,timeout=30)
#     response.raise_for_status()
#     return response.json()

# # CREATE AUTHOR URN
# def create_author_urn(user_info):
#     member_id = user_info.get("sub")
#     if not member_id:
#         raise ValueError("LinkedIn userinfo response does not contain 'sub'.")
#     return f"urn:li:person:{member_id}"

# # MAIN
# def main():
#     print("\n==========================================")
#     print(" LinkedIn OAuth Token Generator")
#     print("==========================================\n")

#     if CLIENT_ID == "YOUR_LINKEDIN_CLIENT_ID":
#         raise ValueError("Please set CLIENT_ID.")
#     if CLIENT_SECRET == "YOUR_LINKEDIN_CLIENT_SECRET":
#         raise ValueError("Please set CLIENT_SECRET.")

#     print("Starting local callback server...")
#     start_callback_server()
#     authorization_url = create_authorization_url()
#     print("\nOpening LinkedIn authorization page...\n")
#     webbrowser.open(authorization_url)

#     print("Please:")
#     print("1. Login to LinkedIn")
#     print("2. Approve the application")
#     print("3. Wait for the redirect\n")
#     # Wait for OAuth callback
#     timeout = 180
#     start_time = time.time()

#     while authorization_code is None and oauth_error is None:
#         if time.time() - start_time > timeout:
#             raise TimeoutError("Timed out waiting for LinkedIn authorization.")
#         time.sleep(0.5)

#     if oauth_error:
#         raise RuntimeError(f"LinkedIn OAuth failed: {oauth_error}")

#     print("Authorization code received.")
#     print("Exchanging code for access token...\n")

#     token_data = get_access_token(authorization_code)
#     access_token = token_data.get("access_token")

#     if not access_token:
#         raise RuntimeError(f"LinkedIn did not return an access token:\n"f"{token_data}")

#     print("Access token received.")

#     # Get member information
#     user_info = get_user_info(access_token)
#     author_urn = create_author_urn(user_info)

#     print("\n==========================================")
#     print(" LINKEDIN CREDENTIALS")
#     print("==========================================\n")

#     print(f"LINKEDIN_ACCESS_TOKEN={access_token}")
#     print(f"LINKEDIN_AUTHOR_URN={author_urn}")

#     print("\n==========================================")
#     print(" Additional information")
#     print("==========================================\n")

#     print(f"Name       : {user_info.get('name')}")
#     print(f"Given name : {user_info.get('given_name')}")
#     print(f"Family name: {user_info.get('family_name')}")
#     print(f"Member ID  : {user_info.get('sub')}")

#     if "expires_in" in token_data:
#         print(f"Expires in : "f"{token_data['expires_in']} seconds")
#     print("\nCopy the two values into your .env file.")
#     print("Do NOT commit them to Git.")

# if __name__ == "__main__":
#     main()

