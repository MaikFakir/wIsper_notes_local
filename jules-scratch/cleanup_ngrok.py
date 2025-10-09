from pyngrok import ngrok
import os

# Set auth token from environment or file, to ensure the client is authenticated
ngrok_authtoken = os.environ.get("NGROK_AUTHTOKEN")
if not ngrok_authtoken:
    try:
        with open(".ngrok_authtoken", "r") as f:
            ngrok_authtoken = f.read().strip()
    except FileNotFoundError:
        pass # No token, will proceed but might have issues

if ngrok_authtoken:
    ngrok.set_auth_token(ngrok_authtoken)

try:
    # Get all active tunnels
    tunnels = ngrok.get_tunnels()
    if tunnels:
        for tunnel in tunnels:
            print(f"Disconnecting tunnel: {tunnel.public_url}")
            ngrok.disconnect(tunnel.public_url)
    else:
        print("No active ngrok tunnels found.")

    # Kill the ngrok process
    print("Shutting down ngrok process...")
    ngrok.kill()
    print("Cleanup complete.")

except Exception as e:
    print(f"An error occurred during cleanup: {e}")
    print("Attempting to kill ngrok process directly.")
    try:
        ngrok.kill()
        print("ngrok process killed.")
    except Exception as kill_e:
        print(f"Failed to kill ngrok process: {kill_e}")