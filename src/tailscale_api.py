import httpx
import asyncio
from datetime import datetime, timedelta
import logging
from config import config

logger = logging.getLogger(__name__)

class TailscaleAPI:
    def __init__(self):
        self.client_id = config.TS_OAUTH_CLIENT_ID
        self.client_secret = config.TS_OAUTH_CLIENT_SECRET
        self.tailnet = config.TS_TAILNET
        self.base_url = config.TS_API_BASE
        self._access_token = None
        self._token_expires = None
    
    async def get_access_token(self):
        """Get OAuth access token"""
        if self._access_token and self._token_expires and datetime.now() < self._token_expires:
            return self._access_token
        
        logger.info("Getting new access token...")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tailscale.com/api/v2/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                    "scope": "auth_keys devices:core"
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"OAuth failed: {response.text}")
            
            data = response.json()
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expires = datetime.now() + timedelta(seconds=expires_in - 60)  # 1 min buffer
            
            logger.info("Access token obtained successfully")
            return self._access_token
    
    async def _request(self, method, endpoint, **kwargs):
        """Make authenticated request to Tailscale API"""
        token = await self.get_access_token()
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {token}'
        kwargs['headers'] = headers
        
        url = f"{self.base_url}/tailnet/{self.tailnet}/{endpoint}"
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, url, **kwargs)
            
            if response.status_code >= 400:
                raise Exception(f"API error {response.status_code}: {response.text}")
            
            return response.json() if response.headers.get('content-type', '').startswith('application/json') else response
    
    async def create_auth_key(self, 
                            reusable=True, 
                            ephemeral=False, 
                            preauthorized=True,
                            tags=None, 
                            expires_days=90,
                            description="Standalone deployment"):
        """Create new auth key"""
        
        if tags is None:
            tags = ["tag:employee"]
        
        expires = datetime.now() + timedelta(days=expires_days)
        
        payload = {
            "capabilities": {
                "devices": {
                    "create": {
                        "reusable": reusable,
                        "ephemeral": ephemeral,
                        "preauthorized": preauthorized,
                        "tags": tags
                    }
                }
            },
            "expirySeconds": expires_days * 24 * 3600,
            "description": description
        }
        
        logger.info(f"Creating auth key with tags: {tags}, expires in {expires_days} days")
        
        result = await self._request("POST", "keys", json=payload)
        
        logger.info(f"Auth key created: {result['id']}")
        return result
    
    async def list_devices(self):
        """List all devices in tailnet"""
        return await self._request("GET", "devices")
    
    async def list_auth_keys(self):
        """List all auth keys"""
        return await self._request("GET", "keys")

# Test function
async def test_api():
    api = TailscaleAPI()
    try:
        # Test token
        token = await api.get_access_token()
        print(f"[OK] Token obtained: {token[:20]}...")
        
        # Test create auth key
        key = await api.create_auth_key(
            tags=["tag:test"], 
            expires_days=1,
            description="API test key"
        )
        print(f"[OK] Auth key created: {key['id']}")
        print(f"Key: {key['key'][:20]}...")
        
        # Test list devices
        devices = await api.list_devices()
        print(f"[OK] Found {len(devices['devices'])} devices")
        
    except Exception as e:
        print(f"[ERROR] API test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())