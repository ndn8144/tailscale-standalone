import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Tailscale settings
    TS_OAUTH_CLIENT_ID = os.getenv('TS_OAUTH_CLIENT_ID')
    TS_OAUTH_CLIENT_SECRET = os.getenv('TS_OAUTH_CLIENT_SECRET') 
    TS_TAILNET = os.getenv('TS_TAILNET', '-')
    TS_API_BASE = "https://api.tailscale.com/api/v2"
    
    # Build settings
    BUILD_OUTPUT_DIR = os.getenv('BUILD_OUTPUT_DIR', 'builds')
    TEMP_DIR = os.getenv('TEMP_DIR', 'temp')
    
    # URLs
    TAILSCALE_MSI_URL = "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi"
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

config = Config()